"""Read-only Windows working-set sampling for one explicitly owned process tree."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


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
        )
    ]


class OwnedMemory:
    def __init__(self, root_pid: int) -> None:
        if os.name != "nt" or type(root_pid) is not int or root_pid <= 0:
            raise ValueError("positive owned Windows server PID required")
        self.root_pid = root_pid
        self.peak = 0
        self.exited_children = 0
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
        self.psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD,
        ]
        self.psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    def sample(self) -> int:
        snapshot = self.kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        processes = {}
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            ok = self.kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                processes[entry.pid] = entry.parent
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
        total = 0
        for pid in owned:
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
            finally:
                self.kernel.CloseHandle(handle)
        self.peak = max(self.peak, total)
        return total
