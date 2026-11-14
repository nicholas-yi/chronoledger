"""Offline P0 screening of cached H0 metadata; no requests, repair or outcome evaluation."""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from calibrate_inference import resident_bytes
from p0_acceptance_audit import factor_calendar

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.p0 import (
    acceptance_candidates,
    first_close_options,
    latest_signal_options,
    window_membership_options,
)
from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
from asof.timeutil import close_time_utc

MAX_CPU_SECONDS, MAX_RSS = 780, 1 << 30  # Reserve two minutes of the batch envelope for checks.
REPORT = PROJECT_ROOT / "results" / "p0_assignment_plan.json"
QUEUE = DATA_DIR / "p0_assignment_queue.parquet"


class CeilingReached(RuntimeError):
    pass


class Budget:
    def __init__(self) -> None:
        self.cpu_start, self.wall_start = time.process_time(), time.monotonic()
        self.peak_rss = 0

    def check(self) -> None:
        self.peak_rss = max(self.peak_rss, resident_bytes())
        if self.peak_rss >= MAX_RSS:
            raise CeilingReached("resident_memory_ceiling")
        if time.process_time() - self.cpu_start >= MAX_CPU_SECONDS:
            raise CeilingReached("CPU_ceiling")


def metadata_inputs() -> tuple[pd.DataFrame, list[Path]]:
    comparison = DATA_DIR / "p0_pair_metadata_comparison.parquet"
    signals = DATA_DIR / "h0_signals.parquet"
    columns = ["cik_pair", "accession", "form_pair", "knowledge_time_pair",
               "cik_bulk", "knowledge_time_bulk"]
    frame = pd.read_parquet(comparison, columns=columns, use_threads=False)
    original = pd.read_parquet(
        signals, columns=["cik", "accession", "form", "knowledge_time"], use_threads=False)
    if not frame["accession"].is_unique or not original["accession"].is_unique:
        raise ValueError("duplicate accession identity: stop rather than remap/deduplicate")
    left = frame[["cik_pair", "accession", "form_pair", "knowledge_time_pair"]].copy()
    left.columns = original.columns
    if not left.reset_index(drop=True).equals(original.reset_index(drop=True)):
        raise ValueError("comparison sidecar no longer matches original H0 metadata/order")
    if frame[["cik_pair", "cik_bulk", "accession", "form_pair"]].isna().any().any():
        raise ValueError("missing filing identity metadata")
    for column in ("knowledge_time_pair", "knowledge_time_bulk"):
        if frame[column].isna().any() or frame[column].dt.tz is None:
            raise ValueError("missing or naive metadata time; no silent exclusion")
    return frame, [comparison, signals]


