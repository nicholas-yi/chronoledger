"""H0 (Lazy Prices) on the development period only. Every configuration is logged to the ledger.

Development: signals known 2023-01-01..2024-06-30; returns through 2024-07-31. With ~18 monthly
observations this run validates the pipeline and gives a point estimate; it is not inferential.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from asof import ledger
from asof.backtest import Config, form_portfolios, long_short, monthly_panel
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.factors import ff5_umd_monthly, nyse_me_breakpoints
from asof.inference import nw_alpha
from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
from asof.prices import YahooPrices

FACTORS = ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "UMD"]


def load_inputs():
    uni = pd.read_parquet(DATA_DIR / "h0_universe.parquet")
    sig = pd.read_parquet(DATA_DIR / "h0_signals.parquet")
    sig["knowledge_time"] = pd.to_datetime(sig["knowledge_time"], utc=True)
    lo = datetime.combine(DEV_START, datetime.min.time(), tzinfo=timezone.utc)
    hi = datetime.combine(DEV_END, datetime.max.time(), tzinfo=timezone.utc)
    sig = sig[(sig["knowledge_time"] >= lo) & (sig["knowledge_time"] <= hi)]
    shares = pd.read_parquet(DATA_DIR / "h0_shares.parquet")
    shares["knowledge_time"] = pd.to_datetime(shares["knowledge_time"], utc=True)
    y = YahooPrices()
    frames = []
    for t in uni["ticker"]:
        try:
            d = y.daily(t, end=DEV_RETURN_CUTOFF)
        except Exception:
            continue
        if not d.empty:
            frames.append(d[d["date"] >= pd.Timestamp("2022-11-01").date()])
    daily = pd.concat(frames, ignore_index=True)
    panel = monthly_panel(daily).merge(uni[["cik", "ticker"]], on="ticker")
    return uni, sig, shares, panel


def run(cfg: Config, sig, shares, panel, bp) -> pd.DataFrame:
    months = pd.period_range(pd.Period(DEV_START, "M"), pd.Period(DEV_END, "M"), freq="M")
    rows, prev = [], None
    for m in months:
        pm = panel[panel["month"] == m]
        port = form_portfolios(m, sig, shares, pm, float(bp.loc[m, cfg.size_pct]), cfg)
        if port.empty:
            prev = None
            continue
        r = long_short(port, prev, cfg)
        r.update(formation=str(m), return_month=str(m + 1), n_firms=len(port))
        rows.append(r)
        prev = port
    return pd.DataFrame(rows)


def summarize(res: pd.DataFrame, factors: pd.DataFrame) -> dict:
    s = res.set_index(pd.PeriodIndex(res["return_month"], freq="M"))["ls_net"]
    f = factors.loc[s.index.min():s.index.max(), FACTORS]
    a = nw_alpha(s, f, lags=6)
    return {
        "months": int(len(s)), "mean_net": float(s.mean()), "mean_gross": float(res["ls_gross"].mean()),
        "sd_net": float(s.std(ddof=1)), "t_mean_naive": float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))),
        "alpha_ff5_umd": a.alpha, "alpha_t_nw6": a.t_stat, "betas": a.betas,
        "avg_firms": float(res["n_firms"].mean()), "avg_cost_per_month": float((res["long_cost"] + res["short_cost"]).mean()),
    }


def main() -> None:
    uni, sig, shares, panel = load_inputs()
    factors = ff5_umd_monthly()
    factors = factors.loc[: pd.Period(DEV_RETURN_CUTOFF, "M")]
    bp = nyse_me_breakpoints()
    configs = [Config(), Config(weighting="equal"), Config(signal="cos_1a"), Config(signal="jac_full")]
    out = {"note": "Development period only (~18 months). Point estimates; not inferential.",
           "price_coverage": {"universe": int(len(uni)), "with_prices": int(panel["ticker"].nunique())},
           "results": []}
    for cfg in configs:
        res = run(cfg, sig, shares, panel, bp)
        summary = summarize(res, factors) if len(res) >= 8 else {"months": int(len(res))}
        h = ledger.log_trial("H0", asdict(cfg), "development", summary)
        out["results"].append({"config": asdict(cfg), "config_hash": h, **summary})
    out["n_trials_logged_H0"] = ledger.n_trials("H0")
    path = PROJECT_ROOT / "results" / "returns_h0_development.json"
    path.write_text(json.dumps(out, indent=2, default=float))
    json.dump(out, sys.stdout, indent=2, default=float)


if __name__ == "__main__":
    main()
