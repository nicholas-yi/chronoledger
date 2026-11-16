"""A2: the next fixed 3000 new random-rest accessions, with predeclared error bounds."""

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
import run_full_timestamps_a1 as a1

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, user_agent
from asof.filing_timestamp_a2 import A2Guard, BoundedSession, bounded_window, error_bounds
from asof.filing_timestamp_audit import DISK_BYTES
from asof.sec_documentation import DocumentationStop, MetadataUnknown

CONFIG = PROJECT_ROOT / "results" / "timestamp_full_a2_config.json"
STATUS = PROJECT_ROOT / "results" / "timestamp_full_a2_status.json"
REPORT = PROJECT_ROOT / "results" / "timestamp_full_a2_report.json"
PRIVATE = DATA_DIR / "timestamp_full_a2"
ORDER = PRIVATE / "frozen_3000_order.jsonl"
SAMPLE = PRIVATE / "frozen_combined_sample.jsonl"
STARTED = PRIVATE / "attempt_started.json"
OUTCOMES = PRIVATE / "resource_outcomes.jsonl"
REQUESTS = PRIVATE / "requests.jsonl"
EVENTS = PRIVATE / "waits_and_retries.jsonl"
CHECKPOINT = PRIVATE / "checkpoint.json"
TABLE = PRIVATE / "combined_per_accession.jsonl"
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "filing_timestamp_a2.py",
           PROJECT_ROOT / "tests" / "test_filing_timestamp_a2.py"]


def frozen_checks(config: dict) -> None:
    base.verify({**config["input_SHA256"], **config["ancestor_source_SHA256"],
                 **config["source_SHA256"], **config["sample_order_SHA256"]})


