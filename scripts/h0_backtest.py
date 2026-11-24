"""H0/H1-family tests on the development period (pre-registration v1 + v2). All trials are logged.

Co-primary (v2): monthly long-short portfolio and filing-level event panel (CAR +1..+60).
Corroboration: monthly rank IC. Variants: 10-K only (v1) vs latest 10-K/10-Q (v2); raw vs
neutralized (industry SIC2, log market cap, 8-K Item 2.01 in prior 12 months).
Development: signals known 2023-01-01..2024-06-30; returns through 2024-07-31.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from asof import ledger
from asof.backtest import (
    Config,
    form_portfolios,
    formation_snapshots,
    long_short,
)
from asof.config import DATA_DIR, PROJECT_ROOT, RAW_DIR
from asof.events import CarEngine, event_panel, rank_ic
from asof.factors import ff5_umd_daily, ff5_umd_monthly, nyse_me_breakpoints
from asof.h0 import INPUTS, load_inputs, neutralize_formations
from asof.inference import nw_alpha
from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
from asof.timeutil import first_tradable_close

FACTORS = ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "UMD"]


def fingerprint_market_inputs() -> None:
    files = sorted((RAW_DIR / "yahoo").glob(f"*_to{DEV_RETURN_CUTOFF:%Y%m%d}_v2.json.gz"))
    files += sorted((RAW_DIR / "french").glob("*.zip"))
    manifest = {
        "note": "Current local guarded caches, not the historical handoff inputs. "
                "Only fingerprints are referenced by the public trial ledger; raw data stays local.",
        "return_cutoff": DEV_RETURN_CUTOFF.isoformat(),
        "files": {str(p.relative_to(DATA_DIR)): ledger.file_sha256(p) for p in files},
    }
    (DATA_DIR / "h0_market_inputs.json").write_text(json.dumps(manifest, indent=2))


def monthly_test(cfg: Config, sig, shares, panel, bp, factors, snapshots=None, *,
                 series_out: list[dict[str, str | float]] | None = None) -> dict:
    months = pd.period_range(pd.Period(DEV_START, "M"), pd.Period(DEV_END, "M"), freq="M")
    rows, prev, ics = [], None, []
    panels = dict(list(panel.groupby("month")))
    for m in months:
        pm = panels.get(m, panel.iloc[:0])
        snapshot = snapshots.get(m, pd.DataFrame(columns=[*pm.columns, cfg.signal, "shares"])) if snapshots is not None else None
        port = form_portfolios(m, sig, shares, pm, float(bp.loc[m, cfg.size_pct]), cfg,
                               snapshot=snapshot)
        if port.empty:
            prev = None
            continue
        r = long_short(port, prev, cfg)
        r.update(return_month=str(m + 1), n_firms=len(port))
        rows.append(r)
        if series_out is not None:
            series_out.append({"return_month": str(m + 1), "ls_net": r["ls_net"],
                               "ls_gross": r["ls_gross"]})
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
            "missing_long_returns": int(res["long_missing"].sum()),
            "missing_short_returns": int(res["short_missing"].sum()),
            "missing_return_assumption": cfg.missing_return,
            "mean_ic": float(ic.mean()), "ic_t": float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic)))) if len(ic) > 2 else float("nan")}


def event_test(sig: pd.DataFrame, signal: str, daily_ret, engine: CarEngine, uni,
               car_cache: dict[tuple[str, date], float] | None = None) -> dict:
    s = sig.merge(uni[["cik", "ticker"]], on="cik").dropna(subset=[signal])
    days = engine.days
    cars = []
    cache = {} if car_cache is None else car_cache
    for r in s.itertuples():
        if r.ticker not in daily_ret:
            continue
        day = first_tradable_close(r.knowledge_time.to_pydatetime(), days)
        if day is None:
            continue
        key = (r.ticker, day)
        if key not in cache:
            cache[key] = engine.car(r.ticker, daily_ret[r.ticker], day, horizon=60)
        cars.append({"car": cache[key], "x": getattr(r, signal),
                     "month": r.knowledge_time.strftime("%Y-%m")})
    c = pd.DataFrame(cars).dropna()
    if len(c) < 30:
        return {"n_events": len(c)}
    p = event_panel(c, "car", "x", "month")
    return {"coef": p.coef, "t": p.t_stat, "n_events": p.n_events, "clusters": p.n_clusters}


def main(output: Path | None = None, signals: Path | None = None) -> None:
    started = perf_counter()
    signals = signals or DATA_DIR / "h0_signals.parquet"
    inputs = [signals if p.name == "h0_signals.parquet" else p for p in INPUTS]
    uni, sig, shares, ent, ma, panel, daily_ret, splits = load_inputs(signals)
    factors = ff5_umd_monthly().loc[: pd.Period(DEV_RETURN_CUTOFF, "M")]
    factors_d = ff5_umd_daily()
    factors_d = factors_d[factors_d.index <= DEV_RETURN_CUTOFF]
    engine = CarEngine(factors_d)
    bp = nyse_me_breakpoints()
    fingerprint_market_inputs()
    tenk = sig[sig["form"] == "10-K"]
    snapshots = {
        "10-K": formation_snapshots(tenk, shares, panel, splits=splits),
        "latest": formation_snapshots(sig, shares, panel, splits=splits),
    }
    snapshots = {
        key: neutralize_formations(value, ent, ma, bp, Config())
        for key, value in snapshots.items()
    }
    car_cache = {}
    results = []
    variants = {
        "v1_10K_raw": (tenk, "cos_full", True, "change"),
        "v2_latest_raw": (sig, "cos_full", True, "change"),
        "v2_latest_neutral": (sig, "neg_change_n", True, "change_n"),
        "v2_10K_neutral": (tenk, "neg_change_n", True, "change_n"),
    }
    for name, (s, col, long_high, ev_col) in variants.items():
        t0 = perf_counter()
        formation = snapshots["10-K" if name in ("v1_10K_raw", "v2_10K_neutral") else "latest"]
        sensitivity = {}
        return_series = {}
        e = {}
        for missing_return in (0.0, -0.3, -1.0):
            cfg = replace(Config(), signal=col, long_high=long_high, missing_return=missing_return)
            config = {"variant": name, **asdict(cfg)}
            with ledger.development_trial(
                "H0" if "raw" in name else "H1n", config, inputs=inputs,
            ) as metrics:
                metrics["phase"] = "monthly"
                series = []
                m = monthly_test(cfg, s, shares, panel, bp, factors, formation, series_out=series)
                metrics.update({f"m_{k}": v for k, v in m.items()})
                if abs(m.get("mean_net", 0.0)) > 0.05 or abs(m.get("mean_gross", 0.0)) > 0.05:
                    raise ValueError(f"{name}: implausible long-short mean; inspect failed ledger entry")
                if missing_return == 0.0:
                    metrics["phase"] = "event_panel"
                    e = event_test(s, ev_col, daily_ret, engine, uni, car_cache) if ev_col == "change" else {
                        "status": "not_evaluated",
                        "note": "Formation-month residuals are not event-time signals (D8). "
                                "An event-time neutralization contract must be fixed before this test.",
                    }
                    primary = m
                    primary_config = asdict(cfg)
                    primary_hash = ledger.config_hash(config)
                metrics.update({f"e_{k}": v for k, v in e.items()})
                metrics["phase"] = "finished"
            sensitivity[str(missing_return)] = m
            return_series[str(missing_return)] = series
        print(f"{name}: {perf_counter() - t0:.2f}s", file=sys.stderr, flush=True)
        entry = {"variant": name, "config": primary_config, "monthly": primary,
                 "monthly_missing_return_sensitivity": sensitivity,
                 "monthly_return_series": return_series,
                 "event_panel_change_on_car60": e, "config_hash": primary_hash}
        results.append(entry)
    out = {"note": "Development period only (~18 monthly obs). Raw change panels are descriptive; "
                   "neutralized event panels are not evaluated (D8). These cosine variants are not "
                   "the claim-level H1 signal. SIC uses current bulk metadata, not verified historical "
                   "classifications. No co-primary success claim; no holdout test executed.",
           "coverage": {"universe": len(uni), "with_prices": len(daily_ret),
                        "unusable_daily_returns_dropped": sum(
                            r.attrs["excluded_price_returns"] for r in daily_ret.values())},
           "results": results, "n_trials": {"H0": ledger.n_trials("H0"), "H1n": ledger.n_trials("H1n")},
           "elapsed_seconds": perf_counter() - started}
    (output or PROJECT_ROOT / "results" / "returns_h0_development.json").write_text(
        json.dumps(out, indent=2, default=float))
    json.dump(out, sys.stdout, indent=2, default=float)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write here instead of the recorded results file")
    parser.add_argument("--signals", type=Path, help="signal file (default: data/h0_signals.parquet)")
    args = parser.parse_args()
    main(args.output, args.signals)
