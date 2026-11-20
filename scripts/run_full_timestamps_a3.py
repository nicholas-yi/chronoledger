"""A3: declared clock-basis test, approved pilot-then-full metadata audit and qualification.

Phases (each refuses to repeat): ``freeze`` -> commit -> ``cb1`` -> ``run pilot`` ->
``run full1`` (only if the pilot gate passed; further ``fullN`` segments only after a
recorded stop) -> ``report``. No price, return, ledger or holdout access.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import run_full_timestamps as base
import run_full_timestamps_a1 as a1
import run_full_timestamps_a2 as a2

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, user_agent
from asof.filing_clock_basis import (
    RULE,
    clock_basis_test,
    first_close_direction,
    identity_class,
    parse_header_dates,
    qualify,
)
from asof.filing_timestamp_a3 import (
    CEILING,
    MAX_CONSECUTIVE_UNRESOLVED,
    MAX_THROTTLE_PAUSES,
    PILOT_ATTEMPTS,
    PILOT_MAX_PAUSES,
    READ_CAP,
    SLOW_GAP,
    START_GAP,
    A3Session,
    AdaptiveLimiter,
    a3_order,
    effective_outcomes,
    raw_resource_bytes,
    reeligible,
)
from asof.filing_timestamp_audit import DISK_BYTES, AuditGuard
from asof.runtime import write_receipt
from asof.sec_documentation import DocumentationStop, MetadataUnknown

START_USED = 3254
CONFIG = PROJECT_ROOT / "results" / "timestamp_full_a3_config.json"
CB1 = PROJECT_ROOT / "results" / "timestamp_a3_clock_basis_cb1.json"
GATE = PROJECT_ROOT / "results" / "timestamp_full_a3_pilot_gate.json"
REPORT = PROJECT_ROOT / "results" / "timestamp_full_a3_report.json"
PRIVATE = DATA_DIR / "timestamp_full_a3"
ORDER = PRIVATE / "frozen_order.jsonl"
TABLE = PRIVATE / "qualified_per_accession.jsonl"
SEGMENTS = ("pilot", "full1", "full2", "full3")
WALL = {"pilot": 2700, "full": 50400}
SOURCES = [Path(__file__), *(PROJECT_ROOT / "src" / "asof" / f"{name}.py" for name in (
    "filing_timestamp_a3", "filing_clock_basis", "filing_timestamp_a2", "filing_timestamp_a1",
    "filing_timestamp_audit", "filing_header_pilot", "sec_documentation", "timeutil")),
    *(PROJECT_ROOT / "scripts" / f"{name}.py" for name in (
        "run_full_timestamps", "run_full_timestamps_a1", "run_full_timestamps_a2")),
    PROJECT_ROOT / "tests" / "test_filing_timestamp_a3.py"]
DIRECTORIES = {"request": base.PRIVATE, "A1_attempts": a1.PRIVATE, "A2_attempts": a2.PRIVATE,
               **{s: PRIVATE / s for s in SEGMENTS}}


def status_path(segment: str) -> Path:
    return PROJECT_ROOT / "results" / f"timestamp_full_a3_{segment}_status.json"


def ancestors() -> list[list[dict]]:
    return [base.load_lines(base.OUTCOMES), base.load_lines(a1.OUTCOMES), base.load_lines(a2.OUTCOMES)]


def a3_segments() -> list[list[dict]]:
    return [base.load_lines(PRIVATE / s / "resource_outcomes.jsonl") for s in SEGMENTS
            if (PRIVATE / s / "resource_outcomes.jsonl").exists()]


def frozen_checks(config: dict) -> None:
    base.verify({**config["input_SHA256"], **config["source_SHA256"], **config["order_SHA256"]})


def freeze() -> None:
    if CONFIG.exists() or PRIVATE.exists():
        raise RuntimeError("A3 already frozen; preserve it")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": START_USED, "ceiling": CEILING}:
        raise ValueError("A3 starts at the recorded 3254 (A2 3246 + 8 closure documentation)")
    parent = json.loads(a2.CONFIG.read_bytes())
    parent_report = json.loads(a2.REPORT.read_bytes())
    base.verify({**parent["input_SHA256"], **parent["source_SHA256"], **parent["sample_order_SHA256"]})
    drift = sorted(p for p, h in parent["ancestor_source_SHA256"].items()
                   if ledger.file_sha256(PROJECT_ROOT / p) != h)
    if drift != ["src\\asof\\sec_documentation.py", "src\\asof\\timeutil.py"]:
        raise ValueError(f"unreviewed ancestor source drift: {drift}")
    base.verify(parent_report["private_hash_manifest"])
    effective = effective_outcomes(ancestors())
    if len(effective) != parent_report["effective_unique_resource_outcomes"]:
        raise ValueError("ancestor merge differs from the A2 report")
    full = base.load_lines(a1.ORDER)
    inventory = base.load_lines(base.INVENTORY)
    again = {u: r["parsed"]["unknown"] for u, r in effective.items() if reeligible(r)}
    order = a3_order(inventory, full, effective)
    if len(order) != len(inventory) - len(effective) + len(again):
        raise ValueError("A3 order does not cover exactly the unrecorded and re-eligible resources")
    PRIVATE.mkdir()
    base.write_lines(ORDER, order)
    http = sum(r["proposed_HTTP_needed"] for r in order)
    value = {
        "kind": "APPROVED CL-TS-A3 pilot-then-full continuation with declared qualification rule",
        "approval": "ask_user timestamp_audit=pilot_then_full: 1,000-request pilot, full only if "
                    "the throttle rate is low; on 503 pause 10 minutes then resume slower; stop "
                    "permanently after 6 throttle pauses; metadata only.",
        "timing": "Frozen after base/A1/A2 outcomes were seen and BEFORE any A3 request or any "
                  "FILING-DATE analysis. Not a registration predating earlier metadata.",
        "scope": {"resources": len(order), "HTTP_needed": http, "pinned_cache_hits": len(order) - http,
                  "reeligible_prior_outcomes": dict(Counter(again.values())),
                  "counter_start": START_USED, "ceiling": CEILING,
                  "ceiling_shortfall_before_retries": max(0, http - (CEILING - START_USED)),
                  "order": "Re-eligible prior outcomes first in inventory order, then A1's frozen "
                           "order (seed 2026111603) of unrecorded resources; no completed refetch.",
                  "ceiling_tail": "Resources beyond the unchanged ceiling stay explicitly unread; "
                                  "any ceiling change needs separate approval."},
        "pacing": {"start_gap_seconds": START_GAP, "after_any_throttle_pause_gap_seconds": SLOW_GAP,
                   "full_start_gap": "0.667 if no earlier A3 throttle pause, else 1.0",
                   "request_timeout_seconds": 30, "connections": 1,
                   "body_bound_bytes": READ_CAP,
                   "body_bound_change": "Raised from 65,536 to the adapter's supported 4 MiB before "
                                        "any A3 request: 35/3,169 earlier outcomes (both kinds, all "
                                        "three phases) were unknown only because of the 64 KiB "
                                        "project bound; those 35 are re-eligible."},
        "error_policy": {
            "HTTP503_or429": "Pause 600 QPC seconds, retry the same URL at >=1.0s gap; repeat "
                             "while pauses remain. Pauses are capped at 6 across ALL A3 segments; "
                             "the next trigger stops permanently.",
            "transport_timeout_or_reset": "Wait 60s, retry once; a second transport failure "
                                          "records transport_unresolved (unknown) and continues. "
                                          "Stop after 3 consecutive transport_unresolved resources.",
            "unknowns": "404/at-cap remain unknown-continue, unchanged.",
            "immediate_stops": "403, other 5xx, redirects, other transport errors, scope, budget "
                               "or integrity failures, wall/disk/sleep.",
        },
        "pilot": {"charged_attempt_limit": PILOT_ATTEMPTS, "max_throttle_pauses": PILOT_MAX_PAUSES,
                  "wall_seconds": WALL["pilot"],
                  "gate": "Full runs only if the pilot stopped at its attempt limit or finished "
                          "the order, used <=1 throttle pause and had no other stop."},
        "full": {"wall_seconds_per_segment": WALL["full"], "segments": list(SEGMENTS[1:]),
                 "continuation": "A later segment may start only after the previous one recorded "
                                 "a wall-cap, sleep or transport-streak stop, with the same rules "
                                 "and the shared pause cap; never after a throttle-cap stop."},
        "clock_basis_CB1": {"rule": RULE, "population": "Every readable base/A1/A2 header",
                            "replication_CB1R": "Same rule on A3-retrieved headers; qualification "
                                                "requires CB1 passed and CB1-R not failed "
                                                "(non-estimable does not block)."},
        "qualification": {
            "qualified_UTC": "Eastern-civil conversion of the header wall when: clock basis "
                             "passed; every archive-path header and index read; one wall; "
                             "index wall equals header wall; unique DST conversion; inside the "
                             "frozen candidate envelope; filing date read, identical across paths "
                             "and consistent with the 17:30 cutoff.",
            "first_close": "Nominal 16:00 ET registered calendar, except acceptance in "
                           "[13:00,16:00) ET on a possible early-close date (Jul 2-3, Dec 23-24, "
                           "day after Thanksgiving) stays unresolved.",
            "identity": "Separate F7 classification of stored CIKs against observed header CIK "
                        "roles; not part of acceptance-time qualification.",
            "limits": "Assumes EDGAR's own clock was synchronized; no second-level UTC "
                      "verification. No timestamp, table or research input is rewritten.",
        },
        "User_Agent_SHA256": parent["User_Agent_SHA256"],
        "ancestor_source_drift_reviewed": {
            "files": drift,
            "review": "Since the A2 freeze, sec_documentation.py moved the same two allowed read "
                      "caps (64 KiB, 4 MiB) into a class attribute and timeutil.py gained an "
                      "unrelated aware_utc helper; no existing function changed. A3 pins the "
                      "current bytes of every module it executes instead."},
        "input_SHA256": {**parent["input_SHA256"], **parent_report["private_hash_manifest"],
                         **base.pin([a2.CONFIG, a2.REPORT])},
        "source_SHA256": base.pin(SOURCES), "order_SHA256": base.pin([ORDER]),
    }
    base.atomic_json(CONFIG, value)
    print(json.dumps({"frozen": value["scope"], "config_SHA256": ledger.file_sha256(CONFIG)}))


def committed_config() -> dict:
    config = json.loads(CONFIG.read_bytes())
    frozen_checks(config)
    lineage = ledger.lineage()
    if lineage["git_dirty"]:
        raise RuntimeError("commit the A3 freeze first")
    committed = subprocess.run(["git", "show", "HEAD:results/timestamp_full_a3_config.json"],
                               cwd=PROJECT_ROOT, capture_output=True, check=True).stdout
    if committed.replace(b"\r\n", b"\n") != CONFIG.read_bytes().replace(b"\r\n", b"\n"):
        raise RuntimeError("A3 config differs from the committed freeze")
    return config | {"_lineage": lineage}


def observations(rows: list[dict]) -> tuple[list[dict], dict]:
    output, map_ = [], {}
    for row in rows:
        if row["kind"] != "header" or "unknown" in row["parsed"]:
            continue
        try:
            obs = parse_header_dates(raw_resource_bytes(row, DATA_DIR, DIRECTORIES), row["accession"])
        except ValueError as exc:
            obs = {"unknown": f"raw_unavailable:{exc}"}
        output.append(obs)
        map_[row["URL"]] = obs
    return output, map_


def cb1() -> None:
    if CB1.exists():
        raise RuntimeError("CB1 already recorded; preserve it")
    config = committed_config()
    effective = effective_outcomes(ancestors())
    obs, _ = observations(list(effective.values()))
    result = clock_basis_test(obs)
    write_receipt(CB1, {"test": "CB1 declared header clock-basis test", "config_SHA256":
                        ledger.file_sha256(CONFIG), "lineage": config["_lineage"],
                        "headers_considered": len(obs), **result,
                        "data_boundary": "Metadata headers only; no HTTP request in this phase."})
    print(json.dumps({k: result[k] for k in ("evaluated_headers", "fixed_EST_rejected",
                                             "UTC_rejected", "integrity_passed", "passed")}))


class A3Guard(AuditGuard):
    def check(self) -> None:
        try:
            super().check()
        except DocumentationStop as exc:
            if str(exc) == "metadata_12h_wall_cap":
                raise DocumentationStop("A3_wall_cap") from exc
            raise


def keep_awake(on: bool) -> None:
    if os.name == "nt":
        flags = 0x80000000 | (0x00000001 if on else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)


async def run(segment: str) -> None:
    config = committed_config()
    if not CB1.exists():
        raise RuntimeError("CB1 must be recorded before any A3 request")
    private = PRIVATE / segment
    status_file = status_path(segment)
    if private.exists() or status_file.exists():
        raise RuntimeError(f"A3 {segment} already attempted; no automatic continuation")
    index = SEGMENTS.index(segment)
    prior_status = [json.loads(status_path(s).read_bytes()) for s in SEGMENTS[:index]]
    if segment != "pilot":
        if not GATE.exists() or json.loads(GATE.read_bytes())["gate_passed"] is not True:
            raise RuntimeError("pilot gate did not pass; full audit not authorized")
        if index > 1 and prior_status[-1].get("stop_reason") not in (
                "A3_wall_cap", "host_sleep_or_suspend_no_automatic_resume", "transport_unresolved_streak"):
            raise RuntimeError("continuation allowed only after a wall, sleep or transport-streak stop")
    pauses_before = sum(s["throttle_pauses"] for s in prior_status)
    charged_before = sum(s["charged"] for s in prior_status)
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": START_USED + charged_before,
                                                "ceiling": CEILING}:
        raise ValueError("shared counter differs from recorded A3 charges")
    if hashlib.sha256(user_agent().encode()).hexdigest() != config["User_Agent_SHA256"]:
        raise ValueError("declared User-Agent changed")
    done = effective_outcomes(a3_segments())
    order = [r for r in base.load_lines(ORDER) if r["URL"] not in done or str(
        done[r["URL"]]["parsed"].get("unknown", "")).startswith("resource_failed:")]
    max_pauses = PILOT_MAX_PAUSES if segment == "pilot" else MAX_THROTTLE_PAUSES - pauses_before
    if max_pauses <= 0 and segment != "pilot":
        raise RuntimeError("shared throttle-pause cap already used")
    private.mkdir(parents=True)
    outcomes, requests, events = (private / n for n in (
        "resource_outcomes.jsonl", "requests.jsonl", "waits_and_retries.jsonl"))
    static = sum(p.stat().st_size for d in (base.PRIVATE, a1.PRIVATE, a2.PRIVATE, PRIVATE)
                 for p in d.rglob("*") if p.is_file())
    session: A3Session | None = None

    def storage() -> int:
        return static + (session.allocated_bytes if session else 0) + sum(
            p.stat().st_size for p in (requests, events, outcomes) if p.exists())

    wall = WALL["pilot" if segment == "pilot" else "full"]
    guard = A3Guard(base.suspend_clocks, storage, wall_seconds=wall)
    status = {"segment": segment, "status": "in_progress", "commit": config["_lineage"]["git_commit"],
              "start_UTC": datetime.now(UTC).isoformat(), "wall_cap_seconds": wall,
              "counter_start": START_USED + charged_before, "resources_recorded": 0, "charged": 0,
              "throttle_pauses": 0, "throttle_pauses_before": pauses_before,
              "max_throttle_pauses": max_pauses, "transport_unresolved": 0,
              "sleep_interruptions": guard.interruptions, "config_SHA256": ledger.file_sha256(CONFIG)}

    def checkpoint(event: dict | None = None) -> None:
        if event:
            status["latest_wait_event"] = {k: v for k, v in event.items() if k != "url"}
        if session:
            status.update(charged=session.charged, throttle_pauses=session.throttle_pauses,
                          gap_seconds=session.limiter.gap)
        for path in (outcomes, requests, events):
            if path.exists():
                with path.open("ab") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
        status.update(counter=json.loads(base.BUDGET.read_bytes()),
                      wall_seconds=time.monotonic() - guard.started,
                      disk_bytes_observed=storage(), checkpoint_UTC=datetime.now(UTC).isoformat())
        base.atomic_json(status_file, status)
        print(json.dumps({k: status.get(k) for k in (
            "segment", "status", "resources_recorded", "charged", "throttle_pauses",
            "counter", "wall_seconds")}), flush=True)

    keep_awake(True)
    checkpoint()
    limiter = AdaptiveLimiter(gap=START_GAP if pauses_before == 0 else SLOW_GAP)
    streak = 0
    try:
        async with A3Session(
                {r["URL"] for r in order if r["proposed_HTTP_needed"]}, base.BUDGET, private, guard,
                start_used=START_USED + charged_before, max_pauses=max_pauses,
                attempt_limit=PILOT_ATTEMPTS if segment == "pilot" else None,
                limiter=limiter, on_event=checkpoint) as session:
            for resource in order:
                guard.check()
                if segment == "pilot" and session.charged >= PILOT_ATTEMPTS:
                    raise DocumentationStop("pilot_attempt_limit_reached")
                item = {**resource, "cache_hit": not resource["proposed_HTTP_needed"],
                        "A3_segment": segment}
                stop = None
                session.current_attempts = []
                try:
                    if item["cache_hit"]:
                        raw = raw_resource_bytes(item, DATA_DIR, DIRECTORIES)
                        if len(raw) >= READ_CAP:
                            raise MetadataUnknown("cached_metadata_at_read_cap")
                    else:
                        raw = await session.fetch(item["URL"])
                    parsed = (base.parse_header(raw, item["accession"]) if item["kind"] == "header"
                              else base.parse_index(raw))
                    candidate = parsed.get("UTC_assuming_Eastern")
                    if candidate and not "2022-01-01" <= candidate[:10] < "2024-07-01":
                        raise DocumentationStop("header_outside_frozen_metadata_date_scope")
                    item["parsed"] = parsed
                    streak = 0
                except MetadataUnknown as exc:
                    item["parsed"] = {"unknown": str(exc)}
                    if str(exc).startswith("transport_unresolved:"):
                        status["transport_unresolved"] += 1
                        streak += 1
                        if streak >= MAX_CONSECUTIVE_UNRESOLVED:
                            stop = "transport_unresolved_streak"
                    else:
                        streak = 0
                except (DocumentationStop, OSError, ValueError) as exc:
                    item["parsed"] = {"unknown": f"resource_failed:{exc}"}
                    stop = str(exc)
                item["A3_attempts"] = list(session.current_attempts)
                with outcomes.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(item, allow_nan=False) + "\n")
                status["resources_recorded"] += 1
                if stop:
                    raise DocumentationStop(stop)
                if status["resources_recorded"] % 500 == 0:
                    frozen_checks(config)
                    checkpoint()
        status["status"] = "order_complete"
    except (DocumentationStop, OSError, ValueError) as exc:
        status.update(status="stopped_final", stop_reason=str(exc))
    finally:
        if status["status"] == "in_progress":
            error = sys.exception()
            status.update(status="interrupted_final", stop_reason=(
                f"{type(error).__name__}:{error}" if error else "unexpected_interruption"))
        checkpoint()
        keep_awake(False)
    if segment == "pilot":
        clean = status["status"] == "order_complete" or status.get("stop_reason") == "pilot_attempt_limit_reached"
        gate = {"gate_passed": clean and status["throttle_pauses"] <= PILOT_MAX_PAUSES,
                "pilot_status": status["status"], "stop_reason": status.get("stop_reason"),
                "charged": status["charged"], "throttle_pauses": status["throttle_pauses"],
                "transport_unresolved": status["transport_unresolved"],
                "rule": config["pilot"]["gate"], "status_SHA256": ledger.file_sha256(status_file)}
        write_receipt(GATE, gate)
        print(json.dumps(gate), flush=True)


def report() -> None:
    if REPORT.exists() or TABLE.exists():
        raise RuntimeError("A3 report already exists; preserve it")
    config = committed_config()
    cb1_value = json.loads(CB1.read_bytes())
    segments = a3_segments()
    effective = effective_outcomes([*ancestors(), *segments])
    inventory, roster = base.load_lines(base.INVENTORY), base.load_lines(base.ROSTER)
    groups = defaultdict(list)
    for resource in inventory:
        groups[resource["accession"]].append(effective.get(resource["URL"], {
            **resource, "parsed": {"unknown": "not_attempted_after_A3_final_stop"}}))
    _, header_obs = observations(list(effective.values()))
    a3_headers = [header_obs[r["URL"]] for seg in segments for r in seg
                  if r["URL"] in header_obs and effective[r["URL"]] is r]
    replication = clock_basis_test(a3_headers)
    estimable = replication["S1_daylight_16_30_to_17_30_same_day"]["n"] >= 30
    replication_failed = estimable and not replication["passed"]
    basis = bool(cb1_value["passed"]) and not replication_failed
    rows, table = [], []
    for record in roster:
        resources = groups[record["accession"]]
        row = base.accession_result(record, resources)
        headers = [header_obs.get(r["URL"], {"unknown": r["parsed"].get("unknown", "unread")})
                   for r in resources if r["kind"] == "header"]
        result = qualify(row, headers, basis)
        identity = identity_class(row)
        rows.append({**row, "conditional_UTC_assuming_Eastern": result["qualified_UTC"],
                     "outside_frozen_candidate_envelope": False})
        table.append({**{k: row[k] for k in ("accession", "pool", "cik_pair", "cik_bulk",
                                              "API_time_stored_pair", "bulk_time", "header_wall",
                                              "index_wall", "agreement_class")},
                      **result, "identity_class": identity})
    occupied = sum(p.stat().st_size for d in (base.PRIVATE, a1.PRIVATE, a2.PRIVATE, PRIVATE)
                   for p in d.rglob("*") if p.is_file())
    if occupied + sum(len(json.dumps(r)) + 1 for r in table) + (64 << 20) >= DISK_BYTES:
        raise DocumentationStop("A3_final_report_disk_budget")
    base.write_lines(TABLE, table)
    qualified = {r["accession"]: r["qualified_UTC"] for r in table if r["qualified_UTC"]}
    calendar = json.loads(base.CALENDAR.read_bytes())
    closes = [datetime.fromisoformat(t) for t in calendar["closes"]]
    universe = base.load_lines(base.UNIVERSE)
    required = {r["accession"] for r in roster}
    assignments = base.assignment_counts(
        universe, rows, closes, [datetime.fromisoformat(t) for t in calendar["formations"]],
        datetime.fromisoformat(calendar["start"]), datetime.fromisoformat(calendar["end"]))
    statuses = [json.loads(status_path(s).read_bytes()) for s in SEGMENTS if status_path(s).exists()]
    logs = [r for s in SEGMENTS if (PRIVATE / s / "requests.jsonl").exists()
            for r in base.load_lines(PRIVATE / s / "requests.jsonl")]
    starts = [r for r in logs if r["event"] == "started"]
    finishes = [r for r in logs if r["event"] == "finished" and r["attempted"]]
    sends = [r for r in logs if r["event"] == "send"]
    used = json.loads(base.BUDGET.read_bytes())["actual_HTTP_attempts"]
    if [r["historical_attempt"] for r in starts] != list(range(START_USED + 1, used + 1)):
        raise ValueError("A3 budget/receipt mismatch")
    gaps = [b["send_perf_counter"] - a["send_perf_counter"] for a, b in pairwise(sends)]
    events = [{**{k: v for k, v in e.items() if k != "url"},
               "URL_SHA256": hashlib.sha256(e["url"].encode()).hexdigest()}
              for s in SEGMENTS if (PRIVATE / s / "waits_and_retries.jsonl").exists()
              for e in base.load_lines(PRIVATE / s / "waits_and_retries.jsonl")]
    manifests = []
    for segment in (s for s in SEGMENTS if (PRIVATE / s).exists()):
        for sub, name in (("raw_metadata", "raw_hashes.jsonl"), ("attempt_receipts", "receipt_hashes.jsonl")):
            manifest = PRIVATE / segment / name
            base.write_lines(manifest, [
                {"path": str(p.relative_to(PRIVATE / segment)), "bytes": p.stat().st_size,
                 "SHA256": ledger.file_sha256(p)} for p in sorted((PRIVATE / segment / sub).glob("*"))])
            manifests.append(manifest)
    reasons = Counter(reason for r in table for reason in r["unresolved_reasons"])
    by_pool = defaultdict(Counter)
    for r in table:
        by_pool[r["pool"]]["accessions"] += 1
        by_pool[r["pool"]]["qualified"] += bool(r["qualified_UTC"])
        by_pool[r["pool"]][f"identity:{r['identity_class']}"] += 1
        if r["qualified_UTC"]:
            stamp = datetime.fromisoformat(r["qualified_UTC"])
            match = (stamp == datetime.fromisoformat(r["API_time_stored_pair"]),
                     stamp == datetime.fromisoformat(r["bulk_time"]))
            by_pool[r["pool"]][{(True, True): "qualified_equals_both", (True, False): "equals_pair_only",
                                (False, True): "equals_bulk_only",
                                (False, False): "equals_neither"}[match]] += 1
    value = {
        "status": [{k: s.get(k) for k in ("segment", "status", "stop_reason", "charged",
                                          "throttle_pauses", "transport_unresolved")} for s in statuses],
        "config_SHA256": ledger.file_sha256(CONFIG), "report_lineage": config["_lineage"],
        "clock_basis": {"CB1_passed": cb1_value["passed"], "CB1_SHA256": ledger.file_sha256(CB1),
                        "CB1R_replication": replication, "CB1R_estimable": estimable,
                        "basis_accepted_for_qualification": basis},
        "qualified_UTC": len(qualified), "unresolved_accessions": len(table) - len(qualified),
        "required_accessions": len(table), "unresolved_reason_counts": dict(reasons),
        "filing_date_consistency": dict(Counter(r["filing_date_consistency"] for r in table)),
        "first_close_status": dict(Counter(r["first_close_status"] for r in table)),
        "by_pool": {k: dict(v) for k, v in sorted(by_pool.items())},
        "first_close_direction": first_close_direction(
            [r for r in universe if r["accession"] in required], qualified, closes),
        "eligibility_and_latest_filing_vs_qualified": assignments["conditional_diagnostics_only"],
        "A3_attempts": len(starts), "A3_HTTP_status_counts": dict(Counter(str(r["status"]) for r in finishes)),
        "A3_retries_charged": sum(bool(r.get("A3_retry")) for r in starts),
        "every_wait_and_retry": events,
        "counter": {"actual_HTTP_attempts": used, "ceiling": CEILING},
        "effective_unique_resource_outcomes": len(effective),
        "resources_never_attempted": len(inventory) - len(effective),
        "QPC_rate": {"sends": len(sends), "minimum_gap_seconds": min(gaps) if gaps else None,
                     "median_gap_seconds": statistics.median(gaps) if gaps else None},
        "private_hash_manifest": base.pin([p for p in (
            ORDER, TABLE, *manifests, *(PRIVATE / s / n for s in SEGMENTS for n in (
                "resource_outcomes.jsonl", "requests.jsonl", "waits_and_retries.jsonl"))) if p.exists()]),
        "limits": "Qualification assumes EDGAR's own clock was synchronized and the declared "
                  "Rule 13(a)(2) basis; it is not second-level UTC verification. Identity is "
                  "reported, not adjudicated. Direction counts compare stored inputs with "
                  "qualified times; no timestamp, table, signal, price, return or ledger row "
                  "was changed and no holdout data was read.",
    }
    base.atomic_json(REPORT, value)
    print(json.dumps({"qualified_UTC": value["qualified_UTC"],
                      "unresolved": value["unresolved_accessions"],
                      "basis": value["clock_basis"]["basis_accepted_for_qualification"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "cb1", "run", "report"))
    parser.add_argument("segment", nargs="?", choices=SEGMENTS)
    args = parser.parse_args()
    if any(os.environ.get(k) != "1" for k in
           ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("set numerical library thread caps to 1")
    if args.phase == "freeze":
        freeze()
    elif args.phase == "cb1":
        cb1()
    elif args.phase == "run":
        if not args.segment:
            raise SystemExit("run requires a segment")
        asyncio.run(run(args.segment))
    else:
        report()
