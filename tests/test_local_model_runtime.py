import json
from types import SimpleNamespace

import pytest

from asof import local_model_runtime as runtime
from asof.benchmark_baseline import TableInput
from asof.reader_positive_control import ANSWER_FIRST_SYSTEM


def test_documented_cache_environment_and_answer_first_default_do_not_mutate_parent():
    policy = runtime.RuntimePolicy()
    parent = {"OLLAMA_HOST":"127.0.0.1:11434","LLAMA_ARG_CACHE_RAM":"8192","KEEP":"yes"}
    environment = policy.environment(parent)
    assert environment["LLAMA_ARG_CACHE_RAM"] == "0"
    assert environment["OLLAMA_HOST"] == "127.0.0.1:11435"
    assert environment["KEEP"] == "yes" and parent["LLAMA_ARG_CACHE_RAM"] == "8192"
    manifest = policy.manifest()
    assert manifest["native_environment"] == {"LLAMA_ARG_CACHE_RAM":"0"}
    body = runtime.answer_first_request(TableInput("invented",(),()),model="toy",options={})
    assert body["messages"][0]["content"] == ANSWER_FIRST_SYSTEM
    with pytest.raises(ValueError):
        runtime.RuntimePolicy(-1)


def test_future_launcher_only_mocked_passes_frozen_native_setting_and_receipt(tmp_path, monkeypatch):
    executable = tmp_path / "synthetic-ollama.exe"
    executable.write_bytes(b"synthetic executable,not run")
    captured = []

    def popen(args, **kwargs):
        captured.append((args,kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(runtime.subprocess,"Popen",popen)
    receipt = tmp_path / "runtime.json"
    process = runtime.launch_owned_server(executable,tmp_path/"server.log",receipt,runtime.RuntimePolicy())
    assert process.pid == 12345 and captured[0][0] == [str(executable),"serve"]
    assert captured[0][1]["env"]["LLAMA_ARG_CACHE_RAM"] == "0"
    assert captured[0][1]["env"]["OLLAMA_HOST"] == "127.0.0.1:11435"
    saved = json.loads(receipt.read_text())
    runtime.verify_runtime_receipt(receipt,12345,saved["policy"])
    with pytest.raises(ValueError):
        runtime.verify_runtime_receipt(receipt,12346,saved["policy"])
    with pytest.raises(RuntimeError):
        runtime.launch_owned_server(executable,tmp_path/"other.log",receipt,runtime.RuntimePolicy())


def test_launcher_receipt_failure_terminates_only_its_mocked_child(tmp_path, monkeypatch):
    executable = tmp_path/"synthetic.exe"
    executable.write_bytes(b"not run")
    receipt = tmp_path/"runtime.json"
    actions = []
    process = SimpleNamespace(pid=12345,terminate=lambda:actions.append("terminate"),
                              wait=lambda timeout:actions.append(("wait",timeout)))
    monkeypatch.setattr(runtime.subprocess,"Popen",lambda *a,**k:process)
    original = type(receipt).write_text

    def write(path,*args,**kwargs):
        if path == receipt:
            raise OSError("synthetic receipt failure")
        return original(path,*args,**kwargs)

    monkeypatch.setattr(type(receipt),"write_text",write)
    with pytest.raises(OSError):
        runtime.launch_owned_server(executable,tmp_path/"server.log",receipt,runtime.RuntimePolicy())
    assert actions == ["terminate",("wait",10)]
