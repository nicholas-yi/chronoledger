"""A4: approved continuation of the timestamp audit plus F7 identity fetches.

Phases (each refuses to repeat): ``freeze`` -> commit -> ``run seg1`` (later segments only
after a recorded wall, sleep or transport-streak stop) -> ``report``. Metadata only: no
price, return, signal, ledger or holdout access.
"""

from __future__ import annotations

import argparse
import asyncio
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

import pandas as pd
import run_full_timestamps as base
import run_full_timestamps_a1 as a1
import run_full_timestamps_a2 as a2
import run_full_timestamps_a3 as a3
from timestamp_a3_impact import impact

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, user_agent
from asof.filing_clock_basis import clock_basis_test, parse_header_dates, qualify
from asof.filing_header_pilot import parse_header, resource_urls
from asof.filing_timestamp_a3 import (
    MAX_CONSECUTIVE_UNRESOLVED,
    READ_CAP,
    AdaptiveLimiter,
    effective_outcomes,
    raw_resource_bytes,
)
from asof.filing_timestamp_a4 import (
    CEILING,
    GATEWAY_WAIT,
    MAX_COUNTED_PAUSES,
    PREVIOUS_CEILING,
    RATE_LIMIT,
    RATE_WINDOW,
    A4Session,
    a4_raw_bytes,
    identity_decision,
    segment_allowance,
)
from asof.filing_timestamp_audit import DISK_BYTES
from asof.sec_documentation import DocumentationStop, MetadataUnknown

START_USED = 6054
CONFIG = PROJECT_ROOT / "results" / "timestamp_full_a4_config.json"
REPORT = PROJECT_ROOT / "results" / "timestamp_full_a4_report.json"
PRIVATE = DATA_DIR / "timestamp_full_a4"
ORDER = PRIVATE / "frozen_order.jsonl"
TABLE = PRIVATE / "qualified_per_accession.jsonl"
IDENTITY = PRIVATE / "F7_identity_per_accession.jsonl"
UNIVERSE_PRICES = DATA_DIR / "h0_universe.parquet"
SEGMENTS = ("seg1", "seg2", "seg3")
WALL = 50400
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "filing_timestamp_a4.py",
           PROJECT_ROOT / "scripts" / "timestamp_a3_impact.py",
           PROJECT_ROOT / "tests" / "test_filing_timestamp_a4.py"]
SEGMENT_DIRS = {s: PRIVATE / s for s in SEGMENTS}


def status_path(segment: str) -> Path:
    return PROJECT_ROOT / "results" / f"timestamp_full_a4_{segment}_status.json"


def a4_segments() -> list[list[dict]]:
    return [base.load_lines(PRIVATE / s / "resource_outcomes.jsonl") for s in SEGMENTS
            if (PRIVATE / s / "resource_outcomes.jsonl").exists()]


def raw(row: dict) -> bytes:
    return a4_raw_bytes(row, SEGMENT_DIRS, lambda r: raw_resource_bytes(r, DATA_DIR, a3.DIRECTORIES))


def frozen_checks(config: dict) -> None:
    base.verify({**config["input_SHA256"], **config["source_SHA256"], **config["order_SHA256"]})


