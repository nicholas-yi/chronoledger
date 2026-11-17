"""Prepare a metadata-only freeze or run the approved cached, no-model exploratory screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from calibrate_inference import resident_bytes
from count_kpi_development_cache import MINIMUM, inventory
from validate_audit_cs import THREAD_VARIABLES, WorkerJob

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.document_scope import filing_document_dates, parse_document_date
from asof.kpi_omission import (
    MAX_BODY,
    MAX_CASES,
    MAX_TOTAL_BODY,
    METRICS,
    SEED,
    analyze_case,
    assert_development_disclosures,
    pin_filing,
    read_cached,
    summarize,
)

PRIVATE = DATA_DIR / "kpi_omission_dev_v1"
MANIFEST = PRIVATE / "manifest.json"
PLAN = PROJECT_ROOT / "results" / "kpi_omission_dev_plan.json"
REPORT = PROJECT_ROOT / "results" / "kpi_omission_dev_review.json"
CACHE = DATA_DIR / "raw" / "sec"
FROZEN = (
    "src/asof/kpi_omission.py", "scripts/study_kpi_omission.py", "tests/test_kpi_omission.py",
    "tests/test_kpi_study_runner.py",
    "src/asof/sections.py", "src/asof/edgar.py", "scripts/validate_audit_cs.py",
    "scripts/calibrate_inference.py", "src/asof/document_scope.py",
    "scripts/count_kpi_development_cache.py", "results/kpi_omission_dev_plan.json",
)
PROTECTED = (
    DATA_DIR / "p0_SEC_request_receipt.json",
    PROJECT_ROOT / "results" / "trial_ledger.jsonl",
    PROJECT_ROOT / "results" / "timestamp_full_a2_report.json",
    PROJECT_ROOT / "results" / "audit_cs_validation.json",
)


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, indent=2, allow_nan=False) + "\n")


def prepare() -> dict:
    if MANIFEST.exists() or PLAN.exists():
        raise FileExistsError("plan already exists; preserve the frozen selection")
    count, pool = inventory()
    if len(pool) < MINIMUM:
        raise RuntimeError("fewer than30 eligible issuer triples; stop without bodies or downloads")
    cases = []
    guard_rows = []
    selected = sorted(pool, key=lambda row: hashlib.sha256(
        f"{SEED}:{row['cik']}".encode()).hexdigest())[:MAX_CASES]
    for i, candidate in enumerate(selected, 1):
        cik, refs, context_refs = candidate["cik"], candidate["annual"], candidate["context"]
        assert_development_disclosures(refs + context_refs)
        case_id = f"KPI-DEV-{i:03d}"
        for role, records in (("annual", refs), ("context", context_refs)):
            for index, ref in enumerate(records):
                dates = filing_document_dates(ref)
                guard_rows.append({
                    "case_id": case_id, "role": role, "index": index,
                    "accession": ref["accession"], "guard_passed": True,
                    "acceptance": parse_document_date(dates.accepted_at, "acceptance").isoformat(),
                    "knowledge": parse_document_date(dates.knowledge_at, "knowledge").isoformat(),
                    "period_end": parse_document_date(dates.period_end, "period_end").isoformat(),
                    "source_clock_qualified": False,
                })
        cases.append({
            "case_id": case_id, "cik": cik,
            "annual": [pin_filing(r, CACHE, fingerprint=False) for r in refs],
            "context": [pin_filing(r, CACHE, fingerprint=False) for r in context_refs],
        })
    if not cases:
        raise ValueError("no eligible cached annual triples; do not broaden or fabricate a roster")
    write_json(MANIFEST, {"cases": cases})
    write_json(PRIVATE / "guard_passes.json", guard_rows)
    result = {
        "study": "KPI-OMISSION-DEVELOPMENT-v1", "status": "frozen_plan_not_executed",
        "seed": SEED, "metadata_eligible_issuers": len(pool), "selected_cases": len(cases),
        "period_change": "2012-01-01..2018-12-31 for acceptance/knowledge/period/context; "
                         "not the superseded2021-2024 roster",
        "inventory_metadata_annual_rows": count["metadata_annual_rows"],
        "manifest_SHA256": ledger.file_sha256(MANIFEST),
        "guard_passes_SHA256": ledger.file_sha256(PRIVATE / "guard_passes.json"),
        "guard_document_count": len(guard_rows),
        "preparation_body_reads": 0, "preparation_body_fingerprints": 0,
        "cache_snapshot": "size/mtime pinned before content; SHA256 recorded at first guarded read",
        "selection": "first 64 issuer SHA256(seed:CIK) ranks; latest cached annual triple, "
                     "330-400 day report-period gaps, increasing unqualified stored times",
        "history": "two prior comparable annual reports, not the paper's three-prior-year rule",
        "metric_patterns": METRICS,
        "earlier_context": "up to 2 cached primary 8-Ks with Item2.02 in prior120days; "
                           "exhibits/calls/news not exhaustive; stored clocks unqualified",
        "body_cap_bytes": MAX_BODY, "total_uncompressed_body_budget": MAX_TOTAL_BODY,
        "checkpoint_policy": "private per-case receipts; recover complete prefix on hard stop",
        "wall_seconds": 300, "compute_parallelism": 1, "worker_commit_limit": 1 << 30,
        "real_content_analyzed_during_prepare": False,
        "baseline_policy": "descriptive lexical/length/numeric differences; no model fitting",
        "casebook_policy": "6 candidates,3 persistence controls,3 incomplete; ties by ID",
        "scope": "cached-only lexical hypotheses, no prices/outcomes/signals for trading",
        "human_effort": False, "human_gold": False, "model_calls": 0,
        "new_downloads": 0, "preserves_H0_H1": True, "scientific_acceptance": False,
    }
    write_json(PLAN, result)
    return result


def worker(cases: list[dict], channel) -> None:
    if channel.recv() != "cached-study-ready":
        raise RuntimeError("owned resource-limited controller handshake required")
    started = time.perf_counter()
    rows = []
    total_bytes = 0
    stop = None
    for case in cases:
        if time.perf_counter() - started > 240 or resident_bytes() >= 900 << 20:
            stop = "cooperative_resource_stop"
            break
        documents = []
        for ref in case["annual"] + case["context"]:
            if total_bytes + MAX_BODY + 1 > MAX_TOTAL_BODY:
                stop = "uncompressed_body_budget_before_next_resource"
                break
            assert_development_disclosures([ref])
            with (PRIVATE / "resource_receipts.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({
                    "case_id": case["case_id"], "accession": ref["accession"],
                    "phase": "guard_pass_before_body", "accepted_at": ref["accepted_at"],
                    "knowledge_time": ref["knowledge_time"], "period_end": ref["report_date"],
                }) + "\n")
            doc = read_cached(ref, CACHE)
            with (PRIVATE / "resource_receipts.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({
                    "case_id": case["case_id"], "accession": ref["accession"],
                    "phase": "completed", "status": doc.status, "reason": doc.reason,
                    "body_bytes": doc.body_bytes,
                }) + "\n")
            documents.append(doc)
            total_bytes += doc.body_bytes
            if total_bytes > MAX_TOTAL_BODY:
                stop = "uncompressed_body_budget"
                break
        if stop:
            break
        row = analyze_case(case, documents[:3], documents[3:])
        write_json(PRIVATE / "case_parts" / f"{case['case_id']}.json", row)
        rows.append(row)
    channel.send({
        "rows": rows, "stop_reason": stop, "body_bytes_read": total_bytes,
        "worker_CPU_seconds": time.process_time(),
        "worker_wall_seconds": time.perf_counter() - started,
        "worker_OS_peak_RSS_bytes": resident_bytes(),
    })
    channel.close()


def recover_cases(cases: list[dict]) -> tuple[list[dict], list[str]]:
    rows, issues = [], []
    for case in cases:
        path = PRIVATE / "case_parts" / f"{case['case_id']}.json"
        if not path.exists():
            issues.append(f"{case['case_id']}:no_complete_checkpoint")
            break
        try:
            row = json.loads(path.read_bytes())
        except json.JSONDecodeError:
            issues.append(f"{case['case_id']}:truncated_checkpoint")
            break
        if not isinstance(row, dict) or row.get("case_id") != case["case_id"]:
            issues.append(f"{case['case_id']}:checkpoint_identity_mismatch")
            break
        rows.append(row)
    return rows, issues


def casebook(rows: list[dict], selected: list[str]) -> str:
    output = [
        "# Cached KPI omission casebook",
        "AI-assisted exploratory evidence, NOT human gold, market novelty or return evidence.",
        "Case selection is deliberately enriched, not a random accuracy audit.",
    ]
    for row in rows:
        if row["case_id"] not in selected:
            continue
        output += [f"\n## {row['case_id']} - CIK {row['cik']}", f"Status: {row['status']}"]
        for i, source in enumerate(row["sources"]):
            output += [
                (f"- Annual {i}: [{source['accession']}]({source['url']}); "
                f"period {source['metadata_report_date']}; identity "
                f"{source.get('identity_status','unavailable')}; "
                f"body SHA256 {source.get('body_SHA256','unavailable')}")]
        for name, metric in row["metrics"].items():
            if not (metric["two_prior_numeric_context_support"]
                    or metric["lexical_omission_candidate_not_semantic_conclusion"]):
                continue
            output += [
                f"\n### {name}",
                ("Alias counts old/previous/current: "
                 f"{[o['alias_mentions'] for o in metric['observations']]}"),
                f"Lexical candidate: {metric['lexical_omission_candidate_not_semantic_conclusion']}",
                f"Earlier cached primary mentions: {metric['earlier_cached_primary_mentions']}",
            ]
            for i, observation in enumerate(metric["observations"]):
                for evidence in observation["evidence"][:2]:
                    output += [
                        (f"\nAnnual {i}, parsed-text offsets "
                         f"{evidence['context_start']}..{evidence['context_end']}:"),
                        "```text", evidence["context"].replace("```", "'''"), "```",
                        f"Unadjudicated explanation cues: {evidence['explanation_cues_for_review']}"]
    return "\n".join(output) + "\n"


def run() -> dict:
    if REPORT.exists() or (PRIVATE / "attempt.json").exists():
        raise FileExistsError("cached screen already attempted; no automatic retry/resume")
    if any(os.environ.get(k) != "1" for k in THREAD_VARIABLES):
        raise RuntimeError("single-thread numerical-library environment flags required")
    plan = json.loads(PLAN.read_bytes())
    if ledger.file_sha256(MANIFEST) != plan["manifest_SHA256"]:
        raise ValueError("frozen manifest changed")
    if ledger.file_sha256(PRIVATE / "guard_passes.json") != plan["guard_passes_SHA256"]:
        raise ValueError("per-document guard receipts changed")
    cases = json.loads(MANIFEST.read_bytes())["cases"]
    assert_development_disclosures([
        ref for case in cases for ref in case["annual"] + case["context"]])
    git = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
                         check=True, capture_output=True, text=True)
    if git.stdout.strip():
        raise RuntimeError("commit source and plan before analyzing real cached content")
    for relative in FROZEN:
        committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=PROJECT_ROOT)
        local = PROJECT_ROOT.joinpath(*relative.split("/")).read_bytes()
        if committed.replace(b"\r\n", b"\n") != local.replace(b"\r\n", b"\n"):
            raise ValueError(f"frozen source differs: {relative}")
    source_hashes = {p: ledger.file_sha256(PROJECT_ROOT.joinpath(*p.split("/"))) for p in FROZEN}
    protected = {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in PROTECTED}
    lineage = ledger.lineage()
    write_json(PRIVATE / "attempt.json", {
        "started_utc": datetime.now(UTC).isoformat(), "lineage": lineage,
        "source_SHA256": source_hashes, "protected_SHA256": protected})
    started = time.perf_counter()
    result = {"status": "stopped", "stop_reason": None, "rows": []}
    job = process = parent = child = None
    try:
        job = WorkerJob()
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=worker, args=(cases, child))
        process.start()
        child.close()
        if process.pid is None:
            raise RuntimeError("owned worker has no PID")
        affinity = job.attach(process.pid)
        parent.send("cached-study-ready")
        if not parent.poll(max(0.01, 300 - (time.perf_counter() - started))):
            raise TimeoutError("cached study wall ceiling")
        output = parent.recv()
        process.join(timeout=max(0.01, 300 - (time.perf_counter() - started)))
        if process.is_alive() or process.exitcode != 0:
            raise RuntimeError("owned cached-study worker did not exit cleanly")
        result.update(output)
        result["affinity_logical_processors"] = affinity.bit_count()
        result["status"] = (
            "completed_exploratory_screen"
            if len(result["rows"]) == len(cases) and not result["stop_reason"] else "stopped")
    except (OSError, ValueError, RuntimeError, EOFError) as exc:
        result["stop_reason"] = f"{type(exc).__name__}:{exc}; unreported work remains unknown"
    finally:
        if job is not None:
            job.close()
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
            process.close()
        for channel in (parent, child):
            if channel is not None:
                channel.close()
    rows = result.pop("rows")
    if result["status"] == "stopped" and not rows:
        rows, recovery_issues = recover_cases(cases)
        result["checkpoint_recovery_issues"] = recovery_issues
        result["recovered_complete_cases"] = len(rows)
    summary = summarize(rows)
    write_json(PRIVATE / "cases.json", rows)
    with (PRIVATE / "casebook.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(casebook(rows, summary["selected_casebook_ids"]))
    result.update(
        summary=summary, lineage=lineage, plan_SHA256=ledger.file_sha256(PLAN),
        selected_case_count=len(cases), unreported_case_count=len(cases) - len(rows),
        manifest_SHA256=ledger.file_sha256(MANIFEST),
        cases_SHA256=ledger.file_sha256(PRIVATE / "cases.json"),
        casebook_SHA256=ledger.file_sha256(PRIVATE / "casebook.md"),
        guard_passes_SHA256=ledger.file_sha256(PRIVATE / "guard_passes.json"),
        resource_receipts_SHA256=(
            ledger.file_sha256(PRIVATE / "resource_receipts.jsonl")
            if (PRIVATE / "resource_receipts.jsonl").exists() else None),
        controller_wall_seconds=time.perf_counter() - started,
        controller_OS_peak_RSS_bytes=resident_bytes(),
        source_unchanged=all(
            ledger.file_sha256(PROJECT_ROOT.joinpath(*p.split("/"))) == v
            for p, v in source_hashes.items()),
        protected_unchanged=all(
            ledger.file_sha256(PROJECT_ROOT.joinpath(*p.split("/"))) == v
            for p, v in protected.items()),
        scientific_acceptance=False, human_gold=False,
        model_calls=0, new_downloads=0, return_evaluations=0,
        source_scope="conservative_development_guard_not_scientific_clearance",
    )
    result["sum_of_separate_OS_RSS_peaks_bytes"] = (
        result["controller_OS_peak_RSS_bytes"] + result.get("worker_OS_peak_RSS_bytes", 1 << 30))
    result["resource_check_passed"] = (
        result["controller_wall_seconds"] <= 300
        and result.get("affinity_logical_processors") == 1
        and result["sum_of_separate_OS_RSS_peaks_bytes"] < 1 << 30
        and result.get("body_bytes_read", MAX_TOTAL_BODY + 1) <= MAX_TOTAL_BODY)
    result["roster_and_guard_receipts_unchanged"] = (
        result["manifest_SHA256"] == plan["manifest_SHA256"]
        and result["guard_passes_SHA256"] == plan["guard_passes_SHA256"])
    failures = []
    if not result["source_unchanged"] or not result["protected_unchanged"]:
        failures.append("source_or_protected_evidence_changed")
    if not result["resource_check_passed"] or not result["roster_and_guard_receipts_unchanged"]:
        failures.append("resource_or_roster_check_unqualified")
    result["post_run_failure_reasons"] = failures
    if failures:
        result["status"] = "stopped"
        result["stop_reason"] = result["stop_reason"] or ";".join(failures)
    write_json(REPORT, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run"])
    args = parser.parse_args()
    result = prepare() if args.command == "prepare" else run()
    print(json.dumps({k: v for k, v in result.items() if k != "metric_patterns"}, indent=2))
    return 0 if args.command == "prepare" or result["status"] == "completed_exploratory_screen" else 2


if __name__ == "__main__":
    raise SystemExit(main())