def summarize(
    frame: pd.DataFrame, closes: list[datetime], formation_closes: list[datetime], budget: Budget,
) -> tuple[dict, pd.DataFrame]:
    start = datetime.combine(DEV_START, datetime.min.time(), tzinfo=UTC)
    end = datetime.combine(DEV_END + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    cutoff = datetime.combine(DEV_RETURN_CUTOFF + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    records = []
    by_cik: dict[int, list[int]] = {}
    candidates = {}
    raw_times = {}
    reasons: dict[str, set[str]] = {}
    if frame.empty or not formation_closes:
        raise ValueError("metadata and registered formation schedule must not be empty")
    earliest = min(frame["knowledge_time_pair"].min(), frame["knowledge_time_bulk"].min())
    closes = [t for t in closes if t.date() >= earliest.date() - timedelta(days=2)]
    if not closes:
        raise ValueError("cached nominal-close calendar cannot anchor the source metadata")
    for index, row in enumerate(frame.itertuples(index=False)):
        if index % 128 == 0:
            budget.check()
        accession = row.accession
        pair, bulk = row.knowledge_time_pair.to_pydatetime(), row.knowledge_time_bulk.to_pydatetime()
        options = [acceptance_candidates(t) for t in (pair, bulk)]
        times = tuple(sorted(set(options[0].instants) | set(options[1].instants)))
        candidates[accession], raw_times[accession] = times, pair
        flags = set()
        anchor_choices = first_close_options(times, closes)
        if len(anchor_choices) > 1:
            flags.add("first_registered_close")
        if len({start <= t < end for t in times}) > 1:
            flags.add("development_period_eligibility")
        if len({t.year for t in times}) > 1:
            flags.add("UTC_year")
        if len({(t.year, t.month) for t in times}) > 1:
            flags.add("UTC_month")
        issues = sorted({issue for option in options for issue in option.issues})
        if issues:
            flags.add("clock_interpretation_issue")
        reasons[accession] = flags
        records.append({
            "cik": int(row.cik_pair), "accession": accession, "form": row.form_pair,
            "pair_time": pair.isoformat(), "bulk_time": bulk.isoformat(),
            "source_times_agree": pair == bulk, "CIKs_agree": row.cik_pair == row.cik_bulk,
            "candidate_times": [t.isoformat() for t in times],
            "clock_issues": issues,
            "first_close_choices": [None if t is None else t.isoformat() for t in anchor_choices],
            "sample_scope": "stored_development" if start <= pair < end else "cached_background",
            "future365_exceeds_observation_cutoff": max(times) + timedelta(days=365) >= cutoff,
        })
        by_cik.setdefault(int(row.cik_pair), []).append(index)
    budget.check()
    formations = Counter()
    window_counts = Counter()
    latest_ties = 0
    all_absent_choices = 0
    for ids in by_cik.values():
        budget.check()
        firm_records = [(records[i]["accession"], candidates[records[i]["accession"]]) for i in ids]
        for close in formation_closes:
            lower, upper = max(close - timedelta(days=365), start), min(close, end)
            for accession, times in firm_records:
                if len({lower <= t < upper for t in times}) > 1:
                    reasons[accession].add("formation_eligibility")
                    formations["eligibility_record_month_instances"] += 1
            possible = latest_signal_options(
                firm_records, close, max_age_days=365, signal_window=(start, end))
            if None in possible:
                all_absent_choices += 1
            if len(possible) > 1:
                formations["latest_signal_firm_month_instances"] += 1
                # Include the entire relevant uncertainty set, not just the possible winners:
                # changing a competing record can also make another accession win.
                for accession, times in firm_records:
                    if any(lower <= t < upper for t in times):
                        reasons[accession].add("joint_latest_signal_context")
            baseline_eligible = [raw_times[a] for a, _ in firm_records
                                 if lower <= raw_times[a] < upper]
            latest_ties += int(bool(baseline_eligible)
                               and baseline_eligible.count(max(baseline_eligible)) > 1)
        for focal, a in firm_records:
            for other, b in firm_records:
                if focal == other:
                    continue
                for window in ("prior_120d", "future_365d"):
                    membership = window_membership_options(a, b, window=window)
                    if len(membership) > 1:
                        window_counts[window] += 1
                        reasons[focal].add(window)
                        reasons[other].add(window)
    budget.check()
    for record in records:
        record["sensitivity_reasons"] = sorted(reasons[record["accession"]])
        record["assignment_sensitive"] = bool(record["sensitivity_reasons"])
        record["status"] = "sensitive_needs_adjudication" if record["assignment_sensitive"] else (
            "screen_insensitive_not_certified")
    queue = pd.DataFrame(records)
    tally = Counter(reason for flags in reasons.values() for reason in flags)
    development = queue[queue["sample_scope"] == "stored_development"]
    return {
        "scope": "Full cached H0 signal metadata; source-identity CIKs preserved. "
                 "No price/size filters, scores, weights, H5 events or H4/H6 labels used.",
        "metadata_rows": len(queue),
        "stored_development_rows": len(development),
        "sensitive_accessions": int(queue["assignment_sensitive"].sum()),
        "sensitive_internally_agreeing_accessions": int(
            (queue["assignment_sensitive"] & queue["source_times_agree"]).sum()),
        "stored_development_sensitive_accessions": int(development["assignment_sensitive"].sum()),
        "sensitivity_reason_accession_counts": dict(sorted(tally.items())),
        "formation_instances": dict(formations),
        "baseline_exact_latest_ties": latest_ties,
        "firm_months_with_possible_no_signal": all_absent_choices,
        "uncertain_metadata_window_pairs": dict(window_counts),
        "window_scope": "Ordered pairs of same-CIK cached H0 filings, not verified "
                        "H6 amendment endpoints or true positive/negative labels.",
        "incomplete_future365_metadata_envelopes": int(
            queue["future365_exceeds_observation_cutoff"].sum()),
        "co_registrant_CIK_disagreements": int((~queue["CIKs_agree"]).sum()),
        "independence_model": "Union of plausible source interpretations, allowing independent "
                              "accession-level choices. Conservative screen, not probabilities "
                              "or a verified correlated source-clock model.",
        "latest_tie_contract": "Preserved input order on equal timestamps, matching stable-sort tail.",
        "development_window": [start.isoformat(), end.isoformat()],
        "window_contracts": "[focal-120d,focal) and (focal,focal+365d], explicit R1 fixture "
                            "operators; not a change to frozen H6 definitions.",
    }, queue


def main() -> None:
    import os

    if any(os.environ.get(k) != "1"
           for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("set OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS to 1")
    budget = Budget()
    report = {
        "label": "OFFLINE METADATA SENSITIVITY SCREEN; not timestamp authority, "
                 "actual look-ahead size, inference or a corrected-input snapshot",
        "status": "incomplete", "production_inputs_changed": False,
        "SEC_requests": 0, "trial_rows_appended": 0,
        "ceilings": {"CPU_seconds": MAX_CPU_SECONDS, "resident_bytes": MAX_RSS},
    }
    try:
        frame, inputs = metadata_inputs()
        before = {p: ledger.file_sha256(p) for p in inputs}
        days = factor_calendar()
        closes = [close_time_utc(d) for d in days]
        month_last = {}
        for day in days:
            if DEV_START <= day <= DEV_END:
                month_last[day.strftime("%Y-%m")] = day
        formation_closes = [close_time_utc(d) for d in month_last.values()]
        summary, queue = summarize(frame, closes, formation_closes, budget)
        for path, digest in before.items():
            if ledger.file_sha256(path) != digest:
                raise RuntimeError("input revision changed during screen; preserve report and stop")
        report.update(summary, calendar_note="Cached French date fields only, nominal16:00ET; "
                      "not an independently certified exchange/early-close calendar.",
                      formation_months=list(month_last), queue_path="data/p0_assignment_queue.parquet",
                      lineage=ledger.lineage(inputs))
        queue.to_parquet(QUEUE, index=False)
        report["queue_sha256"] = ledger.file_sha256(QUEUE)
        budget.check()
        report["status"] = "complete_screen_P0_still_blocked"
    except CeilingReached as exc:
        report["stop_reason"] = str(exc)
        raise
    except (ValueError, OSError, RuntimeError) as exc:
        report["stop_reason"] = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        report.update(CPU_seconds=time.process_time() - budget.cpu_start,
                      wall_seconds=time.monotonic() - budget.wall_start,
                      peak_resident_bytes=budget.peak_rss)
        REPORT.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({k: report[k] for k in (
            "status", "CPU_seconds", "peak_resident_bytes")}), flush=True)


if __name__ == "__main__":
    main()
