"""H0/H1-family tests on the development period (pre-registration v1 + v2). All trials are logged.

Co-primary (v2): monthly long-short portfolio and filing-level event panel (CAR +1..+60).
Corroboration: monthly rank IC. Variants: 10-K only (v1) vs latest 10-K/10-Q (v2); raw vs
neutralized (industry SIC2, log market cap, 8-K Item 2.01 in prior 12 months).
Development: signals known 2023-01-01..2024-06-30; returns through 2024-07-31.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from asof import ledger
from asof.backtest import (
    Config,
    clean_shares,
    form_portfolios,
    latest_as_of,
    long_short,
    monthly_panel,
)
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.events import CarEngine, event_panel, neutralize, rank_ic
from asof.factors import ff5_umd_daily, ff5_umd_monthly, nyse_me_breakpoints
from asof.inference import nw_alpha
from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
from asof.prices import YahooPrices
from asof.timeutil import first_tradable_close

FACTORS = ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "UMD"]
INPUTS = [DATA_DIR / n for n in ("h0_universe.parquet", "h0_signals.parquet", "h0_shares.parquet",
                                 "bulk_entities.parquet", "bulk_filings.parquet")]


def load_inputs():
    uni = pd.read_parquet(DATA_DIR / "h0_universe.parquet")
    sig = pd.read_parquet(DATA_DIR / "h0_signals.parquet")
    sig["knowledge_time"] = pd.to_datetime(sig["knowledge_time"], utc=True)
    lo = datetime.combine(DEV_START, datetime.min.time(), tzinfo=UTC)
    hi = datetime.combine(DEV_END, datetime.max.time(), tzinfo=UTC)
    sig = sig[(sig["knowledge_time"] >= lo) & (sig["knowledge_time"] <= hi)].copy()
    sig["change"] = 1.0 - sig["cos_full"]
    shares = pd.read_parquet(DATA_DIR / "h0_shares.parquet")
    shares["knowledge_time"] = pd.to_datetime(shares["knowledge_time"], utc=True)
    shares = clean_shares(shares)  # point-in-time removal of XBRL share-count typos (F3)
    ent = pd.read_parquet(DATA_DIR / "bulk_entities.parquet")[["cik", "sic"]]
    fil = pd.read_parquet(DATA_DIR / "bulk_filings.parquet")
    ma = fil[(fil["form"] == "8-K") & fil["items"].fillna("").str.contains(r"\b2\.01\b")][["cik", "knowledge_time"]]
    y = YahooPrices()
    frames, daily_ret = [], {}
    for t in uni["ticker"]:
        try:
            d = y.daily(t, end=DEV_RETURN_CUTOFF)
        except Exception:  # noqa: BLE001, S112 - missing tickers are counted as coverage loss
            continue
        if d.empty:
            continue
        daily_ret[t] = d.set_index("date")["adjclose"].pct_change().dropna()
        frames.append(d[d["date"] >= pd.Timestamp("2022-11-01").date()])
    panel = monthly_panel(pd.concat(frames, ignore_index=True)).merge(uni[["cik", "ticker"]], on="ticker")
    return uni, sig, shares, ent, ma, panel, daily_ret


def add_neutral(sig: pd.DataFrame, shares: pd.DataFrame, ent: pd.DataFrame, ma: pd.DataFrame,
                panel: pd.DataFrame) -> pd.DataFrame:
    """Neutralize each filing's change score within its calendar month, using only data known then."""
    s = sig.merge(ent, on="cik", how="left")
    s["sic2"] = s["sic"].astype(str).str[:2]
    s["month"] = s["knowledge_time"].dt.tz_convert(None).dt.to_period("M")
    s["change_n"] = np.nan
    for m, g in s.groupby("month"):
        as_of = g["knowledge_time"].max()
        sh = latest_as_of(shares, "cik", as_of, ["val"])
        px = panel[panel["month"] == m - 1][["cik", "close"]]
        gg = g.merge(sh, on="cik", how="left").merge(px, on="cik", how="left")
        gg["log_mcap"] = np.log((gg["val"] * gg["close"]).where(lambda v: v > 0))
        recent = ma[(ma["knowledge_time"] < as_of) & (ma["knowledge_time"] >= as_of - pd.Timedelta(days=365))]
        gg["ma_flag"] = gg["cik"].isin(set(recent["cik"])).astype(float)
        gg.index = g.index
        s.loc[g.index, "change_n"] = neutralize(gg, "change", "sic2", ["log_mcap", "ma_flag"])
    return s


