"""Reusable owned-process resource and receipt utilities for NEW runners.

Historical frozen scripts retain their original implementations and source hashes.
Job commit limits and observed RSS differ; this is not filesystem/network isolation.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

THREAD_VARIABLES = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS")


def frozen_receipt(root: Path, paths: tuple[str, ...]) -> dict:
    """Verify a clean committed source/config selection; never inspect unlisted data payloads."""
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "--no-pager", *args], cwd=root)

    if git("status", "--porcelain").strip():
        raise RuntimeError("commit source, fixtures and scope before execution")
    hashes = {}
    for path in paths:
        local = root.joinpath(*path.split("/")).read_bytes()
        if git("show", f"HEAD:{path}").replace(b"\r\n", b"\n") != local.replace(b"\r\n", b"\n"):
            raise RuntimeError(f"source differs from its freeze: {path}")
        hashes[path] = hashlib.sha256(local).hexdigest()
    return {"freeze_commit": git("rev-parse", "HEAD").decode().strip(), "source_SHA256": hashes,
            "matching_policy": "LF/CRLF equivalence only; hashes record raw local bytes"}


def write_receipt(path: Path, payload: dict) -> None:
    """Serialize strictly before exclusive creation; refuse replacement, NaN and infinity."""
    data = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def peak_rss_bytes() -> int:
    if os.name == "nt":
        from ctypes import wintypes as w

        class Counters(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("faults", w.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
                    "pagefile", "peak_pagefile")]

        values = Counters()
        values.cb = ctypes.sizeof(values)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = w.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Counters), w.DWORD]
        psapi.GetProcessMemoryInfo.restype = w.BOOL
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(values), values.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(values.peak_ws)
    import resource

    scale = 1 if sys.platform == "darwin" else 1024
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale)


class WorkerJob:
    """Windows kill-on-close Job: one owned child process, private-commit limit and one CPU.

    Callers must start a gated worker, attach it, then release the gate. Attaching after
    computation begins is not safe containment. Only the supplied PID is affected.
    """

    def __init__(self, *, memory_bytes: int = 1 << 30, max_processes: int = 1) -> None:
        if isinstance(memory_bytes, bool) or not isinstance(memory_bytes, int) or memory_bytes <= 0:
            raise ValueError("owned-worker memory limit must be a positive byte count")
        if (isinstance(max_processes, bool) or not isinstance(max_processes, int)
                or not 1 <= max_processes <= 4):
            raise ValueError("owned-process limit must be an integer in [1,4]")
        if os.name != "nt":
            raise OSError("strict owned-worker Job containment currently requires Windows")
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
        limits.basic.active = max_processes
        limits.process_memory = limits.job_memory = memory_bytes
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                             ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error
        self.max_processes = max_processes
        kernel.QueryInformationJobObject.argtypes = [
            w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
        kernel.QueryInformationJobObject.restype = w.BOOL

    def _process(self, pid: int):
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("a specific positive PID is required")
        process = self.kernel.OpenProcess(0x711, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        return process

    def pin(self, pid: int, mask: int | None = None) -> int:
        """Set a permitted affinity mask, returning the original mask for restoration."""
        process = self._process(pid)
        try:
            allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
            if not self.kernel.GetProcessAffinityMask(
                    process, ctypes.byref(allowed), ctypes.byref(system)):
                raise ctypes.WinError(ctypes.get_last_error())
            chosen = allowed.value & -allowed.value if mask is None else mask
            if (isinstance(chosen, bool) or not isinstance(chosen, int) or chosen <= 0
                    or chosen & ~system.value):
                raise ValueError("affinity must be a nonempty permitted CPU mask")
            if not self.kernel.SetProcessAffinityMask(process, chosen):
                raise ctypes.WinError(ctypes.get_last_error())
            return allowed.value
        finally:
            self.kernel.CloseHandle(process)

    def attach(self, pid: int) -> int:
        if not self.handle:
            raise RuntimeError("Job is already closed")
        process = self._process(pid)
        try:
            allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
            if not self.kernel.GetProcessAffinityMask(
                    process, ctypes.byref(allowed), ctypes.byref(system)):
                raise ctypes.WinError(ctypes.get_last_error())
            mask = allowed.value & -allowed.value
            if not mask or not self.kernel.SetProcessAffinityMask(process, mask):
                raise ctypes.WinError(ctypes.get_last_error())
            if not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
            return mask
        finally:
            self.kernel.CloseHandle(process)

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())

    def sample(self) -> dict:
        """Current Job members, RSS/CPU/affinity, without command lines or prompt payloads."""
        from ctypes import wintypes as w

        class Members(ctypes.Structure):
            _fields_ = [("assigned", w.DWORD), ("listed", w.DWORD),
                        ("pids", ctypes.c_size_t * 4)]

        class Counters(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("faults", w.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
                    "pagefile", "peak_pagefile")]

        members, returned = Members(), w.DWORD()
        if not self.kernel.QueryInformationJobObject(
                self.handle, 3, ctypes.byref(members), ctypes.sizeof(members), ctypes.byref(returned)):
            raise ctypes.WinError(ctypes.get_last_error())
        if members.listed > self.max_processes or members.assigned != members.listed:
            raise RuntimeError("owned Job membership incomplete or exceeds its declared process limit")
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Counters), w.DWORD]
        psapi.GetProcessMemoryInfo.restype = w.BOOL
        self.kernel.GetProcessTimes.argtypes = [
            w.HANDLE, *[ctypes.POINTER(w.FILETIME)] * 4]
        self.kernel.GetProcessTimes.restype = w.BOOL
        rows = []
        for pid in members.pids[:members.listed]:
            process = self._process(int(pid))
            try:
                counters = Counters()
                counters.cb = ctypes.sizeof(counters)
                allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
                timestamps = [w.FILETIME() for _ in range(4)]
                if (not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
                        or not self.kernel.GetProcessAffinityMask(
                            process, ctypes.byref(allowed), ctypes.byref(system))
                        or not self.kernel.GetProcessTimes(
                            process, *(ctypes.byref(value) for value in timestamps))):
                    raise ctypes.WinError(ctypes.get_last_error())
                cpu = sum((value.dwHighDateTime << 32) + value.dwLowDateTime
                          for value in timestamps[2:]) / 10_000_000
                rows.append({"pid": int(pid), "RSS_bytes": int(counters.ws),
                             "affinity_mask": allowed.value, "CPU_seconds": cpu})
            finally:
                self.kernel.CloseHandle(process)
        return {"processes": rows, "RSS_bytes": sum(row["RSS_bytes"] for row in rows)}
