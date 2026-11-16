import ctypes
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def memory_module():
    path = Path(__file__).resolve().parents[1]/"scripts"/"reader_real1_memory.py"
    spec = importlib.util.spec_from_file_location("memory_telemetry",path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_PID_reuse_events_and_no_payload_logging(tmp_path):
    m = memory_module()
    path = tmp_path/"process.jsonl"
    telemetry = m.MemoryTelemetry(path)
    root = {"pid":100,"creation_filetime":10,"working_set_bytes":1000}
    old = {"pid":200,"creation_filetime":20,"working_set_bytes":2000}
    new = {"pid":200,"creation_filetime":30,"working_set_bytes":3000}
    telemetry.record(100,[root,old],{"phase":"test","uid":"synthetic"})
    telemetry.record(100,[root,new],{"phase":"test"})
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert rows[-1]["owned_working_set_bytes"] == 4000
    assert rows[-1]["observed_starts"] == [{"pid":200,"creation_filetime":30}]
    assert rows[-1]["observed_exits"] == [{"pid":200,"creation_filetime":20}]
    with pytest.raises(ValueError):
        telemetry.record(100,[root],{"question":"must not log"})
    with pytest.raises(ValueError):
        telemetry.record(100,[{**root,"commandline":"must not log"}],{})


def test_native_sampler_with_mocked_Windows_edges_logs_each_owned_PID(tmp_path, monkeypatch):
    m = memory_module()
    entries = [(100,0,"synthetic-server.exe"),(200,100,"synthetic-runner.exe"),(999,0,"unowned.exe")]
    index = [0]

    def entry(ptr):
        target = ctypes.cast(ptr,ctypes.POINTER(m.ProcessEntry)).contents
        target.pid,target.parent,target.name = entries[index[0]]
        return True

    def first(handle,ptr):
        index[0] = 0
        return entry(ptr)

    def following(handle,ptr):
        index[0] += 1
        return entry(ptr) if index[0] < len(entries) else False

    def process_times(pid,*pointers):
        for pointer,value in zip(pointers,(pid*10,0,20_000_000,30_000_000),strict=True):
            target = ctypes.cast(pointer,ctypes.POINTER(m.wintypes.FILETIME)).contents
            target.dwLowDateTime = value
            target.dwHighDateTime = 0
        return True

    def process_memory(pid,pointer,size):
        target = ctypes.cast(pointer,ctypes.POINTER(m.MemoryCounters)).contents
        target.working_set = pid*10
        target.peak_working_set = pid*11
        target.private_bytes = pid*12
        target.pagefile = pid*13
        return True

    monkeypatch.setattr(m.ctypes,"get_last_error",lambda:18,raising=False)
    sampler = object.__new__(m.OwnedMemory)
    sampler.root_pid,sampler.peak,sampler.exited_children = 100,0,0
    sampler.root_creation = None
    sampler.context = {"phase":"test"}
    sampler.telemetry = m.MemoryTelemetry(tmp_path/"native.jsonl")
    sampler.kernel = SimpleNamespace(CreateToolhelp32Snapshot=lambda *a:1,Process32FirstW=first,
        Process32NextW=following,CloseHandle=lambda *a:None,OpenProcess=lambda access,inherit,pid:pid,
        GetProcessTimes=process_times)
    sampler.psapi = SimpleNamespace(GetProcessMemoryInfo=process_memory)
    assert sampler.sample() == 3000
    saved = json.loads((tmp_path/"native.jsonl").read_text())
    assert [r["pid"] for r in saved["processes"]] == [100,200]
    assert saved["processes"][1]["private_bytes"] == 2400
    assert saved["processes"][1]["CPU_seconds"] == 5