def monthly_test(cfg: Config, sig, shares, panel, bp, factors) -> dict:
    months = pd.period_range(pd.Period(DEV_START, "M"), pd.Period(DEV_END, "M"), freq="M")
    rows, prev, ics = [], None, []
    for m in months:
        pm = panel[panel["month"] == m]
        port = form_portfolios(m, sig, shares, pm, float(bp.loc[m, cfg.size_pct]), cfg)
        if port.empty:
            prev = None
            continue
        r = long_short(port, prev, cfg)
        r.update(return_month=str(m + 1), n_firms=len(port))
        rows.append(r)
        ics.append(rank_ic(port[cfg.signal], port["ret_next"]) * (1 if cfg.long_high else -1))
        prev = port
    res = pd.DataFrame(rows)
    if len(res) < 8:
        return {"months": len(res)}
    s = res.set_index(pd.PeriodIndex(res["return_month"], freq="M"))["ls_net"]
    a = nw_alpha(s, factors.loc[s.index.min():s.index.max(), FACTORS], lags=6)
    ic = pd.Series(ics).dropna()
    return {"months": len(s), "mean_net": float(s.mean()), "mean_gross": float(res["ls_gross"].mean()),
            "alpha": a.alpha, "alpha_t": a.t_stat, "avg_firms": float(res["n_firms"].mean()),
            "mean_ic": float(ic.mean()), "ic_t": float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic)))) if len(ic) > 2 else float("nan")}


def event_test(sig: pd.DataFrame, signal: str, daily_ret, engine: CarEngine, uni) -> dict:
    s = sig.merge(uni[["cik", "ticker"]], on="cik").dropna(subset=[signal])
    days = engine.days
    cars = []
    for r in s.itertuples():
        if r.ticker not in daily_ret:
            continue
        day = first_tradable_close(r.knowledge_time.to_pydatetime(), days)
        if day is None:
            continue
        cars.append({"car": engine.car(r.ticker, daily_ret[r.ticker], day, horizon=60), "x": getattr(r, signal),
                     "month": r.knowledge_time.strftime("%Y-%m")})
    c = pd.DataFrame(cars).dropna()
    if len(c) < 30:
        return {"n_events": len(c)}
    p = event_panel(c, "car", "x", "month")
    return {"coef": p.coef, "t": p.t_stat, "n_events": p.n_events, "clusters": p.n_clusters}


def main() -> None:
    uni, sig, shares, ent, ma, panel, daily_ret = load_inputs()
    sig = add_neutral(sig, shares, ent, ma, panel)
    factors = ff5_umd_monthly().loc[: pd.Period(DEV_RETURN_CUTOFF, "M")]
    factors_d = ff5_umd_daily()
    factors_d = factors_d[factors_d.index <= DEV_RETURN_CUTOFF]
    engine = CarEngine(factors_d)
    bp = nyse_me_breakpoints()
    results = []
    variants = {
        "v1_10K_raw": (sig[sig["form"] == "10-K"], "cos_full", True, "change"),
        "v2_latest_raw": (sig, "cos_full", True, "change"),
        "v2_latest_neutral": (sig.assign(neg_change_n=-sig["change_n"]), "neg_change_n", True, "change_n"),
        "v2_10K_neutral": (sig[sig["form"] == "10-K"].assign(neg_change_n=lambda d: -d["change_n"]),
                           "neg_change_n", True, "change_n"),
    }
    for name, (s, col, long_high, ev_col) in variants.items():
        t0 = __import__("time").time()
        cfg = replace(Config(), signal=col, long_high=long_high)
        m = monthly_test(cfg, s, shares, panel, bp, factors)
        e = event_test(s, ev_col, daily_ret, engine, uni)
        print(f"{name}: {__import__('time').time() - t0:.0f}s", file=sys.stderr, flush=True)
        entry = {"variant": name, "config": asdict(cfg), "monthly": m, "event_panel_change_on_car60": e}
        h = ledger.log_trial("H0" if "raw" in name else "H1n", {"variant": name, **asdict(cfg)},
                             "development", {**{f"m_{k}": v for k, v in m.items()}, **{f"e_{k}": v for k, v in e.items()}},
                             inputs=INPUTS)
        entry["config_hash"] = h
        results.append(entry)
    out = {"note": "Development period only (~18 monthly obs). Event panel: expected sign of change->CAR is negative. "
                   "Point estimates for pipeline validation; holdout sealed.",
           "coverage": {"universe": len(uni), "with_prices": len(daily_ret)},
           "results": results, "n_trials": {"H0": ledger.n_trials("H0"), "H1n": ledger.n_trials("H1n")}}
    (PROJECT_ROOT / "results" / "returns_h0_development.json").write_text(json.dumps(out, indent=2, default=float))
    json.dump(out, sys.stdout, indent=2, default=float)


if __name__ == "__main__":
    main()