def freeze() -> None:
    if CONFIG.exists() or PRIVATE.exists():
        raise RuntimeError("A2 already frozen; preserve it")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": 3137, "ceiling": 34402}:
        raise ValueError("A2 starts at3137of34402")
    parent = json.loads(a1.CONFIG.read_bytes())
    parent_report = json.loads(a1.REPORT.read_bytes())
    a1.frozen_checks(parent)
    base.verify(parent_report["private_hash_manifest"])
    base.suspend_clocks()
    full_order, previous = base.load_lines(a1.ORDER), base.load_lines(a1.OUTCOMES)
    order = bounded_window(full_order, previous)
    old_ids = list(dict.fromkeys(r["accession"] for r in previous if r["priority"] == "random_rest"))
    new_ids = list(dict.fromkeys(r["accession"] for r in order))
    if (len(old_ids), len(new_ids), len(order), order[0]["a1_order"]) != (270, 3000, 6000, 1780):
        raise ValueError("approved fixed boundary differs")
    if set(old_ids) & set(new_ids) or previous[-1]["accession"] in new_ids:
        raise ValueError("A1 timeout must remain outside the clarified new-accession window")
    PRIVATE.mkdir()
    base.write_lines(ORDER, order)
    base.write_lines(SAMPLE, [{"accession": a, "source": source} for source, ids in
                              (("A1_prior270", old_ids), ("A2_fixed3000", new_ids)) for a in ids])
    value = {
        "kind": "APPROVED CL-TS-A2 fixed bounded continuation; no automatic continuation",
        "parent_amendment_commit": "c05e113ee839674d2a2959ecca7304c0d2863361",
        "starting_revision": "ac6e1c4de428b7a2837dec9077b4117a35d1454d",
        "approval": "Lead next=sample_bound; ask_user clarified next_new_accession, "
                    "all_internally_agreeing_random_rest, missingness_sensitivity=true.",
        "scope": {"new_accessions": 3000, "resources": len(order),
                  "primary_GET_URLs": sum(r["proposed_HTTP_needed"] for r in order),
                  "pinned_cache_hits": sum(not r["proposed_HTTP_needed"] for r in order),
                  "start_A1_order_index": order[0]["a1_order"],
                  "end_A1_order_index_inclusive": order[-1]["a1_order"],
                  "seed_unchanged": 2026111603,
                  "rule": "After270A1random-rest accessions, take the next3000NEW accession "
                          "IDs in the existing order, retain both resources, no skipping/"
                          "reordering/refetching completed resources.",
                  "A1_timeout_left_pending": True,
                  "original503_inside_window": any(r["previous503_reeligible"] for r in order)},
        "predeclared_statistic": {
            "timing": "Before any A2 request, AFTER A1 outcomes were seen; combined interval "
                      "is not a registration predating A1 and is not confirmatory return evidence.",
            "fixed_sample": "270A1attempted accessions plus3000disjoint A2selected accessions=3270.",
            "eligibility": "All internally agreeing random-rest strata, including agreement-sensitive "
                           "and boundary pools. Exclude108clock/256CIK priority and original "
                           "sorted-prefix cases. Freeze clarified broader population explicitly.",
            "k": "Complete conditional header/index pair whose Eastern-derived UTC disagrees "
                 "with BOTH stored source times.",
            "n": "Visited, conditionally readable complete pairs with internally agreeing stored "
                 "times; unread/malformed/conflicting pairs never count as error-free.",
            "interval": "Exact one-sided95%Clopper-Pearson upper:Beta.ppf(.95,k+1,n-k), "
                        "k=n=>1,n=0=>null. Report k,n and upper by original pool and overall.",
            "conservative_sensitivity": "Separate all-selected bound: count ALL unread selected "
                                        "eligible cases, including unvisited after early stop, as "
                                        "errors. Report selected/visited/unread/excluded counts.",
            "limits": "Eastern assumption only; random only within remaining random-rest order, "
                      "not allEDGAR. Readability/stopping may be selective; complete-case CP "
                      "is not an always-valid sequential or whole-cohort guarantee.",
        },
        "error_policy": {
            "transport_timeout_or_connection_reset": "Wait60QPCseconds, sameURL retry once.",
            "reset_definition": "Typed ConnectionResetError, ECONNRESET or WinError10054 "
                                "in preserved exception chain; no generic ConnectError retry.",
            "HTTP503_or429": "Wait600QPCseconds, sameURL retry once; max20status waits.",
            "all_waits_cumulative_seconds": 7200,
            "second_request_error": "Stop; never a second retry/cooldown for that resource.",
            "unknowns": "Unchanged404/at-cap unknown-continue, including a retry response.",
            "immediate_stops": "403,other5xx,redirect,othertransport,scope/budget/integrity,"
                               "wall/disk/sleep; record every wait, retry and declined wait.",
        },
        "unchanged": {"minimum_QPC_gap": 0.667, "request_timeout_seconds": 30,
                      "body_bound_bytes": 65536, "checkpoint_resources": 500,
                      "disk_bytes_all_runs": DISK_BYTES, "wall_from_A2_start_seconds": 14400,
                      "counter_start": 3137, "ceiling": 34402,
                      "population_parser_clock_calendar": "Original16921/34354allowlist, parser, "
                          "Eastern assumption, nominal calendar, sleep-stop, no repair/returns."},
        "User_Agent_SHA256": parent["User_Agent_SHA256"],
        "input_SHA256": {
            **parent["input_SHA256"], **parent["order_SHA256"],
            **parent_report["private_hash_manifest"],
            **base.pin([a1.CONFIG, a1.STATUS, a1.REPORT,
                        PROJECT_ROOT / "results" / "timestamp_full_a1_review.json"])},
        "ancestor_source_SHA256": {**parent["parent_source_SHA256"], **parent["source_SHA256"]},
        "source_SHA256": base.pin(SOURCES), "sample_order_SHA256": base.pin([ORDER, SAMPLE]),
    }
    base.atomic_json(CONFIG, value)
    print(json.dumps({"frozen": value["scope"], "config_SHA256": ledger.file_sha256(CONFIG),
                      "counter_unchanged": 3137}))


