"""A1-only continuation with unchanged parent records, parsing and population."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import run_full_timestamps as base

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, user_agent
from asof.filing_timestamp_a1 import (
    MAX_WAITS,
    MIN_GAP,
    SEED,
    WAIT_SECONDS,
    AmendedSession,
    remaining_order,
)
from asof.filing_timestamp_audit import DISK_BYTES, AuditGuard
from asof.sec_documentation import DocumentationStop, MetadataUnknown

CONFIG = PROJECT_ROOT / "results" / "timestamp_full_a1_config.json"
STATUS = PROJECT_ROOT / "results" / "timestamp_full_a1_status.json"
REPORT = PROJECT_ROOT / "results" / "timestamp_full_a1_report.json"
PRIVATE = DATA_DIR / "timestamp_full_a1"
ORDER = PRIVATE / "frozen_remaining_order.jsonl"
STARTED = PRIVATE / "attempt_started.json"
OUTCOMES = PRIVATE / "resource_outcomes.jsonl"
REQUESTS = PRIVATE / "requests.jsonl"
EVENTS = PRIVATE / "waits_and_retries.jsonl"
CHECKPOINT = PRIVATE / "checkpoint.json"
TABLE = PRIVATE / "combined_per_accession.jsonl"
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "filing_timestamp_a1.py",
           PROJECT_ROOT / "tests" / "test_filing_timestamp_a1.py"]


def frozen_checks(config: dict) -> None:
    base.verify({**config["input_SHA256"], **config["parent_source_SHA256"],
                 **config["source_SHA256"], **config["order_SHA256"]})


def freeze() -> None:
    if CONFIG.exists() or PRIVATE.exists():
        raise RuntimeError("A1 already frozen; preserve it")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": 1421, "ceiling": 34402}:
        raise ValueError("A1 starts only at1421of34402")
    original = json.loads(base.CONFIG.read_bytes())
    prior_report = json.loads(base.REPORT.read_bytes())
    base.verify({**original["source_SHA256"], **original["input_SHA256"],
                 **original["exact_lists"], **original["cache_pins"],
                 **prior_report["private_hash_manifest"]})
    base.suspend_clocks()
    roster, inventory = base.load_lines(base.ROSTER), base.load_lines(base.INVENTORY)
    prior = base.load_lines(base.OUTCOMES)
    order = remaining_order(inventory, prior, roster)
    counts = Counter(r["priority"] for r in order)
    groups = {p: len({r["accession"] for r in order if r["priority"] == p})
              for p in counts}
    if (len(order), sum(r["proposed_HTTP_needed"] for r in order),
        groups["clock108"], groups["CIK256"]) != (33066, 32972, 108, 256):
        raise ValueError("approved A1 exact remainder differs")
    PRIVATE.mkdir()
    base.write_lines(ORDER, order)
    value = {
        "kind": "APPROVED CL-TS-FULL AMENDMENT A1; ONE CONTINUATION, NOT REPAIR",
        "approval": "Lead dispatch: user next=resume_amended on2026-11-16.",
        "parent_freeze_commit": "f6495d411bd3eda73286bce19893f6f8fa87a43f",
        "parent_stop_commit": "d5b08bade2a049d000b6308ff82555bc2fa046ca",
        "unchanged": "All original source files, population16921, URLlist34354, cachemarks, "
                     "64KiB bound, parser, Eastern assumption, calendar and output contract.",
        "protected_prior_outcomes": 1288,
        "prior_outcomes_retained": 1289,
        "previous503_resources_reeligible": 1,
        "remaining_resources": 33066, "remaining_new_metadata_URLs": 32972,
        "remaining_pinned_cache_hits": 94,
        "order": {"seed": SEED, "unit": "accession; original within-accession URL order retained",
                  "rule": "Sorted108designated clock-disagreement accessions first; sorted256CIK "
                          "disagreements second; Random(seed).shuffle(sorted(other remaining "
                          "accessions)) last. No previously processed resource re-fetched except "
                          "the expressly reeligible prior503. At-cap unknowns stay protected.",
                  "resource_counts": dict(counts), "accession_counts": groups},
        "rate": {"minimum_gap_seconds": MIN_GAP, "target_starts_per_second": 1.5,
                 "clock": vars(time.get_clock_info("perf_counter")),
                 "algorithm": "perf_counter elapsed-gap comparison in a post-wait recheck loop; "
                              "mark refuses any gap<0.667. Persist each actual application "
                              "transport dispatch perf_counter and UTC in attempt receipts.",
                 "scope": "One borrowed scoped adapter per charged attempt, one shared serial "
                          "connection pool. Original adapter guards are never cleared/bypassed."},
        "error_policy": {"wait_statuses": [503, 429], "wait_seconds": WAIT_SECONDS,
                         "max_waits": MAX_WAITS, "same_URL_retries": 1,
                         "second503or429": "stop immediately; no second wait for that resource",
                         "sixth_wait": "stop before waiting/retrying",
                         "others": "Original404/read-cap unknown-continue;403/other5xx/transport/"
                                   "redirect/scope/budget/integrity/wall/disk/sleep stop."},
        "budget": {"start": 1421, "ceiling_unchanged": 34402,
                   "max_primary_metadata_attempts": 32972, "max_retry_attempts": 5,
                   "max_new_attempts": 32977, "no_documentation_requests": True},
        "resources": {"parallelism": 1, "timeout_seconds": 30, "wall_from_resume_seconds": 43200,
                      "disk_bytes_old_plus_A1": DISK_BYTES, "checkpoint_resources": 500,
                      "sleep": "Existing Windows uptime-minus-awake guard; record/stop, no resume."},
        "no_automatic_resume": True,
        "User_Agent_SHA256": original["User_Agent_SHA256"],
        "input_SHA256": {
            **original["input_SHA256"], **original["exact_lists"], **original["cache_pins"],
            **prior_report["private_hash_manifest"],
            **base.pin([base.CONFIG, base.STATUS, base.REPORT,
                        PROJECT_ROOT / "results" / "timestamp_full_review.json"])},
        "parent_source_SHA256": original["source_SHA256"],
        "source_SHA256": base.pin(SOURCES), "order_SHA256": base.pin([ORDER]),
        "original_rate_context": "Precision miss against our own <=2/s protocol, not evidence "
                                 "of a SEC10/s fair-access breach. Original receipts averaged "
                                 "~1.9/s and never exceeded2starts in a calendar second; sliding "
                                 "windows and coarse clock quantization differ. No503causal claim.",
    }
    base.atomic_json(CONFIG, value)
    print(json.dumps({"frozen": True, "remaining_resources": len(order),
                      "priority_accessions": groups, "config_SHA256": ledger.file_sha256(CONFIG),
                      "counter_unchanged": 1421}))


def merge_outcomes(prior: list[dict], amended: list[dict], order: list[dict]) -> dict:
    allowed = {r["URL"] for r in order}
    if len({r["URL"] for r in amended}) != len(amended):
        raise ValueError("duplicate A1 terminal resource outcome")
    result = {r["URL"]: r for r in prior}
    for row in amended:
        if row["URL"] not in allowed:
            raise ValueError("A1 outcome outside frozen remainder")
        previous = result.get(row["URL"])
        if previous and previous.get("request", {}).get("status") != 503:
            raise ValueError("attempt to replace protected historical resource")
        result[row["URL"]] = row
    return result


def report() -> None:
    if REPORT.exists() or TABLE.exists():
        raise RuntimeError("A1 report already exists; preserve it")
    config = json.loads(CONFIG.read_bytes())
    frozen_checks(config)
    order = base.load_lines(ORDER)
    old = base.load_lines(base.OUTCOMES)
    amended = base.load_lines(OUTCOMES) if OUTCOMES.exists() else []
    effective = merge_outcomes(old, amended, order)
    inventory, roster = base.load_lines(base.INVENTORY), base.load_lines(base.ROSTER)
    grouped = defaultdict(list)
    for resource in inventory:
        grouped[resource["accession"]].append(effective.get(resource["URL"], {
            **resource, "parsed": {"unknown": "not_attempted_after_A1_final_stop"}}))
    rows = [base.accession_result(row, grouped[row["accession"]]) for row in roster]
    required = sum(len(json.dumps(r, allow_nan=False).encode()) + 1 for r in rows)
    occupied = sum(p.stat().st_size for directory in (base.PRIVATE, PRIVATE)
                   for p in directory.rglob("*") if p.is_file())
    if occupied + required + (64 << 20) >= DISK_BYTES:
        raise DocumentationStop("A1_final_report_disk_budget")
    base.write_lines(TABLE, rows)
    calendar = json.loads(base.CALENDAR.read_bytes())
    assignments = base.assignment_counts(
        base.load_lines(base.UNIVERSE), rows,
        [datetime.fromisoformat(t) for t in calendar["closes"]],
        [datetime.fromisoformat(t) for t in calendar["formations"]],
        datetime.fromisoformat(calendar["start"]), datetime.fromisoformat(calendar["end"]))
    logs = base.load_lines(REQUESTS) if REQUESTS.exists() else []
    starts = [r for r in logs if r["event"] == "started"]
    finishes = [r for r in logs if r["event"] == "finished" and r["attempted"]]
    sends = [r for r in logs if r["event"] == "send"]
    used = json.loads(base.BUDGET.read_bytes())["actual_HTTP_attempts"]
    if [r["historical_attempt"] for r in starts] != list(range(1422, used + 1)):
        raise ValueError("A1 budget/receipt mismatch")
    gaps = [b["send_perf_counter"] - a["send_perf_counter"] for a, b in pairwise(sends)]
    waits = base.load_lines(EVENTS) if EVENTS.exists() else []
    public_events = [{**{k: v for k, v in e.items() if k != "url"},
                      "URL_SHA256": hashlib.sha256(e["url"].encode()).hexdigest()} for e in waits]
    pools = {}
    for pool in ("clock_disagreement_winter", "clock_disagreement_summer", "CIK_disagreement",
                 "candidate_calendar_boundary_or_clock_issue", "clock_agreement_sensitive"):
        part = [r for r in rows if r["pool"] == pool]
        pools[pool] = {"accessions": len(part),
                       "agreement_classes": dict(Counter(r["agreement_class"] for r in part)),
                       "unique_conditional_UTC": sum(bool(r["conditional_UTC_assuming_Eastern"])
                                                     for r in part),
                       "historically_qualified_UTC": 0}
    raw_manifest, receipt_manifest = PRIVATE / "raw_hashes.jsonl", PRIVATE / "receipt_hashes.jsonl"
    for directory, manifest in ((PRIVATE / "raw_metadata", raw_manifest),
                                (PRIVATE / "attempt_receipts", receipt_manifest)):
        base.write_lines(manifest, [
            {"path": str(p.relative_to(PRIVATE)), "bytes": p.stat().st_size,
             "SHA256": ledger.file_sha256(p)} for p in sorted(directory.glob("*"))])
    value = {
        "status": json.loads(STATUS.read_bytes())["status"],
        "stop_reason": json.loads(STATUS.read_bytes()).get("stop_reason"),
        "amendment_commit": json.loads(STATUS.read_bytes())["amendment_commit"],
        "config_SHA256": ledger.file_sha256(CONFIG), "parent_freeze": config["parent_freeze_commit"],
        "designated108_first": {p: pools[p] for p in
                                ("clock_disagreement_winter", "clock_disagreement_summer")},
        "pool_summary": pools,
        "qualified_UTC": {"historically_qualified": 0, "unresolved": len(rows),
                          "unique_conditional_assuming_Eastern": sum(
                              bool(r["conditional_UTC_assuming_Eastern"]) for r in rows)},
        "assignments": assignments,
        "A1_attempts": len(starts), "A1_HTTP_status_counts": dict(Counter(
            str(r["status"]) for r in finishes)),
        "A1_retries_charged": sum(bool(r["A1_retry"]) for r in starts),
        "A1_waits_started": sum(e["event"] == "wait_started" for e in waits),
        "every_wait_and_retry": public_events,
        "counter": {"actual_HTTP_attempts": used, "ceiling": 34402},
        "A1_resource_outcomes": len(amended),
        "A1_order_resources_not_processed": len(order) - len(amended),
        "effective_unique_resource_outcomes": len(effective),
        "resources_not_attempted": len(inventory) - len(effective),
        "QPC_rate": {"sends": len(sends), "minimum_gap_seconds": min(gaps) if gaps else None,
                      "median_gap_seconds": statistics.median(gaps) if gaps else None,
                      "maximum_gap_seconds": max(gaps) if gaps else None,
                      "declared_minimum_seconds": MIN_GAP,
                      "all_observed_gaps_meet_minimum": all(g >= MIN_GAP for g in gaps)
                          if gaps else None,
                      "definition": "New A1 application transport dispatches only, not wire "
                                    "timestamps or retrospective validation of the old run."},
        "private_hash_manifest": base.pin([p for p in (
            ORDER, OUTCOMES, REQUESTS, EVENTS, CHECKPOINT, TABLE, raw_manifest, receipt_manifest)
            if p.exists()]),
        "original_rate_context": config["original_rate_context"],
        "limits": "Unqualified Eastern assumption and original cached nominal calendar; no "
                  "verified actual assignment-change count. Original outcomes preserved, "
                  "except authorized503 overlay in the combined view; originals remain intact. "
                  "No prices, returns, feature values, repairs, correction release or ledger row.",
    }
    base.atomic_json(REPORT, value)
    print(json.dumps({"status": value["status"], "counter": used,
                      "A1_attempts": len(starts), "waits": value["A1_waits_started"],
                      "qualified_UTC": 0}), flush=True)


async def run() -> None:
    if any(p.exists() for p in (STARTED, STATUS, OUTCOMES, REQUESTS)):
        raise RuntimeError("A1 already attempted; no automatic continuation")
    config = json.loads(CONFIG.read_bytes())
    frozen_checks(config)
    lineage = ledger.lineage()
    if lineage["git_dirty"]:
        raise RuntimeError("commit A1 source and exact order before requests")
    process = await asyncio.create_subprocess_exec(
        "git", "show", "HEAD:results/timestamp_full_a1_config.json", cwd=PROJECT_ROOT,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    committed, error = await process.communicate()
    if process.returncode != 0 or committed != CONFIG.read_bytes():
        raise RuntimeError(f"A1 config not identical to committed freeze:{error.decode(errors='replace')}")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": 1421, "ceiling": 34402}:
        raise ValueError("A1 starting counter changed")
    if hashlib.sha256(user_agent().encode()).hexdigest() != config["User_Agent_SHA256"]:
        raise ValueError("declared User-Agent changed")
    with STARTED.open("x", encoding="utf-8") as stream:
        json.dump({"UTC": datetime.now(UTC).isoformat(), "lineage": lineage}, stream)
    static_bytes = sum(p.stat().st_size for d in (base.PRIVATE, PRIVATE)
                       for p in d.rglob("*") if p.is_file())
    session: AmendedSession | None = None

    def storage() -> int:
        return static_bytes + (session.allocated_bytes if session else 0) + sum(
            p.stat().st_size for p in (REQUESTS, EVENTS, OUTCOMES, CHECKPOINT, STATUS) if p.exists())

    guard = AuditGuard(base.suspend_clocks, storage)
    status = {"status": "in_progress", "amendment_commit": lineage["git_commit"],
              "start_UTC": datetime.now(UTC).isoformat(), "wall_cap_seconds": 43200,
              "resources_recorded": 0, "sleep_interruptions": guard.interruptions,
              "counter_start": 1421, "config_SHA256": ledger.file_sha256(CONFIG)}

    def checkpoint(event: dict | None = None) -> None:
        if event:
            status["latest_retry_event"] = {k: v for k, v in event.items() if k != "url"}
        for path in (OUTCOMES, REQUESTS, EVENTS):
            if path.exists():
                with path.open("ab") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
        status.update(counter=json.loads(base.BUDGET.read_bytes()),
                      wall_seconds=time.monotonic() - guard.started,
                      disk_bytes_observed=storage(),
                      checkpoint_UTC=datetime.now(UTC).isoformat())
        base.atomic_json(CHECKPOINT, {**status, "hashes": base.pin([
            p for p in (OUTCOMES, REQUESTS, EVENTS) if p.exists()])})
        base.atomic_json(STATUS, status)
        print(json.dumps({k: status[k] for k in (
            "status", "resources_recorded", "counter", "wall_seconds")}), flush=True)

    checkpoint()
    order = base.load_lines(ORDER)
    try:
        async with AmendedSession(
            {r["URL"] for r in order if r["proposed_HTTP_needed"]},
            base.BUDGET, PRIVATE, guard, on_event=checkpoint,
        ) as session:
            for resource in order:
                guard.check()
                item = {**resource, "cache_hit": not resource["proposed_HTTP_needed"]}
                stop = None
                session.current_attempts = []
                try:
                    if item["cache_hit"]:
                        path = DATA_DIR / resource["cache"]["path"]
                        if ledger.file_sha256(path) != resource["cache"]["file_SHA256"]:
                            raise DocumentationStop("frozen_cache_changed")
                        if path.suffix == ".gz":
                            with gzip.open(path, "rb") as stream:
                                raw = stream.read(65536)
                        else:
                            with path.open("rb") as stream:
                                raw = stream.read(65536)
                        if len(raw) >= 65536:
                            raise MetadataUnknown("cached_metadata_at_read_cap")
                    else:
                        raw = await session.fetch(item["URL"])
                    parsed = (base.parse_header(raw, item["accession"]) if item["kind"] == "header"
                              else base.parse_index(raw))
                    candidate = parsed.get("UTC_assuming_Eastern")
                    if candidate and not "2022-01-01" <= candidate[:10] < "2024-07-01":
                        raise DocumentationStop("header_outside_frozen_metadata_date_scope")
                    item["parsed"] = parsed
                except MetadataUnknown as exc:
                    item["parsed"] = {"unknown": str(exc)}
                except (DocumentationStop, OSError, ValueError) as exc:
                    item["parsed"] = {"unknown": f"resource_failed:{exc}"}
                    stop = str(exc)
                item["A1_attempts"] = list(session.current_attempts)
                with OUTCOMES.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(item, allow_nan=False) + "\n")
                status["resources_recorded"] += 1
                if stop:
                    raise DocumentationStop(stop)
                if status["resources_recorded"] % 500 == 0:
                    frozen_checks(config)
                    checkpoint()
        status["status"] = "complete_conditional_A1_check"
    except (DocumentationStop, OSError, ValueError) as exc:
        status.update(status="stopped_final", stop_reason=str(exc))
    finally:
        if status["status"] == "in_progress":
            error = sys.exception()
            status.update(status="interrupted_final", stop_reason=(
                f"{type(error).__name__}:{error}" if error else "unexpected_interruption"))
        checkpoint()
    report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run", "report"))
    args = parser.parse_args()
    if any(os.environ.get(k) != "1" for k in
           ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("set numerical library thread caps to1")
    if args.phase == "freeze":
        freeze()
    elif args.phase == "run":
        asyncio.run(run())
    else:
        report()
