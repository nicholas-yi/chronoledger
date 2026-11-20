"""D15 (H4 only): a development-only extract, then the F8 H4 numerical-thread check.

Approved ``h4=dev_extract_repro``. The H4 file-reading stages stay hard held.

Declared before execution:
- extract: one process reads ``h4_pairs`` and ``h4_outcomes`` in full. That read is the
  recorded exposure, including any H4 holdout-window rows. It writes pairs accepted
  2012-2018, and outcome rows dated no later than the last development report date plus
  430 days (the longest lag the panel uses). It writes nothing unless the panel built from the
  re-read extract equals the panel built from the full files exactly. Only aggregate row
  counts by year are recorded; no values.
- check: three child processes run the registered H4 regressions on the extract: single_A
  and single_B with one numerical thread, and default_threads. ``single_thread_reproducible``
  iff single_A == single_B == the committed Batch B ``h4_development.json`` (exact floats).
  default_threads versus the original multi-thread baseline is reported, not gating.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import h4_fundamentals as h4
import pandas as pd
from development_diagnostics import BASELINE, baseline, differences

from asof.config import DATA_DIR, PROJECT_ROOT
from asof.ledger import LEDGER_PATH, file_sha256
from asof.runtime import frozen_receipt, write_receipt

EXTRACT = DATA_DIR / "h4_dev"
PAIRS, OUTCOMES = EXTRACT / "pairs.parquet", EXTRACT / "outcomes.parquet"
EXTRACT_RECEIPT = PROJECT_ROOT / "results" / "h4_dev_extract.json"
CHECK_RECEIPT = PROJECT_ROOT / "results" / "f8_h4_reproducibility.json"
HOLDOUT_START = pd.Timestamp("2022-01-01")
MAX_LAG_DAYS = 430
CAPS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
RUNS = (("single_A", "1"), ("single_B", "1"), ("default_threads", None))
SOURCES = ("scripts/h4_dev_reproducibility.py", "scripts/h4_fundamentals.py",
           "scripts/development_diagnostics.py", "src/asof/events.py")


def extract_frames(pairs: pd.DataFrame, outcomes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Development pairs and the outcome rows the development panel can reach."""
    known = pd.to_datetime(pairs["knowledge_time"], utc=True)
    dev_pairs = pairs[known.between(*h4.DEV)]
    used = outcomes.merge(dev_pairs[["cik", "accession"]], on=["cik", "accession"])
    cutoff = pd.to_datetime(used["report_date"]).max() + pd.Timedelta(days=MAX_LAG_DAYS)
    return dev_pairs, outcomes[pd.to_datetime(outcomes["report_date"]) <= cutoff]


def year_counts(values: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in sorted(Counter(pd.to_datetime(values).dt.year).items())}


def extract() -> None:
    if EXTRACT_RECEIPT.exists() or EXTRACT.exists():
        raise RuntimeError("D15 extract already made; preserve it")
    freeze = frozen_receipt(PROJECT_ROOT, SOURCES)
    inputs = {str(p.relative_to(PROJECT_ROOT)): file_sha256(p) for p in (h4.PAIRS, h4.OUT, h4.ENT)}
    pairs, outcomes, ent = (pd.read_parquet(p) for p in (h4.PAIRS, h4.OUT, h4.ENT))
    dev_pairs, dev_outcomes = extract_frames(pairs, outcomes)
    EXTRACT.mkdir(parents=True)
    dev_pairs.to_parquet(PAIRS)
    dev_outcomes.to_parquet(OUTCOMES)
    full = h4.panel_from_frames(pairs, outcomes, ent)
    reread = h4.panel_from_frames(pd.read_parquet(PAIRS), pd.read_parquet(OUTCOMES), ent)
    try:
        pd.testing.assert_frame_equal(full, reread, check_exact=True)
    except AssertionError:
        for path in (PAIRS, OUTCOMES):
            path.unlink()
        EXTRACT.rmdir()
        raise
    outcome_dates = pd.to_datetime(outcomes["report_date"])
    write_receipt(EXTRACT_RECEIPT, {
        "scope": "D15 development-only H4 extract (approved h4=dev_extract_repro)", **freeze,
        "declared_rule": __doc__.split("Declared before execution:")[1].strip(),
        "inputs_read_in_full_SHA256": inputs,
        "exposure": {
            "pairs_rows_decoded_by_knowledge_year": year_counts(pd.to_datetime(pairs["knowledge_time"], utc=True)
                                                                .dt.tz_convert(None)),
            "outcome_rows_decoded_by_report_year": year_counts(outcomes["report_date"]),
            "outcome_rows_decoded_in_H4_holdout_window_2022_plus": int((outcome_dates >= HOLDOUT_START).sum()),
            "values_written_or_reported_from_2022_plus": 0,
            "note": "Rows were decoded in memory by this one process; only these counts leave it."},
        "extract": {"pairs_rows": len(dev_pairs), "outcome_rows": len(dev_outcomes),
                    "outcome_report_date_max": str(pd.to_datetime(dev_outcomes["report_date"]).max().date()),
                    "SHA256": {str(p.relative_to(PROJECT_ROOT)): file_sha256(p) for p in (PAIRS, OUTCOMES)}},
        "equivalence": {"panel_rows": len(full), "panel_from_extract_equals_full_panel_exactly": True},
    })
    print(EXTRACT_RECEIPT.read_text())