def report() -> None:
    if REPORT.exists() or TABLE.exists():
        raise RuntimeError("A2 report already exists; preserve it")
    config = json.loads(CONFIG.read_bytes())
    frozen_checks(config)
    order = base.load_lines(ORDER)
    amended = base.load_lines(OUTCOMES) if OUTCOMES.exists() else []
    parent = a1.merge_outcomes(base.load_lines(base.OUTCOMES), base.load_lines(a1.OUTCOMES),
                               base.load_lines(a1.ORDER))
    effective = a1.merge_outcomes(list(parent.values()), amended, order)
    inventory, roster = base.load_lines(base.INVENTORY), base.load_lines(base.ROSTER)
    groups = defaultdict(list)
    for resource in inventory:
        groups[resource["accession"]].append(effective.get(resource["URL"], {
            **resource, "parsed": {"unknown": "not_attempted_after_A2_final_stop"}}))
    rows = [base.accession_result(row, groups[row["accession"]]) for row in roster]
    required = sum(len(json.dumps(r, allow_nan=False).encode()) + 1 for r in rows)
    occupied = sum(p.stat().st_size for d in (base.PRIVATE, a1.PRIVATE, PRIVATE)
                   for p in d.rglob("*") if p.is_file())
    if occupied + required + (64 << 20) >= DISK_BYTES:
        raise DocumentationStop("A2_final_report_disk_budget")
    base.write_lines(TABLE, rows)
    selected = [r["accession"] for r in base.load_lines(SAMPLE)]
    old_random = {r["accession"] for r in base.load_lines(a1.OUTCOMES)
                  if r["priority"] == "random_rest"}
    visited = old_random | {r["accession"] for r in amended}
    bounds = error_bounds(roster, rows, selected, visited)
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
    if [r["historical_attempt"] for r in starts] != list(range(3138, used + 1)):
        raise ValueError("A2 budget/receipt mismatch")
    gaps = [b["send_perf_counter"] - a["send_perf_counter"] for a, b in pairwise(sends)]
    events = base.load_lines(EVENTS) if EVENTS.exists() else []
    public_events = [{**{k: v for k, v in e.items() if k != "url"},
                      "URL_SHA256": hashlib.sha256(e["url"].encode()).hexdigest()} for e in events]
    pools = {}
    for pool in sorted({r["pool"] for r in rows}):
        part = [r for r in rows if r["pool"] == pool]
        pools[pool] = {"accessions": len(part),
                       "agreement_classes": dict(Counter(r["agreement_class"] for r in part)),
                       "unique_conditional_UTC": sum(bool(r["conditional_UTC_assuming_Eastern"])
                                                     for r in part)}
    manifests = []
    for directory, name in ((PRIVATE / "raw_metadata", "raw_hashes.jsonl"),
                            (PRIVATE / "attempt_receipts", "receipt_hashes.jsonl")):
        manifest = PRIVATE / name
        base.write_lines(manifest, [{"path": str(p.relative_to(PRIVATE)), "bytes": p.stat().st_size,
                                    "SHA256": ledger.file_sha256(p)}
                                   for p in sorted(directory.glob("*"))])
        manifests.append(manifest)
    value = {
        "status": json.loads(STATUS.read_bytes())["status"],
        "stop_reason": json.loads(STATUS.read_bytes()).get("stop_reason"),
        "amendment_commit": json.loads(STATUS.read_bytes())["amendment_commit"],
        "config_SHA256": ledger.file_sha256(CONFIG),
        "predeclared_conditional_error_bounds": bounds,
        "conditional_assignments": assignments, "combined_pool_summary": pools,
        "qualified_UTC": 0, "unresolved_accessions": len(rows),
        "unique_conditional_UTC": sum(bool(r["conditional_UTC_assuming_Eastern"]) for r in rows),
        "A2_attempts": len(starts), "A2_HTTP_status_counts": dict(Counter(
            str(r["status"]) for r in finishes)),
        "A2_retries_charged": sum(bool(r["A2_retry"]) for r in starts),
        "A2_waits_started": sum(e["event"] == "wait_started" for e in events),
        "A2_status_waits": sum(e["event"] == "wait_started" and e["trigger"].startswith("HTTP_")
                               for e in events),
        "cumulative_wait_seconds": sum(e["elapsed_perf_seconds"] for e in events
                                       if e["event"] == "wait_finished"),
        "every_wait_and_retry": public_events,
        "counter": {"actual_HTTP_attempts": used, "ceiling": 34402},
        "A2_resource_outcomes": len(amended), "A2_order_resources_not_processed": len(order)-len(amended),
        "effective_unique_resource_outcomes": len(effective),
        "resources_never_attempted": len(inventory)-len(effective),
        "QPC_rate": {"sends": len(sends), "minimum_gap_seconds": min(gaps) if gaps else None,
                      "median_gap_seconds": statistics.median(gaps) if gaps else None,
                      "maximum_gap_seconds": max(gaps) if gaps else None,
                      "all_observed_gaps_meet0_667": all(g >= 0.667 for g in gaps) if gaps else None},
        "private_hash_manifest": base.pin([p for p in (
            ORDER, SAMPLE, OUTCOMES, REQUESTS, EVENTS, CHECKPOINT, TABLE, *manifests) if p.exists()]),
        "limits": "Conditional Eastern assumption and original metadata/calendar only. No "
                  "historically verified UTC or actual assignment-change certification. All "
                  "ancestor records preserved; no completed resource refetch, repair, backtest, "
                  "price/return/feature value, sealed observation or ledger row.",
    }
    base.atomic_json(REPORT, value)
    print(json.dumps({"status": value["status"], "counter": used, "A2_attempts": len(starts),
                      "sample": bounds["by_pool_and_overall"]["overall"]}), flush=True)


