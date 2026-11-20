"""F8 (H0 only): is single-thread H0 exactly reproducible, and do BLAS threads explain F8?

Approved scope: ``f8_rerun=h0_only``; H4 stays on hold. Runs the unchanged registered H0
development configurations in fresh child processes and never overwrites the recorded
``results/returns_h0_development.json``. Every child logs its trials to the append-only ledger
(identical config hashes, so ``n_trials`` does not grow).

Declared before execution:
- single_A and single_B use one numerical thread; default_threads unsets the caps.
- Comparison scope is ``results`` and ``coverage`` with exact float equality (NaN == NaN).
- ``single_thread_reproducible`` iff single_A == single_B == the committed Batch B file.
- ``baseline_reproduced_with_default_threads`` iff default_threads equals the original
  multi-thread baseline revision; informational because the baseline's host/thread count
  was not recorded.
- The mechanism diagnostic compares neutralized formation residuals and within-month
  ranks between one thread and default threads; it reads no returns.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from development_diagnostics import BASELINE, baseline, differences

from asof.config import DATA_DIR, PROJECT_ROOT
from asof.ledger import LEDGER_PATH
from asof.runtime import frozen_receipt, write_receipt

RECEIPT = PROJECT_ROOT / "results" / "f8_h0_reproducibility.json"
WORK = DATA_DIR / "f8_h0_reproducibility"
CAPS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
RUNS = (("single_A", "1"), ("single_B", "1"), ("default_threads", None))
SOURCES = ("scripts/f8_h0_reproducibility.py", "scripts/h0_backtest.py",
           "scripts/development_diagnostics.py", "src/asof/events.py", "src/asof/backtest.py")


def environment(threads: str | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in CAPS}
    if threads is not None:
        env.update(dict.fromkeys(CAPS, threads))
    return env


def child(args: list[str], threads: str | None) -> float:
    started = time.perf_counter()
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, env=environment(threads), check=True,
                   stdout=subprocess.DEVNULL)
    return time.perf_counter() - started


def residuals(output: Path) -> None:
    """Child mode: the exact formation neutralization used by h0_backtest.main, no returns."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import h0_backtest as h0

    from asof.backtest import Config, formation_snapshots
    from asof.factors import nyse_me_breakpoints

    _, sig, shares, ent, ma, panel, _ = h0.load_inputs()
    bp = nyse_me_breakpoints()
    frames = []
    for key, frame in (("10-K", sig[sig["form"] == "10-K"]), ("latest", sig)):
        snapshots = h0.neutralize_formations(formation_snapshots(frame, shares, panel), ent, ma, bp, Config())
        for month, group in snapshots.items():
            frames.append(pd.DataFrame({"key": key, "month": str(month), "cik": group["cik"].to_numpy(),
                                        "residual": group["neg_change_n"].to_numpy()}))
    pd.concat(frames, ignore_index=True).to_parquet(output)


def residual_comparison(one: pd.DataFrame, many: pd.DataFrame) -> dict:
    keys = ["key", "month", "cik"]
    if not one[keys].equals(many[keys]):
        raise ValueError("residual dumps are not aligned row by row")
    a, b = one["residual"].to_numpy(), many["residual"].to_numpy()
    both = ~np.isnan(a) & ~np.isnan(b)
    if (np.isnan(a) != np.isnan(b)).any():
        raise ValueError("thread setting changed residual availability")
    diff = np.abs(a[both] - b[both])
    by_month = []
    for (key, month), index in one[both].groupby(["key", "month"]).groups.items():
        x = one.loc[index, "residual"].rank(method="average").to_numpy()
        y = many.loc[index, "residual"].rank(method="average").to_numpy()
        values = np.sort(one.loc[index, "residual"].to_numpy())
        scale = float(np.std(values)) or 1.0
        by_month.append({"key": key, "month": month, "n": len(index),
                         "rows_with_rank_change": int((x != y).sum()),
                         "adjacent_gaps_below_1e-9_sd": int((np.diff(values) < 1e-9 * scale).sum())})
    changed = [m for m in by_month if m["rows_with_rank_change"]]
    return {"rows": len(one), "non_missing": int(both.sum()),
            "bitwise_different_rows": int((a[both] != b[both]).sum()),
            "max_abs_difference": float(diff.max()) if diff.size else 0.0,
            "months": len(by_month), "months_with_rank_change": len(changed),
            "rank_changed_rows": sum(m["rows_with_rank_change"] for m in by_month),
            "near_tie_gaps_total": sum(m["adjacent_gaps_below_1e-9_sd"] for m in by_month),
            "months_with_rank_change_detail": changed}


