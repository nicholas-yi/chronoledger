"""Freeze, acquire once, and report only the approved timestamp metadata population."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from p0_acceptance_audit import factor_calendar
from plan_full_timestamps import assignment_required, urls_for_record
from run_reader_real2_completion import suspend_clocks

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, RAW_DIR, user_agent
from asof.filing_header_pilot import parse_header, parse_index, pool_for
from asof.filing_timestamp_audit import (
    DISK_BYTES,
    METADATA_ATTEMPTS,
    PROJECT_CEILING,
    AuditGuard,
    FullScopedFilingMetadata,
    accession_result,
    assignment_counts,
    guarded_fetch,
)
from asof.periods import DEV_END, DEV_START
from asof.sec_documentation import DocumentationStop, MetadataUnknown
from asof.timeutil import close_time_utc

PLAN = PROJECT_ROOT / "results" / "timestamp_full_plan.json"
CONFIG = PROJECT_ROOT / "results" / "timestamp_full_config.json"
STATUS = PROJECT_ROOT / "results" / "timestamp_full_status.json"
REPORT = PROJECT_ROOT / "results" / "timestamp_full_report.json"
BUDGET = DATA_DIR / "p0_SEC_request_receipt.json"
PRIVATE = DATA_DIR / "timestamp_full"
INVENTORY = PRIVATE / "frozen_URL_inventory.jsonl"
ROSTER = PRIVATE / "frozen_accessions.jsonl"
UNIVERSE = PRIVATE / "frozen_metadata_universe.jsonl"
CALENDAR = PRIVATE / "frozen_registered_calendar.json"
OUTCOMES = PRIVATE / "resource_outcomes.jsonl"
REQUESTS = PRIVATE / "requests.jsonl"
CHECKPOINT = PRIVATE / "checkpoint.json"
STARTED = PRIVATE / "attempt_started.json"
TABLE = PRIVATE / "per_accession.jsonl"
SOURCES = [
    Path(__file__), PROJECT_ROOT / "src" / "asof" / "filing_timestamp_audit.py",
    PROJECT_ROOT / "src" / "asof" / "sec_documentation.py",
    PROJECT_ROOT / "src" / "asof" / "filing_header_pilot.py",
    PROJECT_ROOT / "src" / "asof" / "timeutil.py", PROJECT_ROOT / "src" / "asof" / "p0.py",
    PROJECT_ROOT / "scripts" / "plan_full_timestamps.py",
    PROJECT_ROOT / "scripts" / "p0_acceptance_audit.py",
    PROJECT_ROOT / "scripts" / "run_reader_real2_completion.py",
    PROJECT_ROOT / "tests" / "test_filing_timestamp_audit.py",
]


def load_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_lines(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def pin(paths: list[Path]) -> dict:
    return {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in paths}


def verify(pins: dict) -> None:
    for path, digest in pins.items():
        if ledger.file_sha256(PROJECT_ROOT / path) != digest:
            raise DocumentationStop(f"frozen_input_source_or_cache_changed:{path}")


def freeze() -> None:
    if CONFIG.exists() or PRIVATE.exists():
        raise RuntimeError("already frozen; no overwrite or replacement inventory")
    suspend_clocks()
    plan = json.loads(PLAN.read_bytes())
    verify(plan["provenance"]["input_SHA256"])
    if json.loads(BUDGET.read_bytes()) != {"actual_HTTP_attempts": 140, "ceiling": 150}:
        raise ValueError("approved baseline must remain140of150")
    proposed = PROJECT_ROOT / plan["URLs_and_cache"]["private_inventory"]
    if ledger.file_sha256(proposed) != plan["URLs_and_cache"]["inventory_SHA256"]:
        raise ValueError("proposed URL inventory changed")
    urls = load_lines(proposed)
    if (len(urls), len({r["URL"] for r in urls}), len({r["accession"] for r in urls}),
        sum(r["proposed_HTTP_needed"] for r in urls)) != (34354, 34354, 16921, METADATA_ATTEMPTS):
        raise ValueError("approved exact inventory or cache count differs")
    fields = ["accession", "cik", "form", "pair_time", "bulk_time", "candidate_times",
              "first_close_choices", "clock_issues", "sensitivity_reasons", "CIKs_agree",
              "source_times_agree", "assignment_sensitive"]
    q = pd.read_parquet(DATA_DIR / "p0_assignment_queue.parquet",
                        columns=fields, use_threads=False)
    m = pd.read_parquet(DATA_DIR / "p0_pair_metadata_comparison.parquet",
                        columns=["accession", "cik_pair", "cik_bulk"], use_threads=False)
    frame = q.merge(m, on="accession", how="outer", validate="one_to_one", indicator=True)
    if len(frame) != 21502 or not frame["_merge"].eq("both").all():
        raise ValueError("original metadata universe changed")
    universe = []
    for row in frame.drop(columns="_merge").to_dict("records"):
        for key in ("candidate_times", "first_close_choices", "clock_issues", "sensitivity_reasons"):
            row[key] = list(row[key])
        row["pool"] = pool_for(row)
        universe.append(row)
    required = {r["accession"] for r in universe if assignment_required(r)
                or r["pool"] in ("clock_disagreement_winter", "clock_disagreement_summer")}
    roster = sorted((r for r in universe if r["accession"] in required),
                    key=lambda r: r["accession"])
    exact = [u for row in roster for u in urls_for_record(row)]
    if required != {u["accession"] for u in urls} or any(
        any(a[k] != b[k] for k in ("accession", "path_CIK", "kind", "URL"))
        for a, b in zip(exact, urls, strict=True)
    ):
        raise ValueError("approved URL/accession identities no longer reproduce")
    cache_pins = {}
    for resource in urls:
        if not resource["proposed_HTTP_needed"]:
            cache = resource["cache"]
            path = DATA_DIR / cache["path"]
            if ledger.file_sha256(path) != cache["file_SHA256"]:
                raise ValueError("approved cache changed")
            cache_pins[str(path.relative_to(PROJECT_ROOT))] = cache["file_SHA256"]
    PRIVATE.mkdir()
    if shutil.disk_usage(PRIVATE).free < DISK_BYTES:
        raise OSError("less than approved4GiB disk allowance available")
    shutil.copyfile(proposed, INVENTORY)
    write_lines(ROSTER, roster)
    write_lines(UNIVERSE, universe)
    days = factor_calendar()
    month_last = {}
    for day in days:
        if DEV_START <= day <= DEV_END:
            month_last[day.strftime("%Y-%m")] = day
    atomic_json(CALENDAR, {
        "closes": [close_time_utc(d).isoformat() for d in days],
        "formations": [close_time_utc(d).isoformat() for d in month_last.values()],
        "start": datetime.combine(DEV_START, datetime.min.time(), tzinfo=UTC).isoformat(),
        "end": datetime.combine(DEV_END + timedelta(days=1), datetime.min.time(), tzinfo=UTC).isoformat(),
        "status": "Existing cached French date fields only, through20240731; nominal16:00ET, "
                  "not certified venue/early-close calendar. No numeric factor values used.",
    })
    archives = [RAW_DIR / "french" / name for name in (
        "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
        "F-F_Momentum_Factor_daily_CSV.zip")]
    value = {
        "kind": "APPROVED CL-TS-FULL ONE-SHOT METADATA CHECK; NOT DATA REPAIR",
        "approval": "User timestamp_budget=approve_when_ready,2026-11-16; Lead dispatch15:08ET.",
        "population": {"accessions": 16921, "unique_URLs": 34354, "pinned_cache_hits": 102},
        "exact_lists": pin([ROSTER, INVENTORY, UNIVERSE, CALENDAR]),
        "list_storage": "Exact private lists frozen by these committed SHA256 pins; no raw "
                        "per-filing metadata in Git. Inventory bytes equal the approved proposal.",
        "cache_pins": cache_pins,
        "input_SHA256": {**plan["provenance"]["input_SHA256"], **pin([PLAN, *archives])},
        "source_SHA256": pin(SOURCES),
        "User_Agent_SHA256": hashlib.sha256(user_agent().encode()).hexdigest(),
        "ceiling_change": {"before": 150, "after": PROJECT_CEILING, "used_unchanged": 140},
        "documentation": {
            "URLs": [], "max_requests": 10, "read_cap_bytes": 4 << 20, "wall_seconds": 1800,
            "status": "SKIPPED: approved plans name categories but no specific qualifying "
                      "official SEC Filer Manual/PDS/clock-definition URLs. No guessed URLs.",
            "clock": "Eastern wall-clock assumption remains explicitly unqualified.",
        },
        "protocol": {
            "metadata_max_requests": METADATA_ATTEMPTS, "max_total_new_requests": 34262,
            "project_ceiling": PROJECT_CEILING, "requests_per_second": 2, "parallelism": 1,
            "per_request_total_timeout_seconds": 30, "retries": 0, "redirects": False,
            "metadata_body_bound_bytes": 65536, "metadata_wall_seconds": 43200,
            "checkpoint_every_resources": 500, "disk_bytes": DISK_BYTES,
            "sleep": "Windows uptime minus unbiased awake uptime >2s:record/cancel/stop.",
            "unknown_continue": ["HTTP404", "declared/read body at64KiB"],
            "stop": ["403", "429", "5xx", "other_non2xx_except404", "transport", "redirect",
                     "scope", "budget", "source/cache integrity", "wall", "disk", "sleep/suspend"],
            "resume": "A stop is final; no automatic continuation. New decision required, "
                      "unchanged freeze and last checkpoint; this runner refuses a second run.",
            "unused_document_budget": "Not transferable to extra metadata URLs.",
        },
        "output_contract": {
            "private": "All16921accessions with storedAPI/pair,bulk,header/index clocks,conditional "
                       "agreement,CIKpath/roles,provenance and qualifiedUTC or explicit unresolved "
                       "reasons. Append-only per-resource outcomes and per-attempt receipts.",
            "summary": "Pool counts, exact coverage/unknown/failed/unattempted reconciliation, "
                       "assignment changes only offline on existing metadata. Qualified actual "
                       "changes unavailable without applicable clock/identity/calendar authority; "
                       "conditional counts separately labelled. Private files hash-manifested.",
            "limits": "No prices, returns, feature/signal values, sealed observations, repairs, "
                      "CIK remaps, correction release, backtest rerun or ledger row.",
        },
    }
    atomic_json(CONFIG, value)
    atomic_json(BUDGET, {"actual_HTTP_attempts": 140, "ceiling": PROJECT_CEILING})
    print(json.dumps({"frozen": value["population"], "documentation": "skipped",
                      "config_SHA256": ledger.file_sha256(CONFIG), "actual_requests": 140}))


def report() -> None:
    if REPORT.exists() or TABLE.exists():
        raise RuntimeError("final report already exists; preserve it")
    config = json.loads(CONFIG.read_bytes())
    verify({**config["exact_lists"], **config["input_SHA256"], **config["source_SHA256"]})
    inventory, roster, universe = load_lines(INVENTORY), load_lines(ROSTER), load_lines(UNIVERSE)
    outcomes = load_lines(OUTCOMES) if OUTCOMES.exists() else []
    receipts = load_lines(REQUESTS) if REQUESTS.exists() else []
    starts = [r for r in receipts if r.get("event") == "started"]
    finishes = [r for r in receipts if r.get("event") == "finished" and r.get("attempted")]
    attempted_urls = {r["url"] for r in starts}
    used = json.loads(BUDGET.read_bytes())["actual_HTTP_attempts"]
    if [r["historical_attempt"] for r in starts] != list(range(141, used + 1)):
        raise ValueError("charged project counter does not reconcile with attempt receipts")
    by_url = {r["URL"]: r for r in outcomes}
    if len(by_url) != len(outcomes):
        raise ValueError("duplicate resource outcome; no silent replacement")
    by_accession = defaultdict(list)
    for resource in inventory:
        by_accession[resource["accession"]].append(by_url.get(resource["URL"], {
            **resource, "parsed": {"unknown": (
                "attempted_outcome_not_recorded" if resource["URL"] in attempted_urls
                else "not_attempted_after_final_stop")}}))
    rows = [accession_result(row, by_accession[row["accession"]]) for row in roster]
    required_table_bytes = sum(len(json.dumps(r, allow_nan=False).encode()) + 1 for r in rows)
    occupied = CONFIG.stat().st_size + sum(
        p.stat().st_size for p in PRIVATE.rglob("*") if p.is_file())
    if occupied + required_table_bytes + len(finishes) * 1024 + (1 << 20) >= DISK_BYTES:
        raise DocumentationStop("final_report_would_exceed4GiB_disk_budget")
    write_lines(TABLE, rows)
    calendar = json.loads(CALENDAR.read_bytes())
    assignments = assignment_counts(
        universe, rows, [datetime.fromisoformat(t) for t in calendar["closes"]],
        [datetime.fromisoformat(t) for t in calendar["formations"]],
        datetime.fromisoformat(calendar["start"]), datetime.fromisoformat(calendar["end"]))
    pools = {}
    for pool in sorted({r["pool"] for r in rows}):
        part = [r for r in rows if r["pool"] == pool]
        pools[pool] = {
            "accessions": len(part),
            "agreement_classes": dict(Counter(r["agreement_class"] for r in part)),
            "conditional_comparable": sum(bool(r["conditional_UTC_assuming_Eastern"]) for r in part),
            "qualified_UTC": 0,
            "outside_screen": sum(r["outside_frozen_candidate_envelope"] for r in part),
        }
    body_paths = [PRIVATE / "raw_metadata" / r["cache_file"] for r in receipts
                  if r.get("event") == "finished" and r.get("cache_file")]
    body_manifest = PRIVATE / "raw_body_hashes.jsonl"
    write_lines(body_manifest, [
        {"path": str(p.relative_to(PRIVATE)), "bytes": p.stat().st_size,
         "SHA256": ledger.file_sha256(p)} for p in body_paths])
    value = {
        "status": json.loads(STATUS.read_bytes())["status"],
        "config_SHA256": ledger.file_sha256(CONFIG),
        "freeze_commit": json.loads(STATUS.read_bytes())["freeze_commit"],
        "documentation": config["documentation"],
        "qualified_UTC_accessions": 0, "unresolved_accessions": len(rows),
        "accessions_accounted_for": len(rows), "resource_outcomes": len(outcomes),
        "resource_outcomes_missing": len(inventory) - len(outcomes),
        "resources_not_attempted": sum(
            r["URL"] not in by_url and r["URL"] not in attempted_urls for r in inventory),
        "new_HTTP_attempts": used - 140,
        "HTTP_status_counts": dict(Counter(str(r["status"]) for r in finishes)),
        "attempts_without_finished_receipt": len(starts) - len(finishes),
        "cache_hits_processed": sum(bool(r.get("cache_hit")) for r in outcomes),
        "resource_unknown_reasons": dict(Counter(
            r["parsed"]["unknown"] for r in outcomes if "unknown" in r["parsed"])),
        "pool_summary": pools, "assignments": assignments,
        "private_hash_manifest": pin([p for p in [
            ROSTER, INVENTORY, UNIVERSE, CALENDAR, OUTCOMES, REQUESTS, CHECKPOINT,
            TABLE, body_manifest] if p.exists()]),
        "clock_limit": "Conditional Eastern assumption only, no historical field-clock authority. "
                       "No actual verified assignment-change count established.",
        "prior_cached_controls": "Two out-of-population conditional clock counterexamples remain "
                                 "in the pinned prior header_pilot_reconciled.json; no new fetch "
                                 "or certification of these controls.",
        "unchanged": "No production metadata/identity repair, correction release, financial "
                     "rerun, price/return/sealed observation, signal value or trial ledger row.",
    }
    atomic_json(REPORT, value)
    print(json.dumps({"status": value["status"], "accessions": len(rows),
                      "new_HTTP_attempts": value["new_HTTP_attempts"],
                      "qualified_UTC": 0, "report": str(REPORT)}), flush=True)


async def run() -> None:
    if STATUS.exists() or STARTED.exists() or OUTCOMES.exists() or REQUESTS.exists():
        raise RuntimeError("already attempted; no automatic resume")
    config = json.loads(CONFIG.read_bytes())
    lineage = ledger.lineage()
    if lineage["git_dirty"]:
        raise RuntimeError("commit frozen code and exact-list manifest before any request")
    process = await asyncio.create_subprocess_exec(
        "git", "show", "HEAD:results/timestamp_full_config.json", cwd=PROJECT_ROOT,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    committed, error = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"cannot verify committed freeze: {error.decode(errors='replace')}")
    if committed != CONFIG.read_bytes():
        raise ValueError("configuration must be byte-identical to the freeze commit")
    verify({**config["exact_lists"], **config["input_SHA256"],
            **config["source_SHA256"], **config["cache_pins"]})
    if json.loads(BUDGET.read_bytes()) != {"actual_HTTP_attempts": 140, "ceiling": PROJECT_CEILING}:
        raise ValueError("approved starting budget changed")
    if hashlib.sha256(user_agent().encode()).hexdigest() != config["User_Agent_SHA256"]:
        raise ValueError("declared User-Agent changed")
    inventory = load_lines(INVENTORY)
    urls = tuple(r["URL"] for r in inventory if r["proposed_HTTP_needed"])
    with STARTED.open("x", encoding="utf-8") as stream:
        json.dump({"UTC": datetime.now(UTC).isoformat(), "freeze": lineage}, stream)
    base_bytes = CONFIG.stat().st_size + sum(
        p.stat().st_size for p in PRIVATE.iterdir() if p.is_file())
    cache_bytes = 0

    def storage() -> int:
        return base_bytes + cache_bytes + sum(p.stat().st_size for p in
            (OUTCOMES, REQUESTS, CHECKPOINT, STATUS) if p.exists())

    guard = AuditGuard(suspend_clocks, storage)
    status = {
        "status": "in_progress", "freeze_commit": lineage["git_commit"],
        "config_SHA256": ledger.file_sha256(CONFIG), "start_UTC": datetime.now(UTC).isoformat(),
        "earliest_completion_hours_at2rps": (len(urls) - 1) / 7200,
        "wall_cap_hours": 12, "resources_recorded": 0, "budget_start": 140,
        "documentation": "skipped_no_exact_eligible_URLs", "sleep_interruptions": guard.interruptions,
    }

    def checkpoint() -> None:
        for path in (OUTCOMES, REQUESTS):
            if path.exists():
                with path.open("ab") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
        status.update(counter=json.loads(BUDGET.read_bytes()),
                      wall_seconds=time.monotonic() - guard.started,
                      disk_bytes_observed=storage(), checkpoint_UTC=datetime.now(UTC).isoformat())
        atomic_json(CHECKPOINT, {**status, "outcome_SHA256": ledger.file_sha256(OUTCOMES)
                                if OUTCOMES.exists() else None,
                                "request_SHA256": ledger.file_sha256(REQUESTS)
                                if REQUESTS.exists() else None})
        atomic_json(STATUS, status)
        print(json.dumps({k: status[k] for k in (
            "status", "resources_recorded", "counter", "wall_seconds")}), flush=True)

    checkpoint()
    try:
        async with FullScopedFilingMetadata(
            urls, BUDGET, REQUESTS, PRIVATE / "raw_metadata",
        ) as client:
            client.check = guard.check
            for ordinal, resource in enumerate(inventory):
                guard.check()
                item = {**resource, "ordinal": ordinal, "cache_hit": not resource["proposed_HTTP_needed"]}
                stop = None
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
                        raw = await guarded_fetch(client, item["URL"], guard)
                    parsed = (parse_header(raw, item["accession"]) if item["kind"] == "header"
                              else parse_index(raw))
                    conditional = parsed.get("UTC_assuming_Eastern")
                    if conditional and not "2022-01-01" <= conditional[:10] < "2024-07-01":
                        raise DocumentationStop("header_outside_frozen_metadata_date_scope")
                    item["parsed"] = parsed
                except MetadataUnknown as exc:
                    item["parsed"] = {"unknown": str(exc)}
                except (DocumentationStop, ValueError, OSError) as exc:
                    item["parsed"] = {"unknown": f"resource_failed:{exc}"}
                    stop = str(exc)
                finally:
                    request = client.last_record
                    if not item["cache_hit"] and request and request["url"] == item["URL"]:
                        item["request"] = dict(request)
                        cache_bytes += request["bytes"]
                with OUTCOMES.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(item, allow_nan=False) + "\n")
                status["resources_recorded"] += 1
                if stop:
                    raise DocumentationStop(stop)
                if status["resources_recorded"] % 500 == 0:
                    verify({**config["exact_lists"], **config["source_SHA256"]})
                    if shutil.disk_usage(PRIVATE).free < (256 << 20):
                        raise OSError("physical_disk_report_reserve")
                    checkpoint()
        status["status"] = "complete_conditional_metadata_check"
    except (DocumentationStop, ValueError, OSError) as exc:
        status.update(status="stopped_final", stop_reason=str(exc))
    finally:
        if status["status"] == "in_progress":
            error = sys.exception()
            status.update(status="interrupted_final",
                          stop_reason="unexpected_interruption" if error is None
                          else f"{type(error).__name__}:{error}")
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
