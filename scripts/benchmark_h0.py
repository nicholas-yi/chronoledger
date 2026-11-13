"""Verify optimized H0 formation, costs, and neutralization against a pinned legacy revision."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter
from types import ModuleType

import h0_backtest as current
import numpy as np
import pandas as pd

from asof import ledger
from asof.backtest import Config, form_portfolios, formation_snapshots, long_short, monthly_panel
from asof.config import PROJECT_ROOT
from asof.periods import DEV_END, DEV_START
from asof.prices import YahooPrices

REFERENCE = "5298d9d9f666c52a3ec2b879c1b85f88f258f15e"


def load_reference(revision: str, path: str) -> ModuleType:
    source = subprocess.run(
        ["git", "show", f"{revision}:{path}"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout
    name = f"_reference_{Path(path).stem}"
    module = ModuleType(name)
    module.__file__ = str(PROJECT_ROOT / path)
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102 - pinned local Git source
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firms", type=int, default=100)
    parser.add_argument("--reference", default=REFERENCE)
    args = parser.parse_args()
    if args.firms < 1:
        parser.error("--firms must be positive")
    legacy = load_reference(args.reference, "scripts/h0_backtest.py")
    backtest = load_reference(args.reference, "src/asof/backtest.py")
    legacy.latest_as_of = backtest.latest_as_of
    uni, sig, shares, ent, ma, panel, _ = current.load_inputs()
    chosen = set(sorted(set(uni["cik"]) & set(sig["cik"]))[:args.firms])
    y = YahooPrices()
    daily = []
    for ticker in uni.loc[uni["cik"].isin(chosen), "ticker"]:
        prices = y.daily(ticker, end=current.DEV_RETURN_CUTOFF)
        if not prices.empty:
            daily.append(prices[prices["date"] >= pd.Timestamp("2022-11-01").date()])
    daily = pd.concat(daily, ignore_index=True)
    start = perf_counter()
    old_panel = backtest.monthly_panel(daily)
    old_panel_seconds = perf_counter() - start
    start = perf_counter()
    new_panel = monthly_panel(daily)
    new_panel_seconds = perf_counter() - start
    pd.testing.assert_frame_equal(new_panel, old_panel, rtol=1e-12, atol=1e-12)
    panel_comparison = {
        "rows": len(new_panel), "reference_seconds": old_panel_seconds,
        "optimized_seconds": new_panel_seconds,
    }
    sig, shares, ent, ma, panel = [
        d[d["cik"].isin(chosen)].copy() for d in (sig, shares, ent, ma, panel)]
    started = perf_counter()
    expected = legacy.add_neutral(sig, shares, ent, ma, panel)
    actual = current.add_neutral(sig, shares, ent, ma, panel)
    pd.testing.assert_frame_equal(actual, expected, rtol=1e-10, atol=1e-12)
    actual["neg_change_n"] = -actual["change_n"]
    expected["neg_change_n"] = -expected["change_n"]
    neutral_seconds = perf_counter() - started
    breakpoints = current.nyse_me_breakpoints()
    current.fingerprint_market_inputs()
    comparison_panel = panel.dropna(subset=["ret_next"])
    months = pd.period_range(pd.Period(DEV_START, "M"), pd.Period(DEV_END, "M"), freq="M")
    summaries = []
    for name, tenk, column in (
        ("v1_10K_raw", True, "cos_full"),
        ("v2_latest_raw", False, "cos_full"),
        ("v2_latest_neutral", False, "neg_change_n"),
        ("v2_10K_neutral", True, "neg_change_n"),
    ):
        cfg = replace(Config(), signal=column)
        old_sig = expected[expected["form"] == "10-K"] if tenk else expected
        new_sig = actual[actual["form"] == "10-K"] if tenk else actual
        snapshots = formation_snapshots(new_sig, shares, comparison_panel, cfg.max_signal_age_days)
        previous_old = previous_new = None
        compared = rows = 0
        passed = False
        old_seconds = new_seconds = 0.0
        config = {"variant": name, **asdict(cfg), "purpose": "optimization_equivalence",
                  "sample_firms": len(chosen), "reference": args.reference}
        try:
            for month in months:
                pm = comparison_panel[comparison_panel["month"] == month]
                start = perf_counter()
                old = backtest.form_portfolios(
                    month, old_sig, shares, pm, float(breakpoints.loc[month, cfg.size_pct]), cfg)
                old_return = backtest.long_short(old, previous_old, cfg) if not old.empty else None
                old_seconds += perf_counter() - start
                start = perf_counter()
                snapshot = snapshots.get(
                    month, pd.DataFrame(columns=[*pm.columns, column, "shares"]))
                new = form_portfolios(
                    month, new_sig, shares, pm, float(breakpoints.loc[month, cfg.size_pct]), cfg,
                    snapshot=snapshot)
                new_return = long_short(new, previous_new, cfg) if not new.empty else None
                new_seconds += perf_counter() - start
                pd.testing.assert_frame_equal(
                    new.reset_index(drop=True), old.reset_index(drop=True),
                    check_dtype=False, rtol=1e-10, atol=1e-12)
                if old_return is not None:
                    assert old_return.keys() <= new_return.keys()
                    np.testing.assert_allclose(
                        list(old_return.values()), [new_return[k] for k in old_return],
                        rtol=1e-10, atol=1e-12)
                    assert new_return["long_missing"] == new_return["short_missing"] == 0
                    compared += 1
                    rows += len(new)
                previous_old = None if old.empty else old
                previous_new = None if new.empty else new
            assert compared, f"{name}: no nonempty portfolios to compare"
            passed = True
        finally:
            ledger.log_trial(
                "H0" if "raw" in name else "H1n", config, "development",
                {"equivalence_passed": passed, "months_compared": compared, "rows_compared": rows,
                 "reference_seconds": old_seconds, "optimized_seconds": new_seconds},
                inputs=current.INPUTS,
            )
        summaries.append({"variant": name, "months": compared, "rows": rows,
                          "reference_seconds": old_seconds, "optimized_seconds": new_seconds})
    result = {
        "note": "Numerical equivalence on a development subsample, not a hypothesis result. "
                "Checks formation rows, signals, quintiles, weights, gross returns and turnover costs. "
                "Uses complete-return rows only for this engineering comparison; production formation "
                "must not select on future return availability (D8). Legacy cohort residuals are "
                "compared separately; production neutralization uses formation-time cross-sections. "
                "This is not the full four-variant wall-clock benchmark.",
        "reference": args.reference, "sample_firms": len(chosen),
        "monthly_panel_comparison": panel_comparison,
        "neutralization_comparison_seconds": neutral_seconds, "variants": summaries,
        "lineage": ledger.lineage(current.INPUTS),
    }
    output = PROJECT_ROOT / "results" / "h0_optimization_equivalence.json"
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