def blas() -> dict:
    config = np.show_config(mode="dicts")["Build Dependencies"]["blas"]
    return {k: config.get(k) for k in ("name", "version", "openblas configuration")}


def run() -> None:
    if RECEIPT.exists() or WORK.exists():
        raise RuntimeError("F8 reproducibility already executed; preserve it")
    freeze = frozen_receipt(PROJECT_ROOT, SOURCES)
    WORK.mkdir(parents=True)
    ledger_before = len(LEDGER_PATH.read_bytes().splitlines())
    outputs, timings = {}, {}
    for label, threads in RUNS:
        path = WORK / f"{label}.json"
        timings[label] = child(["scripts/h0_backtest.py", "--output", str(path)], threads)
        outputs[label] = json.loads(path.read_text())
    dumps = {}
    for label, threads in (("one_thread", "1"), ("default_threads", None)):
        path = WORK / f"residuals_{label}.parquet"
        timings[f"residuals_{label}"] = child(
            ["scripts/f8_h0_reproducibility.py", "residuals", str(path)], threads)
        dumps[label] = pd.read_parquet(path)
    batch_b = json.loads(subprocess.run(
        ["git", "show", "HEAD:results/returns_h0_development.json"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True).stdout)
    original = baseline("returns_h0_development.json")

    def compare(old: dict, new: dict) -> list[dict]:
        return differences(old["results"], new["results"]) + differences(old["coverage"], new["coverage"])

    pairs = {
        "single_A_vs_single_B": compare(outputs["single_A"], outputs["single_B"]),
        "single_A_vs_committed_batch_B": compare(batch_b, outputs["single_A"]),
        "default_threads_vs_original_baseline": compare(original, outputs["default_threads"]),
        "default_threads_vs_single_A": compare(outputs["single_A"], outputs["default_threads"]),
        "single_A_vs_original_baseline": compare(original, outputs["single_A"]),
    }
    reproducible = not pairs["single_A_vs_single_B"] and not pairs["single_A_vs_committed_batch_B"]
    try:
        mechanism = residual_comparison(dumps["one_thread"], dumps["default_threads"])
    except ValueError as exc:
        mechanism = {"error": str(exc)}
    ledger_after = len(LEDGER_PATH.read_bytes().splitlines())
    write_receipt(RECEIPT, {
        "scope": "F8 H0-only reproducibility diagnostic (approved f8_rerun=h0_only); H4 held",
        **freeze, "declared_rule": __doc__.split("Declared before execution:")[1].strip(),
        "baseline_revision": BASELINE, "host_logical_CPUs": os.cpu_count(), "BLAS": blas(),
        "runs": {label: {"thread_caps": threads or "unset (library default)",
                         "seconds": round(timings[label], 1)} for label, threads in RUNS},
        "differences": pairs,
        "difference_counts": {k: len(v) for k, v in pairs.items()},
        "single_thread_reproducible": reproducible,
        "baseline_reproduced_with_default_threads": not pairs["default_threads_vs_original_baseline"],
        "thread_sensitivity_observed": bool(pairs["default_threads_vs_single_A"]),
        "residual_mechanism_one_vs_default_threads": mechanism,
        "ledger_rows_appended": ledger_after - ledger_before,
        "limits": "Same host and inputs; the original baseline's host and thread count were not "
                  "recorded. Exact reproduction of a summary is numerical provenance, not "
                  "scientific acceptance. No recorded results file, H4 output or holdout data "
                  "was touched.",
    })
    print(json.dumps({"single_thread_reproducible": reproducible,
                      "difference_counts": {k: len(v) for k, v in pairs.items()}}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("run", "residuals"))
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    if args.phase == "residuals":
        residuals(args.output)
    else:
        run()