def freeze() -> None:
    if CONFIG.exists() or PRIVATE.exists():
        raise RuntimeError("A4 already frozen; preserve it")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": START_USED,
                                                "ceiling": PREVIOUS_CEILING}:
        raise ValueError("A4 starts at the recorded A3 stop, 6054 of 34402")
    a3_config = json.loads(a3.CONFIG.read_bytes())
    a3.frozen_checks(a3_config)
    a3_report = json.loads(a3.REPORT.read_bytes())
    base.verify(a3_report["private_hash_manifest"])
    effective = effective_outcomes([*a3.ancestors(), *a3.a3_segments()])
    remaining = [{**r, "purpose": "timestamp"} for r in base.load_lines(a3.ORDER)
                 if r["URL"] not in effective
                 or str(effective[r["URL"]]["parsed"].get("unknown", "")).startswith("resource_failed:")]
    roster = {r["accession"] for r in base.load_lines(base.ROSTER)}
    f7 = [{"purpose": "F7_identity", "accession": r["accession"], "kind": "header",
           "cik_pair": r["cik_pair"], "cik_bulk": r["cik_bulk"],
           "URL": resource_urls(r["cik_pair"], r["accession"])["header"],
           "fallback_URL": resource_urls(r["cik_bulk"], r["accession"])["header"],
           "proposed_HTTP_needed": True}
          for r in base.load_lines(base.UNIVERSE) if not r["CIKs_agree"] and r["accession"] not in roster]
    order = [{**r, "a4_order": i} for i, r in enumerate(f7 + remaining)]
    http = sum(r["proposed_HTTP_needed"] for r in order)
    PRIVATE.mkdir()
    base.write_lines(ORDER, order)
    value = {
        "kind": "APPROVED CL-TS-A4 continuation: short gateway retries, ceiling 35,000, F7 identity",
        "approval": "ask_user 2026-11-20 after the A3 pause-cap stop: gateway_policy=short_retry, "
                    "ceiling=35000, f7_identity=true. Metadata only.",
        "timing": "Frozen after A3 results were seen and before any A4 request. Acquisition and "
                  "identity rules are post-A3 decisions; the A3 qualification rule is unchanged.",
        "scope": {"resources": len(order), "HTTP_primary": http, "F7_accessions": len(f7),
                  "F7_max_fallback_requests": len(f7), "timestamp_resources": len(remaining),
                  "counter_start": START_USED, "ceiling": CEILING, "previous_ceiling": PREVIOUS_CEILING,
                  "retry_margin_before_fallbacks": CEILING - START_USED - http,
                  "order": "F7 headers first (pair-CIK path), then A3's frozen order of resources "
                           "never recorded or resource_failed. No completed refetch."},
        "policy": {
            "HTTP_502_or_504": f"First occurrence on a URL: wait {GATEWAY_WAIT}s and retry, not "
                               "counted. A repeat on the same URL: counted 600s pause.",
            "HTTP_503_or_429": "Counted 600s pause, then retry; gap becomes 1.0s.",
            "counted_pause_cap": f"{MAX_COUNTED_PAUSES} across all A4 segments; the next one stops.",
            "gateway_rate_stop": f"Stop when the last {RATE_WINDOW} charged attempts hold more "
                                 f"than {RATE_LIMIT} gateway errors (3%).",
            "transport": "Unchanged from A3: 60s, one retry, then transport_unresolved unknown; "
                         "three in a row stop.",
            "pacing": "0.667s minimum gap; 1.0s after any counted pause. Wall 14h per segment.",
            "unchanged_stops": "403, 500, 501, other 5xx, redirects, other transport errors, "
                               "scope, budget, integrity, disk, sleep.",
        },
        "F7_identity_rule": "For every universe CIK-disagreement accession: read the header "
                            "(F7 fetch, pair-CIK path, falling back to the bulk-CIK path only "
                            "on 404; or the A3 header). Qualified when the header lists both "
                            "stored CIKs and exactly one of them, the pair CIK, is in the frozen "
                            "price universe. Other classes are reported, not repaired.",
        "report_rule": "Same A3 qualification rule and CB1 basis; additionally the A4 headers "
                       "must not fail a CB1 replication when estimable (n>=30 in S1). Impact uses "
                       "the declared timestamp_a3_impact functions on all qualified accessions.",
        "budget_change": {"before": {"actual_HTTP_attempts": START_USED, "ceiling": PREVIOUS_CEILING},
                          "after": {"actual_HTTP_attempts": START_USED, "ceiling": CEILING}},
        "User_Agent_SHA256": a3_config["User_Agent_SHA256"],
        "input_SHA256": {**a3_report["private_hash_manifest"],
                         **base.pin([a3.CONFIG, a3.AMENDMENT, a3.REPORT, UNIVERSE_PRICES])},
        "source_SHA256": {**a3_config["source_SHA256"],
                          **json.loads(a3.AMENDMENT.read_bytes())["source_SHA256"],
                          **base.pin(SOURCES)},
        "order_SHA256": base.pin([ORDER]),
    }
    base.atomic_json(CONFIG, value)
    base.atomic_json(base.BUDGET, value["budget_change"]["after"])
    print(json.dumps({"frozen": value["scope"], "config_SHA256": ledger.file_sha256(CONFIG)}))


def committed_config() -> dict:
    config = json.loads(CONFIG.read_bytes())
    frozen_checks(config)
    lineage = ledger.lineage()
    if lineage["git_dirty"]:
        raise RuntimeError("commit the A4 freeze first")
    committed = subprocess.run(["git", "show", "HEAD:results/timestamp_full_a4_config.json"],
                               cwd=PROJECT_ROOT, capture_output=True, check=True).stdout
    if committed.replace(b"\r\n", b"\n") != CONFIG.read_bytes().replace(b"\r\n", b"\n"):
        raise RuntimeError("A4 config differs from the committed freeze")
    return config | {"_lineage": lineage}


