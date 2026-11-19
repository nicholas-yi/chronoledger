"""Reusable owned-process resource and receipt utilities for NEW runners.

Historical frozen scripts retain their original implementations and source hashes.
Job commit limits and observed RSS differ; this is not filesystem/network isolation.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from pathlib import Path

THREAD_VARIABLES = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS")


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

    def __init__(self, *, memory_bytes: int = 1 << 30) -> None:
        if isinstance(memory_bytes, bool) or not isinstance(memory_bytes, int) or memory_bytes <= 0:
            raise ValueError("owned-worker memory limit must be a positive byte count")
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
        limits.basic.active = 1
        limits.process_memory = limits.job_memory = memory_bytes
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                             ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def _process(self, pid: int):
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("a specific positive PID is required")
        process = self.kernel.OpenProcess(0x701, False, pid)
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
