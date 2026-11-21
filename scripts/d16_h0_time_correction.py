"""D16: correct H0 knowledge times to their qualified acceptance times, then rerun H0.

Declared before execution (owner approval 2026-11-21, after the A4 revision-2 report):
- build: for every H0 signal whose accession has an A4 revision-2 ``qualified_UTC``, the
  knowledge time becomes that qualified time. Every other row keeps its stored time and must
  be one the frozen roster rule marked assignment-insensitive (no candidate offset moves its
  first close, month or eligibility). Refuse if any qualified time falls in [13:00, 16:00) ET
  on a verified NYSE early-close date in the signal window. Only ``knowledge_time`` changes.
- rerun: the unchanged H0 runner on the corrected file with one numerical thread (D14),
  writing a new results file; the recorded Batch B file is never overwritten. Every trial is
  logged. Compare against the committed Batch B results field by field (exact, reported,
  not gating) and refuse if the runner's 5% plausibility guard fails.
- diagnostics: the conditional current-vintage DSR and D4 status that F8 blocked
  (``development_diagnostics`` functions, unchanged), on the corrected series. Development
  only; PBO stays not_estimable below 32 aligned months.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from bisect import bisect_right
from collections import Counter
from datetime import date, datetime, time

import pandas as pd
import run_full_timestamps as base
from development_diagnostics import current_family_diagnostic, differences
from plan_full_timestamps import assignment_required

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.ledger import LEDGER_PATH, file_sha256
from asof.runtime import frozen_receipt, write_receipt
from asof.timeutil import ET
from asof.trial_manifest import registered_co_primary_decision

A4_R2 = PROJECT_ROOT / "results" / "timestamp_full_a4_report_r2.json"
QUALIFIED = DATA_DIR / "timestamp_full_a4" / "qualified_per_accession_r2.jsonl"
SIGNALS = DATA_DIR / "h0_signals.parquet"
CORRECTED = DATA_DIR / "h0_signals_d16.parquet"
BUILD_RECEIPT = PROJECT_ROOT / "results" / "d16_h0_time_correction.json"
RESULTS = PROJECT_ROOT / "results" / "returns_h0_development_d16.json"
COMPARISON = PROJECT_ROOT / "results" / "d16_h0_rerun_comparison.json"
DIAGNOSTICS = PROJECT_ROOT / "results" / "current_vintage_diagnostics_d16.json"
# NYSE 1:00 p.m. closes in the signal window, from NYSE Group's announced calendars:
# https://ir.theice.com/press/news-details/2019/NYSE-Group-Announces-2020-2021-and-2022-Holiday-and-Early-Closings-Calendar/default.aspx
# https://www.nasdaq.com/press-release/nyse-group-announces-2021-2022-and-2023-holiday-and-early-closings-calendar-2020-12
EARLY_CLOSES = (date(2022, 11, 25), date(2023, 7, 3), date(2023, 11, 24))
SOURCES = ("scripts/d16_h0_time_correction.py", "scripts/h0_backtest.py",
           "scripts/development_diagnostics.py", "scripts/plan_full_timestamps.py")
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def corrected_times(signals: pd.DataFrame, qualified: dict[str, str], universe: dict[str, dict]) -> pd.Series:
    """Qualified time where available; otherwise the stored time of an insensitive row."""
    unaudited = [a for a in signals["accession"] if a not in qualified]
    sensitive = [a for a in unaudited if assignment_required(universe[a])]
    if sensitive:
        raise ValueError(f"{len(sensitive)} assignment-sensitive signals lack a qualified time")
    for stamp in qualified.values():
        local = datetime.fromisoformat(stamp).astimezone(ET)
        if local.date() in EARLY_CLOSES and time(13) <= local.time() < time(16):
            raise ValueError("a qualified acceptance falls after a verified early close; needs a rule")
    replacement = pd.to_datetime(signals["accession"].map(qualified), utc=True)
    return replacement.fillna(signals["knowledge_time"]).astype(signals["knowledge_time"].dtype)


def build() -> None:
    if BUILD_RECEIPT.exists() or CORRECTED.exists():
        raise RuntimeError("D16 correction already built; preserve it")
    freeze = frozen_receipt(PROJECT_ROOT, SOURCES)
    report = json.loads(A4_R2.read_bytes())
    key = str(QUALIFIED.relative_to(PROJECT_ROOT))
    if file_sha256(QUALIFIED) != report["private_hash_manifest"][key]:
        raise ValueError("qualified table differs from the A4 revision-2 manifest")
    qualified = {r["accession"]: r["qualified_UTC"] for r in base.load_lines(QUALIFIED) if r["qualified_UTC"]}
    universe = {r["accession"]: r for r in base.load_lines(base.UNIVERSE)}
    signals = pd.read_parquet(SIGNALS)
    corrected = signals.assign(knowledge_time=corrected_times(signals, qualified, universe))
    if not corrected.drop(columns="knowledge_time").equals(signals.drop(columns="knowledge_time")):
        raise ValueError("only knowledge_time may change")
    closes = [datetime.fromisoformat(t) for t in json.loads(base.CALENDAR.read_bytes())["closes"]]
    direction = Counter()
    early = []
    for accession, old, new in zip(signals["accession"], signals["knowledge_time"], corrected["knowledge_time"],
                                   strict=True):
        a, b = bisect_right(closes, old.to_pydatetime()), bisect_right(closes, new.to_pydatetime())
        label = "unchanged_time" if old == new else (
            "same_first_close" if a == b else "was_earlier_lookahead" if a < b else "was_later_delay")
        direction[label] += 1
        if label == "was_earlier_lookahead":
            early.append(accession)
    corrected.to_parquet(CORRECTED)
    month = (signals["knowledge_time"].dt.tz_convert(None).dt.to_period("M")
             != corrected["knowledge_time"].dt.tz_convert(None).dt.to_period("M"))
    write_receipt(BUILD_RECEIPT, {
        "scope": "D16 H0 knowledge-time correction (owner approval 2026-11-21)", **freeze,
        "declared_rule": __doc__.split("Declared before execution")[1].strip(),
        "A4_r2_report_SHA256": file_sha256(A4_R2), "qualified_table_SHA256": file_sha256(QUALIFIED),
        "signals": {"rows": len(signals), "with_qualified_time": int(signals["accession"].isin(qualified).sum()),
                    "kept_stored_insensitive": int((~signals["accession"].isin(qualified)).sum())},
        "changes_versus_stored_on_registered_calendar": dict(direction),
        "UTC_month_changed": int(month.sum()),
        "corrected_lookahead_accessions": early,
        "verified_early_closes_checked": [d.isoformat() for d in EARLY_CLOSES],
        "input_SHA256": file_sha256(SIGNALS), "output_SHA256": file_sha256(CORRECTED),
    })
    print(BUILD_RECEIPT.read_text())


def rerun() -> None:
    if RESULTS.exists() or COMPARISON.exists():
        raise RuntimeError("D16 rerun already recorded; preserve it")
    freeze = frozen_receipt(PROJECT_ROOT, (*SOURCES, "results/d16_h0_time_correction.json"))
    if file_sha256(CORRECTED) != json.loads(BUILD_RECEIPT.read_bytes())["output_SHA256"]:
        raise ValueError("corrected signals changed since the build receipt")
    before = len(LEDGER_PATH.read_bytes().splitlines())
    env = {**os.environ, **dict.fromkeys(THREADS, "1")}
    subprocess.run([sys.executable, "scripts/h0_backtest.py", "--signals", str(CORRECTED), "--output", str(RESULTS)],
                   cwd=PROJECT_ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    new = json.loads(RESULTS.read_bytes())
    old = json.loads(subprocess.run(["git", "show", "HEAD:results/returns_h0_development.json"], cwd=PROJECT_ROOT,
                                    check=True, capture_output=True, text=True).stdout)
    changed = differences(old["results"], new["results"]) + differences(old["coverage"], new["coverage"])
    summary = {v["variant"]: {k: {"batch_B": o["monthly"].get(k), "D16": v["monthly"].get(k)}
                              for k in ("mean_net", "alpha", "alpha_t", "mean_ic", "ic_t", "months", "avg_firms")}
               | {"event_panel": {"batch_B": o["event_panel_change_on_car60"], "D16": v["event_panel_change_on_car60"]}}
               for o, v in zip(old["results"], new["results"], strict=True)}
    write_receipt(COMPARISON, {
        "scope": "D16 H0 development rerun on corrected knowledge times; one numerical thread (D14)", **freeze,
        "results_SHA256": file_sha256(RESULTS), "changed_fields": len(changed),
        "primary_summary_batch_B_vs_D16": summary, "all_changed_fields": changed,
        "ledger_rows_appended": len(LEDGER_PATH.read_bytes().splitlines()) - before,
        "limits": "Development period only, about 18 monthly observations; no holdout. A changed "
                  "number is the effect of removing timestamp errors, not new evidence of an edge.",
    })
    diagnostics(new)
    print(json.dumps({"changed_fields": len(changed), "summary": summary}, indent=1, default=str))


def diagnostics(h0: dict) -> None:
    families: dict[str, dict[str, pd.Series]] = {"H0": {}, "H1n": {}}
    decisions = {}
    for variant in h0["results"]:
        name = variant["variant"]
        family = "H0" if "raw" in name else "H1n"
        for assumption, rows in variant["monthly_return_series"].items():
            monthly = variant["monthly_missing_return_sensitivity"][assumption]
            frame = pd.DataFrame(rows)
            if (len(frame) != monthly["months"] or float(frame["ls_net"].mean()) != monthly["mean_net"]):
                raise ValueError("persisted series does not reconcile to its summary")
            index = pd.PeriodIndex(frame["return_month"], freq="M")
            if index.max() > pd.Period("2024-07", "M"):
                raise ValueError("series exceeds the development return cutoff")
            families[family][f"{name}:{assumption}"] = pd.Series(frame["ls_net"].to_numpy(), index=index)
        if family == "H0":
            decision = registered_co_primary_decision(
                "H0", monthly_t=variant["monthly"]["alpha_t"], event_change_t=None,
                delisting_effects={float(a): m["alpha"] for a, m in
                                   variant["monthly_missing_return_sensitivity"].items()},
                referee_passed=None, requires_tfidf=False, tfidf_t=None)
            decisions[name] = {"status": decision.status, "reasons": decision.reasons}
        else:
            decisions[name] = {"status": "not_applicable", "reason": "H1n is not formal H1"}
    write_receipt(DIAGNOSTICS, {
        "label": "DEVELOPMENT ONLY, D16-corrected inputs; conditional diagnostics, not support or a tradable edge",
        "families": {h: current_family_diagnostic(pd.concat(list(v.values()), axis=1, keys=list(v), join="inner"),
                                                  ledger.n_trials(h)) for h, v in families.items()},
        "D4": decisions, "results_SHA256": file_sha256(RESULTS),
        "note": "Unblocked by D14 (F8 explained). The registered monthly NW t-test is unreliable at this "
                "length (F10), so every statistic here is descriptive.",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("build", "rerun"))
    if any(os.environ.get(k) != "1" for k in THREADS[:3]):
        raise RuntimeError("set numerical library thread caps to 1")
    {"build": build, "rerun": rerun}[parser.parse_args().phase]()