async def run(segment: str) -> None:
    config = committed_config()
    private, status_file = PRIVATE / segment, status_path(segment)
    if private.exists() or status_file.exists():
        raise RuntimeError(f"A4 {segment} already attempted; no automatic continuation")
    prior = [json.loads(status_path(s).read_bytes()) for s in SEGMENTS[:SEGMENTS.index(segment)]]
    if len(prior) != SEGMENTS.index(segment):
        raise RuntimeError("earlier A4 segments must be recorded first")
    allowance = segment_allowance(prior)
    charged_before = sum(s["charged"] for s in prior)
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": START_USED + charged_before,
                                                "ceiling": CEILING}:
        raise ValueError("shared counter differs from recorded A4 charges")
    if hashlib.sha256(user_agent().encode()).hexdigest() != config["User_Agent_SHA256"]:
        raise ValueError("declared User-Agent changed")
    done = effective_outcomes(a4_segments())
    order = [r for r in base.load_lines(ORDER) if r["URL"] not in done or str(
        done[r["URL"]]["parsed"].get("unknown", "")).startswith("resource_failed:")]
    private.mkdir(parents=True)
    outcomes, requests, events = (private / n for n in (
        "resource_outcomes.jsonl", "requests.jsonl", "waits_and_retries.jsonl"))
    static = sum(p.stat().st_size for d in (base.PRIVATE, a1.PRIVATE, a2.PRIVATE, a3.PRIVATE, PRIVATE)
                 for p in d.rglob("*") if p.is_file())
    session: A4Session | None = None

    def storage() -> int:
        return static + (session.allocated_bytes if session else 0) + sum(
            p.stat().st_size for p in (requests, events, outcomes) if p.exists())

    guard = a3.A3Guard(base.suspend_clocks, storage, wall_seconds=WALL)
    status = {"segment": segment, "status": "in_progress", "commit": config["_lineage"]["git_commit"],
              "start_UTC": datetime.now(UTC).isoformat(), "wall_cap_seconds": WALL,
              "counter_start": START_USED + charged_before, "resources_recorded": 0, "charged": 0,
              "throttle_pauses": 0, "throttle_pauses_before": allowance["pauses_before"],
              "max_throttle_pauses": allowance["max_pauses"], "short_gateway_retries": 0,
              "transport_unresolved": 0, "F7_fallbacks": 0,
              "sleep_interruptions": guard.interruptions, "config_SHA256": ledger.file_sha256(CONFIG)}

    def checkpoint(event: dict | None = None) -> None:
        if event:
            status["latest_wait_event"] = {k: v for k, v in event.items() if k != "url"}
        if session:
            status.update(charged=session.charged, throttle_pauses=session.throttle_pauses,
                          short_gateway_retries=session.short_gateway_retries,
                          gateway_errors_in_window=sum(session.window), gap_seconds=session.limiter.gap)
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
            "short_gateway_retries", "counter", "wall_seconds")}), flush=True)

    a3.keep_awake(True)
    checkpoint()
    allowed = {r["URL"] for r in order if r["proposed_HTTP_needed"]} | {
        r["fallback_URL"] for r in order if r["purpose"] == "F7_identity"}
    streak = 0
    try:
        async with A4Session(allowed, base.BUDGET, private, guard, start_used=START_USED + charged_before,
                             max_pauses=allowance["max_pauses"],
                             limiter=AdaptiveLimiter(gap=allowance["start_gap"]),
                             on_event=checkpoint) as session:
            for resource in order:
                guard.check()
                item = {**resource, "cache_hit": not resource["proposed_HTTP_needed"], "A4_segment": segment}
                stop = None
                session.current_attempts = []
                try:
                    if item["cache_hit"]:
                        body = raw_resource_bytes(item, DATA_DIR, a3.DIRECTORIES)
                        if len(body) >= READ_CAP:
                            raise MetadataUnknown("cached_metadata_at_read_cap")
                    elif item["purpose"] == "F7_identity":
                        try:
                            body = await session.fetch(item["URL"])
                        except MetadataUnknown as exc:
                            if str(exc) != "HTTP_404":
                                raise
                            item["fallback_used"] = True
                            status["F7_fallbacks"] += 1
                            body = await session.fetch(item["fallback_URL"])
                    else:
                        body = await session.fetch(item["URL"])
                    if item["purpose"] == "F7_identity":
                        parsed = parse_header(body, item["accession"])
                    else:
                        parsed = (base.parse_header(body, item["accession"]) if item["kind"] == "header"
                                  else base.parse_index(body))
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
                item["A4_attempts"] = list(session.current_attempts)
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
        reason = str(exc)
        status.update(status="stopped_final",
                      stop_reason="A4_wall_cap" if reason == "A3_wall_cap" else reason)
    finally:
        if status["status"] == "in_progress":
            error = sys.exception()
            status.update(status="interrupted_final", stop_reason=(
                f"{type(error).__name__}:{error}" if error else "unexpected_interruption"))
        checkpoint()
        a3.keep_awake(False)


