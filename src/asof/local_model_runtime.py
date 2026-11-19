"""Frozen policy for future owned local servers; default reader is answer-first."""

from __future__ import annotations

import json
import math
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from asof import ledger
from asof.benchmark_baseline import TableInput
from asof.config import PROJECT_ROOT
from asof.reader_positive_control import SyntheticCase, control_body

DEFAULT_READER = "answer_first"
SUPPORT = PROJECT_ROOT / "results" / "local_model_runtime_support.json"


@dataclass(frozen=True)
class RuntimePolicy:
    prompt_cache_MiB: int = 0

    def __post_init__(self) -> None:
        if type(self.prompt_cache_MiB) is not int or not 0 <= self.prompt_cache_MiB <= 8192:
            raise ValueError("finite_supported_prompt_cache_bound_required")

    def manifest(self) -> dict:
        return {
            "default_reader": DEFAULT_READER,
            "strict_formats": "stopped_experimental_not_default",
            "host": "127.0.0.1:11435",
            "prompt_cache_MiB": self.prompt_cache_MiB,
            "native_environment": {"LLAMA_ARG_CACHE_RAM": str(self.prompt_cache_MiB)},
            "documentation": "results/local_model_runtime_support.json",
            "support_document_SHA256": ledger.file_sha256(SUPPORT),
            "validation_limit": "Documented shipped native flag plus mocked launcher tests; "
                                "no live cache-effect or memory-cure validation in this task.",
        }

    def environment(self, parent: dict[str, str] | None = None) -> dict[str, str]:
        value = dict(os.environ if parent is None else parent)
        value.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_NUM_PARALLEL="1",
                     OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_NO_CLOUD="1",
                     LLAMA_ARG_CACHE_RAM=str(self.prompt_cache_MiB))
        return value


def answer_first_request(item: TableInput, *, model: str, options: dict) -> dict:
    return control_body(SyntheticCase("local", "local", item, None), "answer_first",
                        model=model, options=options)


def launch_owned_server(
    executable: Path, log_path: Path, receipt_path: Path, policy: RuntimePolicy,
) -> subprocess.Popen:
    """Explicit future launch only; callers/tests must opt in and own the returned PID."""
    if receipt_path.exists():
        raise RuntimeError("runtime_receipt_exists_no_implicit_restart")
    executable_digest = ledger.file_sha256(executable)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    environment = policy.environment()
    with log_path.open("xb") as stream:
        process = subprocess.Popen([str(executable), "serve"], env=environment,
                                   stdout=stream, stderr=subprocess.STDOUT)
    receipt = {"owned_server_PID": process.pid, "policy": policy.manifest(),
               "executable_SHA256": executable_digest,
               "launch": "Explicit owned11435server only,no model pull or inference performed by launcher."}
    try:
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    except OSError:
        process.terminate()
        process.wait(timeout=10)
        raise
    return process


def verify_runtime_receipt(path: Path, pid: int, policy: dict) -> None:
    receipt = json.loads(path.read_bytes())
    if receipt["owned_server_PID"] != pid or receipt["policy"] != policy:
        raise ValueError("owned_server_runtime_policy_mismatch")


def verify_supported_package(executable: Path) -> dict:
    support = json.loads(SUPPORT.read_bytes())
    paths = {
        executable: support["Ollama_executable_SHA256"],
        executable.parent / support["native_backend"]["relative_executable"]:
            support["native_backend"]["executable_SHA256"],
        executable.parent / support["native_backend"]["relative_implementation"]:
            support["native_backend"]["implementation_SHA256"],
    }
    if any(ledger.file_sha256(path).lower() != digest for path,digest in paths.items()):
        raise ValueError("pinned_Ollama_or_native_backend_changed_requalify_cache_setting")
    return {"support_document_SHA256":ledger.file_sha256(SUPPORT),
            "package_verified":True}


def preload_owned_model(client: httpx.Client, *, model: str, options: dict, seconds: float) -> dict:
    """Load only within the existing startup deadline; never disguise generation as warmup."""
    if not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError("model preload must fit the remaining60secondstartupbudget")
    started = time.monotonic()
    response = client.post("/api/generate", json={
        "model": model, "prompt": "", "stream": False, "keep_alive": "20m", "options": options,
    }, timeout=seconds)
    response.raise_for_status()
    raw = response.json()
    if (raw.get("done") is not True or raw.get("response") != ""
            or raw.get("eval_count") not in (None, 0)
            or raw.get("prompt_eval_count") not in (None, 0)):
        raise ValueError("preload response contains generation or incomplete load evidence")
    elapsed = time.monotonic()-started
    remaining = seconds-elapsed
    if remaining <= 0:
        raise TimeoutError("model preload exhaustedstartupdeadline")
    state = client.get("/api/ps", timeout=remaining)
    state.raise_for_status()
    models = state.json().get("models", [])
    if not models or any(row.get("name") != model or row.get("size_vram") != 0 for row in models):
        raise ValueError("ownedpreloadmodelidentityorCPUstateunverified")
    if time.monotonic()-started >= seconds:
        raise TimeoutError("model preload exceededstartupdeadline")
    return {
        "status": "load_only_complete", "wall_seconds": time.monotonic()-started,
        "model": model, "generated_tokens_reported": raw.get("eval_count"),
        "load_duration_ns": raw.get("load_duration"), "response_text_empty": True,
        "separate_from_evaluated_generation": True,
        "documentation": "https://github.com/ollama/ollama/blob/main/docs/api.md#load-a-model",
    }
