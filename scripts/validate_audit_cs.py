"""One frozen invented-data CS check, supervised within the approved resource budget."""

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

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "results" / "audit_cs_validation_plan.json"
REPORT = ROOT / "results" / "audit_cs_validation.json"
ATTEMPT = ROOT / "data" / "audit_cs_validation" / "attempt.json"
THREAD_VARIABLES = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS")
FROZEN = (
    "src/asof/audit_cs.py", "scripts/audit_confidence_sequence.py",
    "scripts/validate_audit_cs.py", "scripts/calibrate_inference.py",
    "tests/test_audit_cs.py", "tests/test_audit_cs_validation.py",
    "results/audit_cs_validation_plan.json",
)
PROTECTED = (
    "results/trial_ledger.jsonl", "results/timestamp_full_a2_report.json",
    "results/timestamp_full_a2_review.json", "data/p0_SEC_request_receipt.json",
)


def hashes(paths: tuple[str, ...]) -> dict[str, str]:
    return {p: hashlib.sha256(ROOT.joinpath(*p.split("/")).read_bytes()).hexdigest() for p in paths}


def frozen_lineage() -> dict:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "--no-pager", *args], cwd=ROOT)

    if git("status", "--porcelain").strip():
        raise RuntimeError("commit source and clear unrelated changes before the frozen run")
    for relative in FROZEN:
        committed = git("show", f"HEAD:{relative}").replace(b"\r\n", b"\n")
        local = ROOT.joinpath(*relative.split("/")).read_bytes().replace(b"\r\n", b"\n")
        if committed != local:
            raise RuntimeError(f"worktree bytes differ from frozen HEAD: {relative}")
    return {
        "git_commit": git("rev-parse", "HEAD").decode().strip(), "SHA256": hashes(FROZEN),
        "matching_policy": "CRLF/LF equivalence only; SHA256 records actual raw worktree bytes",
    }


def validate_plan(plan: dict) -> None:
    expected = {
        "population": 80, "total_errors": [0, 1, 8, 40, 79, 80],
        "missingness": ["none", "hide_errors", "hide_nonerrors", "all_unread", "bursts"],
        "replicates_per_cell": 1000, "planned_paths": 30000, "delta": 0.05,
        "limits": {
            "controller_wall_seconds": 300, "worker_soft_wall_seconds": 270,
            "worker_CPU_seconds": 270, "RAM_bytes": 1 << 30,
            "compute_threads": 1, "worker_affinity_logical_processors": 1,
        },
    }
    if any(plan.get(key) != value for key, value in expected.items()):
        raise ValueError("validation plan does not match the approved bounded allocation")