def header_observations(rows: list[dict]) -> dict[str, dict]:
    output = {}
    for row in rows:
        if row["kind"] != "header" or "unknown" in row["parsed"]:
            continue
        try:
            output[row["URL"]] = parse_header_dates(raw(row), row["accession"])
        except ValueError as exc:
            output[row["URL"]] = {"unknown": f"raw_unavailable:{exc}"}
    return output


def report() -> None:
    if REPORT.exists() or TABLE.exists():
        raise RuntimeError("A4 report already exists; preserve it")
    config = committed_config()
    a3_report = json.loads(a3.REPORT.read_bytes())
    segments = a4_segments()
    timestamp_rows = [[r for r in seg if r["purpose"] == "timestamp"] for seg in segments]
    f7_rows = {r["accession"]: r for seg in segments for r in seg if r["purpose"] == "F7_identity"}
    effective = effective_outcomes([*a3.ancestors(), *a3.a3_segments(), *timestamp_rows])
    inventory, roster = base.load_lines(base.INVENTORY), base.load_lines(base.ROSTER)
    groups = defaultdict(list)
    for resource in inventory:
        groups[resource["accession"]].append(effective.get(resource["URL"], {
            **resource, "parsed": {"unknown": "not_attempted_after_A4_final_stop"}}))
    header_obs = header_observations(list(effective.values()))
    a4_headers = [header_obs[r["URL"]] for seg in timestamp_rows for r in seg
                  if r["URL"] in header_obs and effective[r["URL"]] is r]
    replication = clock_basis_test(a4_headers)
    estimable = replication["S1_daylight_16_30_to_17_30_same_day"]["n"] >= 30
    basis = bool(a3_report["clock_basis"]["basis_accepted_for_qualification"]) and not (
        estimable and not replication["passed"])
    rows, table = [], []
    for record in roster:
        resources = groups[record["accession"]]
        row = base.accession_result(record, resources)
        headers = [header_obs.get(r["URL"], {"unknown": r["parsed"].get("unknown", "unread")})
                   for r in resources if r["kind"] == "header"]
        result = qualify(row, headers, basis)
        rows.append(row)
        table.append({**{k: row[k] for k in ("accession", "pool", "cik_pair", "cik_bulk",
                                              "API_time_stored_pair", "bulk_time", "header_wall",
                                              "index_wall", "agreement_class")}, **result})
    listed = set(pd.read_parquet(UNIVERSE_PRICES)["cik"].astype(int))
    by_accession = {r["accession"]: r for r in rows}
    identity = []
    for record in base.load_lines(base.UNIVERSE):
        if record["CIKs_agree"]:
            continue
        accession = record["accession"]
        if accession in by_accession:
            notes = by_accession[accession]["CIK_role_notes"]
            ciks = None if any(n.get("unknown") for n in notes) or not notes else {
                int(c) for n in notes for values in n["observed_roles"].values() for c in values}
            source = "A1-A4 audit header"
        else:
            row = f7_rows.get(accession)
            parsed = row["parsed"] if row else {"unknown": "not_fetched"}
            ciks = None if "unknown" in parsed else {
                int(c) for values in parsed["header_CIKs_by_role"].values() for c in values}
            source = "A4 F7 header" + (" (bulk-CIK path fallback)" if row and row.get("fallback_used") else "")
        identity.append({"accession": accession, "cik_pair": record["cik_pair"],
                         "cik_bulk": record["cik_bulk"], "source": source,
                         "decision": identity_decision(record["cik_pair"], record["cik_bulk"], ciks, listed)})
    occupied = sum(p.stat().st_size for d in (base.PRIVATE, a1.PRIVATE, a2.PRIVATE, a3.PRIVATE, PRIVATE)
                   for p in d.rglob("*") if p.is_file())
    if occupied + sum(len(json.dumps(r)) + 1 for r in table + identity) + (64 << 20) >= DISK_BYTES:
        raise DocumentationStop("A4_final_report_disk_budget")
    base.write_lines(TABLE, table)
    base.write_lines(IDENTITY, identity)
    calendar = json.loads(base.CALENDAR.read_bytes())
    closes = [datetime.fromisoformat(t) for t in calendar["closes"]]
    universe = base.load_lines(base.UNIVERSE)
    qualified = [r for r in table if r["qualified_UTC"]]
    statuses = [json.loads(status_path(s).read_bytes()) for s in SEGMENTS if status_path(s).exists()]
    logs = [r for s in SEGMENTS if (PRIVATE / s / "requests.jsonl").exists()
            for r in base.load_lines(PRIVATE / s / "requests.jsonl")]
    starts = [r for r in logs if r["event"] == "started"]
    finishes = [r for r in logs if r["event"] == "finished" and r["attempted"]]
    used = json.loads(base.BUDGET.read_bytes())["actual_HTTP_attempts"]
    if [r["historical_attempt"] for r in starts] != list(range(START_USED + 1, used + 1)):
        raise ValueError("A4 budget/receipt mismatch")
    gaps = {}
    for s in SEGMENTS:
        if (PRIVATE / s / "requests.jsonl").exists():
            sends = [r["send_perf_counter"] for r in base.load_lines(PRIVATE / s / "requests.jsonl")
                     if r["event"] == "send"]
            values = [b - a for a, b in pairwise(sends)]
            gaps[s] = {"sends": len(sends), "minimum_gap_seconds": min(values) if values else None,
                       "median_gap_seconds": statistics.median(values) if values else None}
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
    by_pool = defaultdict(Counter)
    for r in table:
        by_pool[r["pool"]]["accessions"] += 1
        by_pool[r["pool"]]["qualified"] += bool(r["qualified_UTC"])
    value = {
        "status": [{k: s.get(k) for k in ("segment", "status", "stop_reason", "charged", "throttle_pauses",
                                          "short_gateway_retries", "transport_unresolved", "F7_fallbacks")}
                   for s in statuses],
        "config_SHA256": ledger.file_sha256(CONFIG), "report_lineage": config["_lineage"],
        "clock_basis": {"A3_basis_accepted": a3_report["clock_basis"]["basis_accepted_for_qualification"],
                        "CB1R2_replication_on_A4_headers": replication, "CB1R2_estimable": estimable,
                        "basis_accepted_for_qualification": basis},
        "qualified_UTC": len(qualified), "unresolved_accessions": len(table) - len(qualified),
        "required_accessions": len(table),
        "unresolved_reason_counts": dict(Counter(x for r in table for x in r["unresolved_reasons"])),
        "filing_date_consistency": dict(Counter(r["filing_date_consistency"] for r in table)),
        "first_close_status": dict(Counter(r["first_close_status"] for r in table)),
        "by_pool": {k: dict(v) for k, v in sorted(by_pool.items())},
        "impact_first_close_direction": impact(universe, table, closes),
        "F7_identity": {"universe_disagreements": len(identity),
                        "decisions": dict(Counter(r["decision"] for r in identity)),
                        "by_source": dict(Counter(r["source"] for r in identity))},
        "A4_attempts": len(starts),
        "A4_HTTP_status_counts": dict(Counter(str(r["status"]) for r in finishes)),
        "A4_retries_charged": sum(bool(r.get("A4_retry")) for r in starts),
        "every_wait_and_retry": events,
        "counter": {"actual_HTTP_attempts": used, "ceiling": CEILING},
        "effective_unique_resource_outcomes": len(effective),
        "resources_never_attempted": len(inventory) - len(effective),
        "QPC_rate_by_segment": gaps,
        "private_hash_manifest": base.pin([p for p in (
            ORDER, TABLE, IDENTITY, *manifests, *(PRIVATE / s / n for s in SEGMENTS for n in (
                "resource_outcomes.jsonl", "requests.jsonl", "waits_and_retries.jsonl"))) if p.exists()]),
        "limits": "Qualification assumes EDGAR's own clock was synchronized and the declared "
                  "Rule 13(a)(2) basis. Identity names which stored CIK is the listed security "
                  "of a co-filed accession; it is not historical security-master verification. "
                  "No timestamp, table, signal, price, return or ledger row was changed and no "
                  "holdout data was read.",
    }
    base.atomic_json(REPORT, value)
    print(json.dumps({"qualified_UTC": value["qualified_UTC"], "unresolved": value["unresolved_accessions"],
                      "F7": value["F7_identity"]["decisions"], "basis": basis}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run", "report"))
    parser.add_argument("segment", nargs="?", choices=SEGMENTS)
    args = parser.parse_args()
    if any(os.environ.get(k) != "1" for k in
           ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("set numerical library thread caps to 1")
    if args.phase == "freeze":
        freeze()
    elif args.phase == "run":
        if not args.segment:
            raise SystemExit("run requires a segment")
        asyncio.run(run(args.segment))
    else:
        report()
