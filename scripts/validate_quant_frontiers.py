"""One committed, bounded all-nine synthetic benchmark; no real-data or ledger access."""

from __future__ import annotations

import argparse
import ctypes
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
from validate_audit_cs import THREAD_VARIABLES, BudgetStop, WorkerJob

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "results" / "quant_frontiers_validation_plan.json"
REPORT = ROOT / "results" / "quant_frontiers_validation.json"
ATTEMPT = ROOT / "data" / "quant_frontiers_validation_v1" / "attempt.json"
FROZEN = (
    "scripts/validate_quant_frontiers.py", "scripts/quant_frontiers_cases.py",
    "scripts/validate_audit_cs.py", "scripts/calibrate_inference.py",
    "results/quant_frontiers_validation_plan.json", "requirements-dev.lock", "pyproject.toml",
    "src/asof/timeutil.py", "docs/QUANT_SYNTHETIC_VALIDATION.md",
    *(f"src/asof/research/{name}.py" for name in (
        "__init__", "_validation", "economic", "arrivals", "trajectories",
        "networks", "pricing", "mechanisms", "control", "identification", "prequential")),
    "tests/research/test_benchmark_controller.py",
)


def validate_plan(plan: dict) -> None:
    expected = {
        "study": "CL-QF-SYN-01",
        "authorization": "2026-11-17 ask_user testing_scope=synthetic_and_plan",
        "seed": 202611171803, "cases_per_area": 64, "arrival_events": 256,
        "arrival_dkw_delta": 0.01, "max_arrival_proposals": 100000,
        "binary_horizon": 12, "binary_alpha": 0.05, "oracle_absolute_tolerance": 1e-8,
        "limits": {
            "total_wall_seconds": 300, "controller_stop_seconds": 290,
            "worker_soft_wall_seconds": 270, "worker_CPU_seconds": 270,
            "total_RSS_bytes": 1 << 30, "controller_RSS_allowance": 128 << 20,
            "worker_RAM_bytes": 896 << 20, "compute_CPUs": 1,
        },
    }
    if plan != expected:
        raise ValueError("plan differs from the frozen approved allocation")


def source_hashes() -> dict[str, str]:
    return {p: hashlib.sha256(ROOT.joinpath(*p.split("/")).read_bytes()).hexdigest()
            for p in FROZEN}


def freeze_receipt() -> dict:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "--no-pager", *args], cwd=ROOT)

    if git("status", "--porcelain").strip():
        raise RuntimeError("commit source, plan and tests before executing any random draw")
    for path in FROZEN:
        blob = git("show", f"HEAD:{path}").replace(b"\r\n", b"\n")
        local = ROOT.joinpath(*path.split("/")).read_bytes().replace(b"\r\n", b"\n")
        if blob != local:
            raise RuntimeError(f"source differs from committed freeze: {path}")
    return {"git_commit": git("rev-parse", "HEAD").decode().strip(),
            "source_SHA256": source_hashes(),
            "line_endings": "LF/CRLF equivalence for Git matching; hashes use raw worktree bytes"}


def worker(plan: dict, channel: Connection) -> None:
    if channel.recv() != "quant-frontiers-contained":
        raise RuntimeError("controller handshake required before imports or random draws")
    started = time.perf_counter()
    limits = plan["limits"]

    def guard() -> None:
        if time.perf_counter() - started >= limits["worker_soft_wall_seconds"]:
            raise BudgetStop("worker_soft_wall_ceiling")
        if time.process_time() >= limits["worker_CPU_seconds"]:
            raise BudgetStop("worker_CPU_ceiling")
        if resident_bytes() >= limits["worker_RAM_bytes"]:
            raise BudgetStop("worker_peak_RSS_ceiling")

    def publish(cell: dict) -> None:
        guard()
        channel.send({"kind": "cell", "cell": cell})

    try:
        from quant_frontiers_cases import execute_cells

        execute_cells(plan, publish, guard)
        status, reason = "complete", None
    except (BudgetStop, MemoryError, ValueError, TypeError, ArithmeticError, RuntimeError) as exc:
        status, reason = "stopped", f"{type(exc).__name__}:{exc}"
    channel.send({
        "kind": "final", "status": status, "stop_reason": reason,
        "worker_CPU_seconds": time.process_time(),
        "worker_wall_seconds": time.perf_counter() - started,
        "worker_peak_RSS_bytes": resident_bytes(),
    })
    channel.close()


