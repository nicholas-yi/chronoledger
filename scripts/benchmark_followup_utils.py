"""Shared intake/version/resource helpers for the bounded benchmark follow-up only."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

from calibrate_inference import resident_bytes
from run_benchmark_diagnostic import ROOT, verified_assets

from asof import ledger
from asof.config import PROJECT_ROOT

V1 = ROOT.parent / "bench_2" / "baseline_v1.py"
ORIGINAL_CONFIG = PROJECT_ROOT / "results" / "benchmark_diagnostic_config.json"
ORIGINAL_RECEIPT = PROJECT_ROOT / "results" / "benchmark_diagnostic_status.json"
FOLLOWUP = PROJECT_ROOT / "results" / "benchmark_followup_status.json"


def load_v1():
    expected = json.loads(ORIGINAL_CONFIG.read_text())["baseline_file_sha256"]
    if ledger.file_sha256(V1) != expected:
        raise ValueError("frozen a36126d baseline cache differs")
    spec = importlib.util.spec_from_file_location("benchmark_baseline_a36126d", V1)
    if spec is None or spec.loader is None:
        raise ImportError("frozen baseline cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Budget:
    def __init__(self) -> None:
        if any(os.environ.get(k) != "1"
               for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
            raise RuntimeError("single-thread flags required")
        self.cpu_start, self.wall_start = time.process_time(), time.monotonic()
        self.peak = 0
        previous = read_followup()
        spent = sum(part.get("resources", {}).get("CPU_seconds", 0.0)
                    for part in previous.values() if isinstance(part, dict))
        self.allowance = max(0.0, 720 - spent)

    def check(self) -> None:
        self.peak = max(self.peak, resident_bytes())
        if time.process_time() - self.cpu_start >= self.allowance or self.peak >= 1 << 30:
            raise RuntimeError("follow-up resource ceiling")

    def receipt(self) -> dict:
        self.peak = max(self.peak, resident_bytes())
        return {"CPU_seconds": time.process_time() - self.cpu_start,
                "wall_seconds": time.monotonic() - self.wall_start,
                "peak_resident_bytes": self.peak, "threads": 1,
                "shared_scoring_CPU_seconds_limit": 720,
                "batch_CPU_seconds_limit": 900}


def read_followup() -> dict:
    return json.loads(FOLLOWUP.read_text()) if FOLLOWUP.exists() else {
        "label": "SMALL NON-MODEL DEVELOPMENT DIAGNOSTICS; not formal H1 or historical usability"}


def assert_frozen(config: dict, runner: Path) -> None:
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit source before scoring")
    if ledger.file_sha256(runner) != config["runner_sha256"]:
        raise ValueError("runner changed after freeze")
    if verified_assets() != config["assets"]:
        raise ValueError("benchmark inputs or scorers changed")
    if ledger.file_sha256(ORIGINAL_RECEIPT) != config["original_receipt_sha256"]:
        raise ValueError("the first diagnostic must remain unchanged")
