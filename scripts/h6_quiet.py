"""H6 quiet downward revisions (pre-registration v2 + D5). Development periods only.

(a) Does a quiet revision predict a formal restatement (10-K/A or 8-K 4.02) within 365 days?
    H4 sample, regular 10-K/10-Q filings accepted 2012-2018, LPM with year FE, clustered by firm.
(b) Mean CAR +1..+60 after quiet revisions, H0 universe, 2023-01-01..2024-06-30 (window <= cutoff).
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta

import numpy as np
import pandas as pd
import statsmodels.api as sm

from asof import ledger
from asof.bulk import iter_companyfacts
from asof.config import DATA_DIR, PROJECT_ROOT, RAW_DIR
from asof.quiet import IS_TAGS, flatten_usd, quiet_down_revisions

FIL = DATA_DIR / "bulk_filings.parquet"
DEV_A = (pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2018-12-31 23:59:59", tz="UTC"))


def detect(ciks: set[int], filings: pd.DataFrame) -> pd.DataFrame:
    by_cik = {c: g for c, g in filings[filings["cik"].isin(ciks)].groupby("cik")}
    out = []
    for cik, data in iter_companyfacts(ciks):
        facts = flatten_usd(data.get("facts", {}), cik, IS_TAGS)
        out.append(quiet_down_revisions(facts, by_cik.get(cik, filings.iloc[0:0])))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def part_a(filings: pd.DataFrame) -> dict:
    sample = set(pd.read_parquet(DATA_DIR / "h4_sample.parquet")["cik"])
    f = filings[filings["cik"].isin(sample)]
    quiet = detect(sample, f)
    base = f[f["form"].isin(["10-K", "10-Q"]) & f["knowledge_time"].between(*DEV_A)].copy()
    base["quiet_down"] = base["accession"].isin(set(quiet["accession"])).astype(float)
    formal = f[(f["form"] == "10-K/A") | f["items"].fillna("").str.contains(r"\b4\.02\b")]
    only402 = f[f["items"].fillna("").str.contains(r"\b4\.02\b")]

    def within(rows, events):
        ev = events.groupby("cik")["knowledge_time"].apply(list).to_dict()
        return [float(any(t < e <= t + timedelta(days=365) for e in ev.get(c, [])))
                for c, t in zip(rows["cik"], rows["knowledge_time"])]

    base["restate_12m"] = within(base, formal)
    base["item402_12m"] = within(base, only402)
    base["year"] = base["knowledge_time"].dt.year.astype(str)
    x = sm.add_constant(pd.concat([base[["quiet_down"]], pd.get_dummies(base["year"], drop_first=True, dtype=float)], axis=1))
    fit = sm.OLS(base["restate_12m"], x).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(base["cik"])[0]})
    q = base[base["quiet_down"] == 1]
    return {"coef": float(fit.params["quiet_down"]), "t": float(fit.tvalues["quiet_down"]),
            "n_filings": len(base), "n_quiet": len(q), "firms": int(base["cik"].nunique()),
            "restate_rate_quiet": float(q["restate_12m"].mean()) if len(q) else float("nan"),
            "restate_rate_other": float(base.loc[base["quiet_down"] == 0, "restate_12m"].mean()),
            "item402_rate_quiet": float(q["item402_12m"].mean()) if len(q) else float("nan"),
            "item402_rate_other": float(base.loc[base["quiet_down"] == 0, "item402_12m"].mean())}


def part_b(filings: pd.DataFrame) -> dict:
    from asof.events import car
    from asof.factors import ff5_umd_daily
    from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
    from asof.prices import YahooPrices
    from asof.timeutil import first_tradable_close

    uni = pd.read_parquet(DATA_DIR / "h0_universe.parquet")
    f = filings[filings["cik"].isin(set(uni["cik"]))]
    quiet = detect(set(uni["cik"]), f)
    lo = pd.Timestamp(DEV_START, tz="UTC")
    hi = pd.Timestamp(DEV_END, tz="UTC") + pd.Timedelta(hours=23, minutes=59)
    quiet = quiet[pd.to_datetime(quiet["knowledge_time"], utc=True).between(lo, hi)].merge(uni[["cik", "ticker"]], on="cik")
    factors = ff5_umd_daily()
    factors = factors[factors.index <= DEV_RETURN_CUTOFF]
    days = list(factors.index)
    y = YahooPrices()
    cars = []
    for r in quiet.itertuples():
        d = y.daily(r.ticker, end=DEV_RETURN_CUTOFF)
        if d.empty:
            continue
        ret = d.set_index("date")["adjclose"].pct_change().dropna()
        day = first_tradable_close(pd.Timestamp(r.knowledge_time).to_pydatetime(), days)
        if day:
            cars.append({"car": car(ret, factors, day, horizon=60),
                         "month": pd.Timestamp(r.knowledge_time).strftime("%Y-%m")})
    c = pd.DataFrame(cars).dropna()
    if len(c) < 10:
        return {"n": len(c), "note": "too few events for inference"}
    fit = sm.OLS(c["car"], np.ones(len(c))).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(c["month"])[0]})
    return {"mean_car": float(fit.params.iloc[0]), "t": float(fit.tvalues.iloc[0]), "n": len(c),
            "clusters": int(c["month"].nunique())}


def main() -> None:
    filings = pd.read_parquet(FIL)
    results = {}
    common = [FIL, RAW_DIR / "bulk" / "companyfacts.zip"]
    for name, fn, inputs in (
        ("H6a_restatement_12m", part_a, [*common, DATA_DIR / "h4_sample.parquet"]),
        ("H6b_car_60", part_b, [*common, DATA_DIR / "h0_universe.parquet",
                              DATA_DIR / "h0_market_inputs.json"]),
    ):
        with ledger.development_trial("H6", {"test": name}, inputs=inputs) as metrics:
            if name == "H6b_car_60":
                metrics["scientific_status"] = "invalid_f2_current_ticker_survivorship"
            m = fn(filings)
            metrics.update(m)
        results[name] = m
    out = {"note": "Development only. H6a threshold |t| >= 3 (new). H6b is INVALID under F2; "
                   "its rerun is a pipeline diagnostic, not a replication or hypothesis result.",
           "results": results}
    (PROJECT_ROOT / "results" / "h6_development.json").write_text(json.dumps(out, indent=2, default=float))
    json.dump(out, sys.stdout, indent=2, default=float)


if __name__ == "__main__":
    main()