def pin_controller(job: WorkerJob, mask: int) -> int:
    """Pin only this controller to the worker's CPU; return its original mask."""
    process = job.kernel.OpenProcess(0x701, False, os.getpid())
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        original, system = ctypes.c_size_t(), ctypes.c_size_t()
        if not job.kernel.GetProcessAffinityMask(
                process, ctypes.byref(original), ctypes.byref(system)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not job.kernel.SetProcessAffinityMask(process, mask):
            raise ctypes.WinError(ctypes.get_last_error())
        return original.value
    finally:
        job.kernel.CloseHandle(process)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required for the single frozen attempt")
    if ATTEMPT.exists() or REPORT.exists():
        raise FileExistsError("already attempted; no retry or automatic resume")
    plan = json.loads(PLAN.read_bytes())
    validate_plan(plan)
    if any(os.environ.get(key) != "1" for key in THREAD_VARIABLES):
        raise RuntimeError("set all four numerical-library thread variables to one")
    started = time.perf_counter()
    lineage = freeze_receipt()
    limits = plan["limits"]
    ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    with ATTEMPT.open("x", encoding="utf-8") as output:
        json.dump({"started_utc": datetime.now(UTC).isoformat(), "lineage": lineage}, output)
    report = {
        "study": plan["study"], "plan": plan, "lineage": lineage,
        "status": "stopped", "stop_reason": None, "cells": {},
        "synthetic_QA_passed": False, "economic_claim_validated": False,
        "real_data_read": False, "model_training_run": False, "production_ledger_rows": 0,
    }
    job = process = parent = child = None
    original_affinity = None
    try:
        if resident_bytes() >= limits["controller_RSS_allowance"]:
            raise BudgetStop("controller_RSS_allowance_before_launch")
        job = WorkerJob(memory_bytes=limits["worker_RAM_bytes"])
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=worker, args=(plan, child))
        process.start()
        child.close()
        if process.pid is None:
            raise RuntimeError("owned worker has no PID")
        report["worker_pid"] = process.pid
        mask = job.attach(process.pid)
        original_affinity = pin_controller(job, mask)
        report["compute_affinity_logical_processors"] = mask.bit_count()
        parent.send("quant-frontiers-contained")
        final = None
        while final is None:
            if time.perf_counter() - started >= limits["controller_stop_seconds"]:
                raise TimeoutError("controller deadline with cleanup reserve")
            if resident_bytes() >= limits["controller_RSS_allowance"]:
                raise BudgetStop("controller_RSS_allowance")
            if not parent.poll(0.05):
                if not process.is_alive():
                    raise RuntimeError("worker exited without final receipt")
                continue
            message = parent.recv()
            if message.get("kind") == "cell":
                cell = message["cell"]
                report["cells"][cell["name"]] = cell
            elif message.get("kind") == "final":
                final = message
            else:
                raise ValueError("unknown worker message")
        process.join(timeout=3)
        if process.is_alive() or process.exitcode != 0:
            raise RuntimeError("worker did not exit cleanly")
        report.update({k: v for k, v in final.items() if k != "kind"})
    except (OSError, ValueError, TypeError, RuntimeError, EOFError, TimeoutError) as exc:
        report["stop_reason"] = f"{type(exc).__name__}:{exc}"
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
    report["controller_wall_seconds"] = time.perf_counter() - started
    report["controller_CPU_seconds"] = time.process_time()
    report["controller_peak_RSS_bytes"] = resident_bytes()
    report["sum_separate_peak_RSS_bytes"] = (
        report["controller_peak_RSS_bytes"] + report.get("worker_peak_RSS_bytes", 1 << 30))
    report["source_unchanged"] = source_hashes() == lineage["source_SHA256"]
    report["resource_check_passed"] = (
        report["controller_wall_seconds"] < limits["total_wall_seconds"]
        and report["sum_separate_peak_RSS_bytes"] < limits["total_RSS_bytes"]
        and report.get("worker_CPU_seconds", 301) <= limits["worker_CPU_seconds"]
        and report.get("compute_affinity_logical_processors") == 1)
    cells = list(report["cells"].values())
    report["synthetic_QA_passed"] = (
        report["status"] == "complete" and len(cells) == 9
        and all(c["completed"] == c["planned"] and not c["failures"] for c in cells)
        and report["source_unchanged"] and report["resource_check_passed"])
    report["unreported_work_unknown_if_stopped"] = report["status"] != "complete"
    with REPORT.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in (
        "status", "stop_reason", "synthetic_QA_passed", "resource_check_passed",
        "source_unchanged", "controller_wall_seconds")}, indent=2))
    return 0 if report["synthetic_QA_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
