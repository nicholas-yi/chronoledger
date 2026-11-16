"""Read-only Windows working-set sampling for one explicitly owned process tree."""

from __future__ import annotations

import ctypes
import json
import os
import time
from ctypes import wintypes
from datetime import UTC, datetime, timedelta
from pathlib import Path


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
        ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
        ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
        ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260),
    ]


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "peak_working_set", "working_set", "peak_paged", "paged",
            "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile",
            "private_bytes",
        )
    ]


class MemoryTelemetry:
    def __init__(self, path: Path) -> None:
        if path.exists():
            raise RuntimeError("per_process_memory_log_already_exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.previous: dict[tuple[int, int], dict] = {}

    def record(self, root_pid: int, records: list[dict], context: dict) -> None:
        if set(context) - {"phase", "arm", "uid", "stage", "call_id", "options_SHA256"}:
            raise ValueError("memory_context_must_not_include_prompt_or_answer_payload")
        allowed = {"pid","parent_pid","process_basename","creation_filetime","created_UTC",
                   "working_set_bytes","process_peak_working_set_bytes","private_bytes",
                   "commit_bytes","CPU_seconds"}
        if any(set(record)-allowed for record in records):
            raise ValueError("process_record_must_not_include_payload_or_commandline")
        current = {(r["pid"], r["creation_filetime"]): r for r in records}
        if len(current) != len(records) or not any(r["pid"] == root_pid for r in records):
            raise ValueError("owned_process_snapshot_malformed")
        row = {"timestamp_UTC": datetime.now(UTC).isoformat(),
               "monotonic_seconds": time.monotonic(), "root_PID": root_pid,
               "context": dict(context), "processes": records,
               "observed_starts": [{"pid":p,"creation_filetime":c}
                                    for p,c in sorted(current.keys()-self.previous.keys())],
               "observed_exits": [{"pid":p,"creation_filetime":c}
                                   for p,c in sorted(self.previous.keys()-current.keys())],
               "owned_working_set_bytes": sum(r["working_set_bytes"] for r in records)}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
        self.previous = current


class OwnedMemory:
    def __init__(self, root_pid: int, *, telemetry_path: Path | None = None,
                 context: dict | None = None) -> None:
        if os.name != "nt" or type(root_pid) is not int or root_pid <= 0:
            raise ValueError("positive owned Windows server PID required")
        self.root_pid = root_pid
        self.peak = 0
        self.exited_children = 0
        self.context = context if context is not None else {}
        self.telemetry = MemoryTelemetry(telemetry_path) if telemetry_path is not None else None
        self.root_creation: int | None = None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.psapi = ctypes.WinDLL("psapi", use_last_error=True)
        self.kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        for name in ("Process32FirstW", "Process32NextW"):
            method = getattr(self.kernel, name)
            method.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
            method.restype = wintypes.BOOL
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [
            wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4]
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD,
        ]
        self.psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    def sample(self) -> int:
        snapshot = self.kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        processes, names = {}, {}
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            ok = self.kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                processes[entry.pid] = entry.parent
                names[entry.pid] = entry.name
                ok = self.kernel.Process32NextW(snapshot, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.kernel.CloseHandle(snapshot)
        if self.root_pid not in processes:
            raise RuntimeError("owned isolated server exited")
        owned = {self.root_pid}
        while True:
            children = {pid for pid, parent in processes.items() if parent in owned}
            updated = owned | children
            if updated == owned:
                break
            owned = updated
        total, records = 0, []
        for pid in sorted(owned):
            handle = self.kernel.OpenProcess(0x1010, False, pid)
            if not handle:
                error = ctypes.get_last_error()
                if error == 87 and pid != self.root_pid:
                    self.exited_children += 1
                    continue
                raise ctypes.WinError(error)
            try:
                memory = MemoryCounters()
                memory.cb = ctypes.sizeof(memory)
                if not self.psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
                    raise ctypes.WinError(ctypes.get_last_error())
                total += memory.working_set
                if self.telemetry is not None:
                    creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
                    if not self.kernel.GetProcessTimes(handle, ctypes.byref(creation),
                        ctypes.byref(exit_time), ctypes.byref(kernel_time), ctypes.byref(user_time)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    def ticks(value):
                        return (value.dwHighDateTime << 32) + value.dwLowDateTime
                    created = ticks(creation)
                    if pid == self.root_pid:
                        if self.root_creation is not None and created != self.root_creation:
                            raise RuntimeError("owned_root_PID_reused")
                        self.root_creation = created
                    records.append({
                        "pid":pid,"parent_pid":processes[pid],"process_basename":names[pid],
                        "creation_filetime":created,
                        "created_UTC":(datetime(1601,1,1,tzinfo=UTC)+timedelta(
                            microseconds=created//10)).isoformat(),
                        "working_set_bytes":memory.working_set,
                        "process_peak_working_set_bytes":memory.peak_working_set,
                        "private_bytes":memory.private_bytes,"commit_bytes":memory.pagefile,
                        "CPU_seconds":(ticks(kernel_time)+ticks(user_time))/10_000_000})
            finally:
                self.kernel.CloseHandle(handle)
        self.peak = max(self.peak, total)
        if self.telemetry is not None:
            self.telemetry.record(self.root_pid, records, self.context)
        return total
