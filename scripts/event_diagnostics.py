"""Diagnostics for the event-study pipeline: unconditional mean CAR and a random-date placebo.

If random event dates in the same universe produce positive CARs, the universe (selected on
survival to today) is biased, and event-study signs cannot be trusted without a survivorship fix.
"""

from __future__ import annotations

import json
import random
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

from asof.config import DATA_DIR, PROJECT_ROOT
from asof.events import car
from asof.factors import ff5_umd_daily
from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
from asof.prices import YahooPrices, daily_returns


def clustered_mean(c: pd.DataFrame) -> dict:
    fit = sm.OLS(c["car"], np.ones(len(c))).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(c["month"])[0]})
    return {"mean_car": float(fit.params.iloc[0]), "t": float(fit.tvalues.iloc[0]), "n": len(c)}


def main(n_placebo: int = 4000, seed: int = 7) -> None:
    uni = pd.read_parquet(DATA_DIR / "h0_universe.parquet")
    factors = ff5_umd_daily()
    factors = factors[factors.index <= DEV_RETURN_CUTOFF]
    days = [d for d in factors.index if DEV_START <= d <= DEV_END]
    y = YahooPrices()
    rets = {}
    for t in uni["ticker"]:
        d = y.daily(t, end=DEV_RETURN_CUTOFF)
        if not d.empty:
            rets[t] = daily_returns(d.set_index("date")).dropna()
    rng = random.Random(seed)
    tickers = sorted(rets)
    out = {}
    for horizon in (20, 60):
        rows = []
        for _ in range(n_placebo):
            t, day = rng.choice(tickers), rng.choice(days)
            rows.append({"car": car(rets[t], factors, day, horizon=horizon), "month": str(day)[:7]})
        c = pd.DataFrame(rows).dropna()
        out[f"placebo_random_dates_car{horizon}"] = clustered_mean(c)
    # Raw (not abnormal) buy-and-hold check: mean daily return of surviving universe vs market.
    allr = pd.concat(rets.values())
    allr = allr[(allr.index >= DEV_START) & (allr.index <= DEV_RETURN_CUTOFF)]
    mkt = (factors["Mkt_RF"] + factors["RF"]).loc[DEV_START:DEV_RETURN_CUTOFF]
    out["mean_daily_return_universe"] = float(allr.mean())
    out["mean_daily_return_market"] = float(mkt.mean())
    path = PROJECT_ROOT / "results" / "returns_event_diagnostics.json"
    path.write_text(json.dumps(out, indent=2))
    json.dump(out, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