async def run() -> None:
    if any(p.exists() for p in (STARTED, STATUS, OUTCOMES, REQUESTS)):
        raise RuntimeError("A2 already attempted; no automatic continuation")
    config = json.loads(CONFIG.read_bytes())
    frozen_checks(config)
    lineage = ledger.lineage()
    if lineage["git_dirty"]:
        raise RuntimeError("commit A2 exact sample and source first")
    process = await asyncio.create_subprocess_exec(
        "git", "show", "HEAD:results/timestamp_full_a2_config.json", cwd=PROJECT_ROOT,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    committed, error = await process.communicate()
    if process.returncode != 0 or committed != CONFIG.read_bytes():
        raise RuntimeError(f"A2 config not identical to committed freeze:{error.decode(errors='replace')}")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": 3137, "ceiling": 34402}:
        raise ValueError("A2 starting counter changed")
    if hashlib.sha256(user_agent().encode()).hexdigest() != config["User_Agent_SHA256"]:
        raise ValueError("declared User-Agent changed")
    with STARTED.open("x", encoding="utf-8") as stream:
        json.dump({"UTC": datetime.now(UTC).isoformat(), "lineage": lineage}, stream)
    static = sum(p.stat().st_size for d in (base.PRIVATE, a1.PRIVATE, PRIVATE)
                 for p in d.rglob("*") if p.is_file())
    session: BoundedSession | None = None

    def storage() -> int:
        return static + (session.allocated_bytes if session else 0) + sum(
            p.stat().st_size for p in (REQUESTS, EVENTS, OUTCOMES, CHECKPOINT, STATUS) if p.exists())

    guard = A2Guard(base.suspend_clocks, storage, wall_seconds=14400)
    status = {"status": "in_progress", "amendment_commit": lineage["git_commit"],
              "start_UTC": datetime.now(UTC).isoformat(), "wall_cap_seconds": 14400,
              "resources_recorded": 0, "sleep_interruptions": guard.interruptions,
              "counter_start": 3137, "config_SHA256": ledger.file_sha256(CONFIG)}

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
                      disk_bytes_observed=storage(), checkpoint_UTC=datetime.now(UTC).isoformat())
        base.atomic_json(CHECKPOINT, {**status, "hashes": base.pin([
            p for p in (OUTCOMES, REQUESTS, EVENTS) if p.exists()])})
        base.atomic_json(STATUS, status)
        print(json.dumps({k: status[k] for k in (
            "status", "resources_recorded", "counter", "wall_seconds")}), flush=True)

    checkpoint()
    order = base.load_lines(ORDER)
    try:
        async with BoundedSession({r["URL"] for r in order if r["proposed_HTTP_needed"]},
                                  base.BUDGET, PRIVATE, guard, on_event=checkpoint) as session:
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
                item["A2_attempts"] = list(session.current_attempts)
                with OUTCOMES.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(item, allow_nan=False) + "\n")
                status["resources_recorded"] += 1
                if stop:
                    raise DocumentationStop(stop)
                if status["resources_recorded"] % 500 == 0:
                    frozen_checks(config)
                    checkpoint()
        status["status"] = "bounded3000_complete_conditional_A2"
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