class WorkerJob:
    """Limits only a newly owned worker; never changes the host or another process."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("this strict validation supervisor currently requires Windows")
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", w.DWORD), ("min_ws", ctypes.c_size_t), ("max_ws", ctypes.c_size_t),
                ("active", w.DWORD), ("affinity", ctypes.c_size_t),
                ("priority", w.DWORD), ("scheduling", w.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [
            w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        kernel.SetInformationJobObject.restype = w.BOOL
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.AssignProcessToJobObject.restype = w.BOOL
        kernel.GetProcessAffinityMask.argtypes = [
            w.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.GetProcessAffinityMask.restype = w.BOOL
        kernel.SetProcessAffinityMask.argtypes = [w.HANDLE, ctypes.c_size_t]
        kernel.SetProcessAffinityMask.restype = w.BOOL
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.CloseHandle.restype = w.BOOL
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000 | 0x100 | 0x200 | 0x8
        limits.basic.active = 1
        limits.process_memory = limits.job_memory = 1 << 30
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                             ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach(self, pid: int) -> int:
        process = self.kernel.OpenProcess(0x701, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
            if not self.kernel.GetProcessAffinityMask(
                    process, ctypes.byref(allowed), ctypes.byref(system)):
                raise ctypes.WinError(ctypes.get_last_error())
            single_cpu = allowed.value & -allowed.value
            if not single_cpu or not self.kernel.SetProcessAffinityMask(process, single_cpu):
                raise ctypes.WinError(ctypes.get_last_error())
            if not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
            return single_cpu
        finally:
            self.kernel.CloseHandle(process)

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


class BudgetStop(RuntimeError):
    pass


def worker(plan: dict, channel: Connection) -> None:
    if channel.recv() != "audit-cs-controller-ready":
        raise RuntimeError("worker requires the resource-limited controller handshake")
    channel.send(simulate(plan))
    channel.close()


def simulate(plan: dict) -> dict:
    started = time.perf_counter()
    import random
    from functools import lru_cache

    from scipy.stats import beta

    from asof.audit_cs import audit_confidence_set

    population, delta = plan["population"], plan["delta"]
    cases = [(k, mode) for k in plan["total_errors"] for mode in plan["missingness"]]
    limits = plan["limits"]
    results: list[dict] = []
    stopped = None

    @lru_cache(maxsize=16384)
    def cs(drawn: int, errors: int, unread: int):
        return audit_confidence_set(population, drawn, errors, unread, delta)

    def check() -> None:
        if time.perf_counter() - started >= limits["worker_soft_wall_seconds"]:
            raise BudgetStop("worker_soft_wall_ceiling")
        if time.process_time() >= limits["worker_CPU_seconds"]:
            raise BudgetStop("worker_CPU_ceiling")
        if resident_bytes() >= limits["RAM_bytes"]:
            raise BudgetStop("worker_RSS_ceiling")

    try:
        for i, (total, mode) in enumerate(cases):
            rng = random.Random(plan["seed"] + i)
            cell = {
                "total_errors": total, "missingness": mode, "seed": plan["seed"] + i,
                "attempted": 0, "anytime_noncoverage": 0, "first_error_stop_noncoverage": 0,
                "precision_stop_noncoverage": 0, "precision_stops_before_census": 0,
                "precision_stop_draw_sum": 0, "final_count_span_sum": 0,
            }
            results.append(cell)
            for _ in range(plan["replicates_per_cell"]):
                check()
                labels = [1] * total + [0] * (population - total)
                rng.shuffle(labels)
                errors = unread = 0
                missed = not cs(0, 0, 0).contains(total)
                first_error_missed = precision_missed = None
                precision_draw = population
                for position, label in enumerate(labels):
                    hidden = (
                        mode == "all_unread" or (mode == "hide_errors" and label == 1)
                        or (mode == "hide_nonerrors" and label == 0)
                        or (mode == "bursts" and position % 7 in (0, 1, 2)))
                    unread += hidden
                    errors += label == 1 and not hidden
                    result = cs(position + 1, errors, unread)
                    excluded = not result.contains(total)
                    missed |= excluded
                    if first_error_missed is None and errors:
                        first_error_missed = excluded
                    if (precision_missed is None and position + 1 >= 20
                            and result.intervals[-1][1] / population <= 0.10):
                        precision_missed, precision_draw = excluded, position + 1
                cell["attempted"] += 1
                cell["anytime_noncoverage"] += missed
                cell["first_error_stop_noncoverage"] += (
                    excluded if first_error_missed is None else first_error_missed)
                cell["precision_stop_noncoverage"] += (
                    excluded if precision_missed is None else precision_missed)
                cell["precision_stops_before_census"] += precision_draw < population
                cell["precision_stop_draw_sum"] += precision_draw
                cell["final_count_span_sum"] += (
                    result.intervals[-1][1] - result.intervals[0][0])
    except (BudgetStop, MemoryError) as exc:
        stopped = f"{type(exc).__name__}:{exc}"
    for cell in results:
        n, k = cell["attempted"], cell["anytime_noncoverage"]
        cell["simultaneous_95_MC_upper"] = (
            1.0 if n == 0 or k == n else float(beta.ppf(1 - 0.05 / len(cases), k + 1, n - k)))
    complete = (stopped is None and len(results) == len(cases)
                and all(c["attempted"] == plan["replicates_per_cell"] for c in results))
    return {
        "status": "complete" if complete else "stopped", "stop_reason": stopped,
        "implementation_QA_screen_passed": complete and all(
            c["simultaneous_95_MC_upper"] <= 0.075 for c in results),
        "attempted_paths": sum(c["attempted"] for c in results), "cells": results,
        "worker_CPU_seconds": time.process_time(),
        "worker_wall_seconds": time.perf_counter() - started,
        "worker_OS_peak_RSS_bytes": resident_bytes(),
        "state_cache": cs.cache_info()._asdict(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    plan = json.loads(PLAN.read_bytes())
    if REPORT.exists() or ATTEMPT.exists():
        raise FileExistsError("validation already attempted; no retry or automatic resume")
    if any(os.environ.get(k) != "1" for k in THREAD_VARIABLES):
        raise RuntimeError("set OPENBLAS/OMP/MKL/NUMEXPR_NUM_THREADS=1 before launch")
    validate_plan(plan)
    started = time.perf_counter()
    lineage, protected = frozen_lineage(), hashes(PROTECTED)
    ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    with ATTEMPT.open("x", encoding="utf-8") as stream:
        json.dump({"started_utc": datetime.now(UTC).isoformat(), "lineage": lineage}, stream)
    report = {
        "label": plan["label"], "lineage": lineage, "plan": plan,
        "scientific_acceptance": False, "qualifies_UTC": False,
        "reads_real_audit_counts": False, "creates_return_trial": False,
        "status": "stopped", "implementation_QA_screen_passed": False,
    }
    job = None
    process = None
    controller = child = None
    try:
        job = WorkerJob()
        context = multiprocessing.get_context("spawn")
        controller, child = context.Pipe()
        process = context.Process(target=worker, args=(plan, child))
        process.start()
        child.close()
        if process.pid is None:
            raise RuntimeError("owned worker did not acquire a process ID")
        report["worker_affinity_mask"] = job.attach(process.pid)
        controller.send("audit-cs-controller-ready")
        if not controller.poll(max(0.01, 300 - (time.perf_counter() - started))):
            raise TimeoutError("owned worker exceeded the controller deadline")
        output = controller.recv()
        if not isinstance(output, dict):
            raise TypeError("owned worker returned an invalid receipt")
        process.join(timeout=max(0.01, 300 - (time.perf_counter() - started)))
        if process.is_alive():
            raise TimeoutError("owned worker did not exit by the controller deadline")
        if process.exitcode != 0:
            raise RuntimeError(f"owned worker failed with exit code {process.exitcode}")
        report.update(output)
    except TimeoutError:
        report["stop_reason"] = "controller_wall_ceiling; unreported partial paths unknown"
    except (OSError, ValueError, TypeError, RuntimeError, EOFError) as exc:
        report["stop_reason"] = f"{type(exc).__name__}:{exc}"
    finally:
        if job is not None:
            job.close()
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
            report["worker_exit_code"] = process.exitcode
            process.close()
        if controller is not None:
            controller.close()
        if child is not None:
            child.close()
    report["controller_wall_seconds"] = time.perf_counter() - started
    report["controller_OS_peak_RSS_bytes"] = resident_bytes()
    report["protected_before_SHA256"] = protected
    report["protected_unchanged"] = hashes(PROTECTED) == protected
    report["source_unchanged"] = hashes(FROZEN) == lineage["SHA256"]
    combined_peak = (report["controller_OS_peak_RSS_bytes"]
                     + report.get("worker_OS_peak_RSS_bytes", 1 << 30))
    report["sum_of_separate_OS_RSS_peaks_bytes"] = combined_peak
    report["resource_check_passed"] = (
        report["controller_wall_seconds"] <= 300 and combined_peak < 1 << 30
        and report.get("worker_CPU_seconds", 301) <= 270)
    if not (report["protected_unchanged"] and report["source_unchanged"]
            and report["resource_check_passed"]):
        report["implementation_QA_screen_passed"] = False
    with REPORT.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in (
        "status", "implementation_QA_screen_passed", "resource_check_passed",
        "protected_unchanged", "source_unchanged", "controller_wall_seconds")}, indent=2))
    return 0 if report["implementation_QA_screen_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
