"""H5 timestamp-event tests on the development period (pre-registration v2, section 4)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from asof import ledger, store
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.events import car, event_panel
from asof.factors import ff5_umd_daily
from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
from asof.prices import YahooPrices
from asof.timeutil import ET, first_tradable_close


def load_events() -> pd.DataFrame:
    con = store.connect(str(DATA_DIR / "h0.duckdb"), read_only=True)
    lo = datetime.combine(DEV_START, datetime.min.time(), tzinfo=UTC)
    hi = datetime.combine(DEV_END, datetime.max.time(), tzinfo=UTC)
    ev = con.execute(
        "SELECT cik, accession, form, items, knowledge_time FROM filings "
        "WHERE form IN ('8-K', 'NT 10-K', 'NT 10-Q') AND knowledge_time BETWEEN ? AND ?", [lo, hi]).df()
    con.close()
    ev["knowledge_time"] = pd.to_datetime(ev["knowledge_time"], utc=True)
    local = ev["knowledge_time"].dt.tz_convert(ET)
    ev["friday_evening"] = (local.dt.weekday == 4) & (local.dt.hour >= 16)
    items = ev["items"].fillna("")
    ev["item_402"] = items.str.contains(r"\b4\.02\b")
    ev["item_401"] = items.str.contains(r"\b4\.01\b")
    ev["nt"] = ev["form"].str.startswith("NT ")
    return ev


def merge_overlaps(ev: pd.DataFrame, days: int) -> pd.DataFrame:
    """Keep the first event per firm within ``days`` calendar-equivalent trading days (approx. 1.4x)."""
    ev = ev.sort_values(["cik", "knowledge_time"])
    keep, last = [], {}
    gap = pd.Timedelta(days=int(days * 1.4))
    for r in ev.itertuples():
        if r.cik in last and r.knowledge_time - last[r.cik] < gap:
            continue
        keep.append(r.Index)
        last[r.cik] = r.knowledge_time
    return ev.loc[keep]


def mean_car_test(sub: pd.DataFrame) -> dict:
    """Mean CAR with standard errors clustered by calendar month."""
    import statsmodels.api as sm

    fit = sm.OLS(sub["car"], np.ones(len(sub))).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(sub["month"])[0]})
    return {"mean_car": float(fit.params.iloc[0]), "t": float(fit.tvalues.iloc[0]),
            "n": len(sub), "clusters": int(sub["month"].nunique())}


def main() -> None:
    uni = pd.read_parquet(DATA_DIR / "h0_universe.parquet")
    factors = ff5_umd_daily()
    factors = factors[factors.index <= DEV_RETURN_CUTOFF]
    ev = load_events().merge(uni[["cik", "ticker"]], on="cik")
    y = YahooPrices()
    rets: dict[str, pd.Series] = {}
    for t in ev["ticker"].unique():
        d = y.daily(t, end=DEV_RETURN_CUTOFF)
        if not d.empty:
            rets[t] = d.set_index("date")["adjclose"].pct_change().dropna()
    ev = ev[ev["ticker"].isin(rets)]
    trading_days = list(factors.index)

    def cars(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
        out = df.copy()
        out["event_day"] = [first_tradable_close(k.to_pydatetime(), trading_days) for k in out["knowledge_time"]]
        out["car"] = [car(rets[t], factors, d, horizon=horizon) if d else np.nan
                      for t, d in zip(out["ticker"], out["event_day"])]
        out["month"] = pd.PeriodIndex(out["knowledge_time"].dt.tz_convert(None), freq="M").astype(str)
        return out.dropna(subset=["car"])

    results = {}
    eightk = merge_overlaps(ev[ev["form"] == "8-K"], 20)
    a = cars(eightk, 20)
    a["friday_evening"] = a["friday_evening"].astype(float)
    r = event_panel(a, "car", "friday_evening", "month")
    results["H5a_friday_evening_8k"] = {"coef": r.coef, "t": r.t_stat, "n": r.n_events,
                                        "n_treated": int(a["friday_evening"].sum()), "clusters": r.n_clusters}
    for name, mask in (("H5b_nt_filings", ev["nt"]), ("H5c_item_402", ev["item_402"]),
                       ("H5c_item_401", ev["item_401"])):
        sub = cars(merge_overlaps(ev[mask], 60), 60)
        results[name] = mean_car_test(sub) if len(sub) >= 10 else {
            "n": len(sub), "note": "too few events for inference"}
    for name, m in results.items():
        ledger.log_trial(name.split("_")[0], {"test": name, "period": "development"}, "development", m,
                         inputs=[DATA_DIR / "h0_universe.parquet"])
    out = {"note": "Development period only; replication tests use |t| >= 2 with Holm across H5a-c and H6b.",
           "results": results}
    (PROJECT_ROOT / "results" / "returns_h5_development.json").write_text(json.dumps(out, indent=2))
    json.dump(out, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
