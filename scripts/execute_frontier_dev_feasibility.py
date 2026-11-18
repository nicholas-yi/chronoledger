"""One guarded development-derived feasibility pass, not an economic validation or return trial."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import subprocess
import time
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from pathlib import Path

from calibrate_inference import resident_bytes
from validate_audit_cs import THREAD_VARIABLES, WorkerJob
from validate_quant_frontiers import pin_controller

from asof.research.feasibility import guard_manifest, project_cases

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "results" / "quant_dev_feasibility_plan.json"
REPORT = ROOT / "results" / "quant_dev_feasibility.json"
SOURCE = ROOT / "data" / "kpi_omission_dev_v1"
PRIVATE = ROOT / "data" / "quant_frontiers_dev_feas_v1"
ATTEMPT = PRIVATE / "attempt.json"
FROZEN = (
    "scripts/execute_frontier_dev_feasibility.py", "src/asof/research/feasibility.py",
    "src/asof/research/_validation.py", "src/asof/research/economic.py",
    "src/asof/research/trajectories.py", "src/asof/timeutil.py",
    "src/asof/document_scope.py", "src/asof/periods.py", "scripts/validate_audit_cs.py",
    "scripts/validate_quant_frontiers.py", "scripts/calibrate_inference.py",
    "results/quant_dev_feasibility_plan.json", "docs/QUANT_DEV_FEASIBILITY.md",
    "tests/research/test_development_feasibility.py", "requirements-dev.lock",
)


def validate_plan(plan: dict) -> None:
    expected = {
        "study": "CL-QF-DEV-FEAS-01",
        "source_manifest_sha256": "0944009c8f230372172c0622b560716fc5ee4db00f09cd0b93c5ae32363b4e92",
        "source_cases_sha256": "1b86638f40b689d7d76da1017b0d9340debc2a55a1a125a1414cf2e2678f4cee",
        "expected_manifest_cases": 64, "expected_guarded_references": 263,
        "expected_derived_cases": 50, "minimum_complete_sources": 30,
        "metadata_cap_bytes": 256 << 10, "derived_cap_bytes": 1 << 20,
        "development_start": "2012-01-01", "development_end": "2018-12-31",
        "posthoc_after_prior_exposure": True,
        "limits": {
            "wall_seconds": 300, "controller_stop_seconds": 290,
            "worker_soft_wall_seconds": 240, "worker_RAM_bytes": 896 << 20,
            "controller_RSS_allowance": 128 << 20, "total_RSS_bytes": 1 << 30,
            "compute_CPUs": 1,
        },
    }
    if any(plan.get(key) != value for key, value in expected.items()):
        raise ValueError("development execution scope or resource contract changed")


def hashes() -> dict[str, str]:
    return {p: hashlib.sha256(ROOT.joinpath(*p.split("/")).read_bytes()).hexdigest() for p in FROZEN}


def freeze_receipt() -> dict:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "--no-pager", *args], cwd=ROOT)

    if git("status", "--porcelain").strip():
        raise RuntimeError("commit source and scope before derived-text access")
    for path in FROZEN:
        if (git("show", f"HEAD:{path}").replace(b"\r\n", b"\n")
                != ROOT.joinpath(*path.split("/")).read_bytes().replace(b"\r\n", b"\n")):
            raise RuntimeError(f"source differs from the committed freeze: {path}")
    return {"freeze_commit": git("rev-parse", "HEAD").decode().strip(), "source_SHA256": hashes()}


def _read_cap(path: Path, cap: int, role: str, receipt: dict) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(cap + 1)
    receipt[f"{role}_bytes_read"] = len(data)
    if len(data) > cap:
        raise ValueError(f"{role} exceeds the frozen input cap")
    return data


def curate(plan: dict, receipt: dict) -> list[dict]:
    """Only this adapter reads the pre-cleared extract; the worker gets no text or source paths."""
    manifest_raw = _read_cap(SOURCE / "manifest.json", plan["metadata_cap_bytes"], "metadata", receipt)
    manifest = json.loads(manifest_raw)
    scope = guard_manifest(manifest)
    receipt.update(scope)
    if (hashlib.sha256(manifest_raw).hexdigest() != plan["source_manifest_sha256"]
            or scope["manifest_cases"] != plan["expected_manifest_cases"]
            or scope["guarded_metadata_references"] != plan["expected_guarded_references"]):
        raise ValueError("metadata differs from the prior development freeze; no derived-text read")
    receipt["all_metadata_guarded_before_derived_bytes"] = True
    raw = _read_cap(SOURCE / "cases.json", plan["derived_cap_bytes"], "derived_extract", receipt)
    digest = hashlib.sha256(raw).hexdigest()
    receipt["observed_derived_sha256"] = digest
    if digest != plan["source_cases_sha256"]:
        raise ValueError("derived bytes differ from the prior content receipt; do not decode or proceed")
    cases = json.loads(raw)
    if len(cases) != plan["expected_derived_cases"]:
        raise ValueError("derived cohort count changed; no replacements or resampling")
    projected = project_cases(manifest, cases)
    private_raw = (json.dumps(projected, sort_keys=True, allow_nan=False) + "\n").encode()
    with (PRIVATE / "projected_input.json").open("xb") as stream:
        stream.write(private_raw)
    receipt.update({
        "projected_rows": len(projected), "projected_input_bytes": len(private_raw),
        "projected_input_sha256": hashlib.sha256(private_raw).hexdigest(),
        "worker_input": "only dates, pseudonymous sequence IDs, coverage and prior lexical counts",
        "derived_bytes_included_preexisting_verbatim_excerpts": True,
        "worker_received_raw_text": False, "raw_cache_body_reads": 0,
        "mixed_archive_or_parquet_reads": 0, "source_clock_qualified": False,
    })
    with (PRIVATE / "curation_receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    return projected


def worker(rows: list[dict], channel: Connection) -> None:
    if channel.recv() != "development-projection-contained":
        raise RuntimeError("owned controller gate required before processing")
    started = time.perf_counter()
    from asof.research.feasibility import diagnose_projection

    try:
        result = diagnose_projection(rows)
        status, reason = "completed_unlabelled_feasibility", None
    except (ValueError, TypeError, ArithmeticError, RuntimeError) as exc:
        result, status, reason = {}, "stopped", f"{type(exc).__name__}:{exc}"
    channel.send({"status": status, "stop_reason": reason, "diagnostics": result,
                  "worker_wall_seconds": time.perf_counter()-started,
                  "worker_CPU_seconds": time.process_time(),
                  "worker_peak_RSS_bytes": resident_bytes()})
    channel.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args(argv).execute:
        parser.error("--execute is required for the frozen single pass")
    if ATTEMPT.exists() or REPORT.exists():
        raise FileExistsError("already attempted; no retry or automatic resume")
    if any(os.environ.get(key) != "1" for key in THREAD_VARIABLES):
        raise RuntimeError("all numerical thread environment variables must equal one")
    plan = json.loads(PLAN.read_bytes())
    validate_plan(plan)
    started = time.perf_counter()
    lineage = freeze_receipt()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with ATTEMPT.open("x", encoding="utf-8") as stream:
        json.dump({"started_utc": datetime.now(UTC).isoformat(), "lineage": lineage}, stream)
    access: dict = {}
    report = {"study": plan["study"], "plan": plan, "lineage": lineage, "access": access,
              "status": "stopped", "stop_reason": None, "diagnostics": {},
              "independent_gold_validation": False, "economic_claim_validated": False,
              "production_ledger_rows": 0, "model_calls": 0, "return_evaluations": 0}
    job = process = parent = child = None
    original_affinity = None
    limits = plan["limits"]
    try:
        rows = curate(plan, access)
        if resident_bytes() >= limits["controller_RSS_allowance"]:
            raise RuntimeError("curation/controller RSS allowance")
        job = WorkerJob(memory_bytes=limits["worker_RAM_bytes"])
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=worker, args=(rows, child))
        process.start()
        child.close()
        if process.pid is None:
            raise RuntimeError("owned worker has no PID")
        report["worker_pid"] = process.pid
        mask = job.attach(process.pid)
        original_affinity = pin_controller(job, mask)
        report["compute_affinity_logical_processors"] = mask.bit_count()
        parent.send("development-projection-contained")
        remaining = limits["controller_stop_seconds"]-(time.perf_counter()-started)
        if not parent.poll(max(0.01, remaining)):
            raise TimeoutError("owned development worker exceeded the deadline")
        output = parent.recv()
        process.join(timeout=3)
        if process.is_alive() or process.exitcode != 0:
            raise RuntimeError("owned worker did not exit cleanly")
        report.update(output)
        if report["diagnostics"].get("complete_three_source_cases", 0) < plan["minimum_complete_sources"]:
            report["status"] = "stopped"
            report["stop_reason"] = report["stop_reason"] or "fewer_than_30_complete_source_sequences"
    except (OSError, ValueError, TypeError, RuntimeError, EOFError) as exc:
        report["status"], report["stop_reason"] = "stopped", f"{type(exc).__name__}:{exc}"
    finally:
        if job is not None:
            try:
                if original_affinity is not None:
                    pin_controller(job, original_affinity)
            except OSError as exc:
                report["status"] = "stopped"
                report["cleanup_issue"] = f"controller_affinity_restore_failed:{exc}"
                report["stop_reason"] = report["stop_reason"] or report["cleanup_issue"]
            finally:
                job.close()
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=3)
            report["worker_exit_code"] = process.exitcode
            process.close()
        for channel in (parent, child):
            if channel is not None:
                channel.close()
    report["controller_wall_seconds"] = time.perf_counter()-started
    report["combined_separate_peak_RSS_bytes"] = (
        resident_bytes()+report.get("worker_peak_RSS_bytes", 1 << 30))
    report["source_unchanged"] = hashes() == lineage["source_SHA256"]
    report["resource_check_passed"] = (
        report["controller_wall_seconds"] < limits["wall_seconds"]
        and report["combined_separate_peak_RSS_bytes"] < limits["total_RSS_bytes"]
        and report.get("worker_wall_seconds", 301) < limits["worker_soft_wall_seconds"]
        and report.get("compute_affinity_logical_processors") == 1)
    if not report["source_unchanged"] or not report["resource_check_passed"]:
        report["status"] = "stopped"
        report["stop_reason"] = report["stop_reason"] or "source_or_resource_check_failed"
    with REPORT.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({key: report[key] for key in (
        "status", "stop_reason", "resource_check_passed", "source_unchanged",
        "controller_wall_seconds")}, indent=2))
    return 0 if report["status"] == "completed_unlabelled_feasibility" else 2


if __name__ == "__main__":
    raise SystemExit(main())