def child(output: Path) -> None:
    receipt = json.loads(EXTRACT_RECEIPT.read_bytes())
    for path, digest in receipt["extract"]["SHA256"].items():
        if file_sha256(PROJECT_ROOT / path) != digest:
            raise ValueError(f"extract changed: {path}")
    panel = h4.panel_from_frames(pd.read_parquet(PAIRS), pd.read_parquet(OUTCOMES), pd.read_parquet(h4.ENT))
    output.write_text(json.dumps({"results": h4.results_from_panel(panel, [PAIRS, OUTCOMES, h4.ENT])}, indent=2))


def environment(threads: str | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in CAPS}
    if threads is not None:
        env.update(dict.fromkeys(CAPS, threads))
    return env


def check() -> None:
    if CHECK_RECEIPT.exists():
        raise RuntimeError("F8 H4 check already executed; preserve it")
    if not EXTRACT_RECEIPT.exists():
        raise RuntimeError("make and commit the D15 extract first")
    freeze = frozen_receipt(PROJECT_ROOT, (*SOURCES, "results/h4_dev_extract.json"))
    ledger_before = len(LEDGER_PATH.read_bytes().splitlines())
    work = EXTRACT / "runs"
    work.mkdir()
    outputs, seconds = {}, {}
    for label, threads in RUNS:
        path = work / f"{label}.json"
        started = time.perf_counter()
        subprocess.run([sys.executable, "scripts/h4_dev_reproducibility.py", "child", str(path)],
                       cwd=PROJECT_ROOT, env=environment(threads), check=True, stdout=subprocess.DEVNULL)
        seconds[label] = round(time.perf_counter() - started, 1)
        outputs[label] = json.loads(path.read_text())["results"]
    batch_b = json.loads(subprocess.run(["git", "show", "HEAD:results/h4_development.json"], cwd=PROJECT_ROOT,
                                        check=True, capture_output=True, text=True).stdout)["results"]
    original = baseline("h4_development.json")["results"]
    pairs = {
        "single_A_vs_single_B": differences(outputs["single_A"], outputs["single_B"]),
        "single_A_vs_committed_batch_B": differences(batch_b, outputs["single_A"]),
        "default_threads_vs_original_baseline": differences(original, outputs["default_threads"]),
        "default_threads_vs_single_A": differences(outputs["single_A"], outputs["default_threads"]),
        "single_A_vs_original_baseline": differences(original, outputs["single_A"]),
    }
    reproducible = not pairs["single_A_vs_single_B"] and not pairs["single_A_vs_committed_batch_B"]
    write_receipt(CHECK_RECEIPT, {
        "scope": "F8 H4 reproducibility on the D15 development-only extract; H4 stages stay held",
        **freeze, "baseline_revision": BASELINE, "host_logical_CPUs": os.cpu_count(),
        "runs": {label: {"thread_caps": threads or "unset (library default)", "seconds": seconds[label]}
                 for label, threads in RUNS},
        "differences": pairs, "difference_counts": {k: len(v) for k, v in pairs.items()},
        "max_abs_difference": {k: max((abs(d["new"] - d["old"]) for d in v if "new" in d), default=0.0)
                               for k, v in pairs.items()},
        "single_thread_reproducible": reproducible,
        "baseline_reproduced_with_default_threads": not pairs["default_threads_vs_original_baseline"],
        "ledger_rows_appended": len(LEDGER_PATH.read_bytes().splitlines()) - ledger_before,
        "limits": "Same host and extract; the original baseline's host and thread count were not "
                  "recorded. Numerical provenance only, not scientific acceptance. No H4 stage, "
                  "holdout evaluation or recorded result file was run or rewritten.",
    })
    print(json.dumps({"single_thread_reproducible": reproducible,
                      "difference_counts": {k: len(v) for k, v in pairs.items()}}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("extract", "check", "child"))
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    {"extract": extract, "check": check}.get(args.phase, lambda: child(args.output))()
