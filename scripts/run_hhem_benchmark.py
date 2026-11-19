"""One offline pinned HHEM benchmark in an explicitly selected owned CPU worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from asof.hhem_verifier import benchmark, fixture, summarize
from asof.runtime import THREAD_VARIABLES, WorkerJob, frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "src/asof/hhem_verifier.py", "src/asof/reader_regression.py", "src/asof/reader_fields.py",
    "src/asof/linked_reader.py", "src/asof/runtime.py", "src/asof/reader_cells.py",
    "src/asof/reader_field_challenge.py", "src/asof/reader_reliability.py",
    "src/asof/reader_stress.py", "src/asof/verified_reader.py", "src/asof/focused_reader.py",
    "src/asof/extraction.py", "scripts/run_hhem_benchmark.py", "scripts/prepare_hhem_assets.py",
    "scripts/check_reader_regressions.py", "tests/test_hhem_verifier.py",
    "tests/test_reader_fields.py", "tests/test_reader_regression.py",
    "tests/fixtures/focused_reader.json", "tests/fixtures/verified_reader.json",
    "tests/fixtures/reader_stress.json", "tests/fixtures/linked_challenge.json",
    "tests/fixtures/reader_fields.json", "tests/fixtures/reader_reliability.json",
    "results/hhem_assets.json", "results/hhem_environment.json", "results/hhem_plan.json",
    "docs/FOCUSED_READER.md", "pyproject.toml",
    "results/focused_reader.json", "results/focused_reader_v2.json", "results/verified_reader.json",
    "results/reader_stress.json", "results/linked_reader.json", "results/reader_fields.json",
    "results/reader_reliability.json", "results/reader_cell_selection.json",
    "results/reader_cell_selection_accounting.json", "results/reader_ai_review.json",
)


def worker() -> int:
    if sys.stdin.readline().strip() != "owned-hhem-job-ready":
        raise RuntimeError("ownedHHEMJobcontainmenthandshake required")

    def emit(message):
        print(json.dumps(message, allow_nan=False), flush=True)

    try:
        result = benchmark(ROOT, emit)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        emit({"kind": "failure", "reason": f"{type(exc).__name__}:{exc}"})
        return 2
    emit({"kind": "final", "result": result})
    if sys.stdin.readline().strip() != "controller-received-final":
        raise RuntimeError("controllerfinalreceiptacknowledgementmissing")
    return 0


def run(python: Path) -> int:
    from asof.reader_regression import regression_matrix

    report_path = ROOT / "results" / "hhem_benchmark.json"
    private = ROOT / "data" / "hhem_benchmark_v1"
    if report_path.exists() or (private / "attempt.json").exists():
        raise FileExistsError("HHEMattemptalreadyexists;noautomaticretry")
    plan = json.loads((ROOT / "results" / "hhem_plan.json").read_bytes())
    fixed = {"profile": "HHEM-LOCAL-01", "max_cases": 24, "threshold": 0.5,
             "wall_seconds": 1200, "controller_stop_seconds": 1180,
             "RAM_bytes": 6 << 30, "controller_RAM_allowance": 128 << 20,
             "CPU_count": 1, "input_token_cap": 2048, "GPU": False}
    if plan != fixed or any(os.environ.get(key) != "1" for key in THREAD_VARIABLES):
        raise ValueError("verifierallocationorthreadenvironmentdiffers")
    if not python.is_file():
        raise FileNotFoundError("explicitisolatedverifierPythonrequired")
    lineage = frozen_receipt(ROOT, SOURCES)
    private.mkdir(parents=True, exist_ok=True)
    write_receipt(private / "attempt.json", {"lineage": lineage, "plan": plan})
    report = {
        "status": "stopped", "stop_reason": None, "rows": [], "started_cases": [],
        "lineage": lineage, "plan": plan,
        "real_data_read": False, "model": "vectara/hallucination_evaluation_model",
        "production_ledger_rows": 0, "training": False, "decision_authority": "advisory_only",
    }
    started = time.monotonic()
    report["current_regressions"] = regression_matrix(ROOT)
    environment = dict(os.environ)
    environment.update(
        PYTHONPATH=str(ROOT / "src"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false", CUDA_VISIBLE_DEVICES="-1",
        HF_MODULES_CACHE=str(private / "reviewed_module_cache"))
    process = job = None
    original_affinity = None
    peak, owned = 0, set()
    messages = queue.Queue()
    try:
        job = WorkerJob(memory_bytes=plan["RAM_bytes"]-plan["controller_RAM_allowance"], max_processes=2)
        with (private / "worker.log").open("xb") as log:
            process = subprocess.Popen(
                [str(python), "-u", str(Path(__file__).resolve()), "--worker"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True, env=environment)
            mask = job.attach(process.pid)
            original_affinity = job.pin(os.getpid(), mask)
            report["affinity_mask"] = mask

            def read_lines():
                for line in process.stdout:
                    messages.put(line)
                messages.put(None)

            threading.Thread(target=read_lines, daemon=True).start()
            process.stdin.write("owned-hhem-job-ready\n")
            process.stdin.flush()
            final = None
            while final is None:
                if time.monotonic()-started >= plan["controller_stop_seconds"]:
                    raise TimeoutError("ownedverifierwallceiling")
                sample = job.sample()
                owned.update(row["pid"] for row in sample["processes"])
                if any(row["affinity_mask"] != mask for row in sample["processes"]):
                    raise RuntimeError("verifierdidnotinheritoneCPUaffinity")
                peak = max(peak, sample["RSS_bytes"]+peak_rss_bytes())
                if peak >= plan["RAM_bytes"]:
                    raise RuntimeError("verifiercombinedworking-setlimit")
                with (private / "resources.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"elapsed": time.monotonic()-started, **sample})+"\n")
                try:
                    line = messages.get(timeout=0.25)
                except queue.Empty:
                    continue
                if line is None:
                    raise RuntimeError("verifierworkerclosedwithoutfinal")
                message = json.loads(line)
                if message["kind"] == "case":
                    report["rows"].append(message["row"])
                elif message["kind"] == "case_started":
                    report["started_cases"].append(message["id"])
                elif message["kind"] == "loaded":
                    report["load"] = message
                elif message["kind"] == "failure":
                    raise RuntimeError(message["reason"])
                elif message["kind"] == "final":
                    final = message["result"]
                else:
                    raise ValueError("unknownverifiermessage")
            report.update(final)
            process.stdin.write("controller-received-final\n")
            process.stdin.flush()
            process.wait(timeout=10)
            if process.returncode != 0:
                raise RuntimeError("verifierworkerexitnotzero")
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        report["status"], report["stop_reason"] = "stopped", f"{type(exc).__name__}:{exc}"
    finally:
        if job is not None:
            try:
                if original_affinity is not None:
                    job.pin(os.getpid(), original_affinity)
            finally:
                job.close()
        if process is not None:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            report["worker_exit_code"] = process.returncode
            process.stdin.close()
            process.stdout.close()
    recorded = {row["id"] for row in report["rows"]}
    report["rows"].extend({"id": uid, "support_score": None, "status": "incomplete_attempt",
                           "latency_seconds": None}
                          for uid in report["started_cases"] if uid not in recorded)
    report.update(
        summary=summarize(report["rows"]), controller_wall_seconds=time.monotonic()-started,
        observed_combined_peak_RSS_bytes=peak, owned_pids_observed=sorted(owned),
        fixture_sha256=hashlib.sha256(json.dumps(fixture(), sort_keys=True).encode()).hexdigest(),
    )
    report["source_unchanged"] = frozen_sources_match(lineage)
    report["resource_check_passed"] = (
        report["controller_wall_seconds"] < plan["wall_seconds"]
        and peak < plan["RAM_bytes"] and report.get("affinity_mask", 0).bit_count() == 1
        and len(report["rows"]) <= plan["max_cases"])
    if not report["source_unchanged"] or not report["resource_check_passed"]:
        report["status"], report["stop_reason"] = "stopped", "source_or_resource_contract_failed"
    write_receipt(report_path, report)
    print(json.dumps({key: report[key] for key in (
        "status", "stop_reason", "summary", "source_unchanged", "resource_check_passed",
        "controller_wall_seconds", "observed_combined_peak_RSS_bytes")}, indent=2))
    return 0 if report["status"] == "complete_invented_entailment_benchmark" else 2


def frozen_sources_match(lineage: dict) -> bool:
    return all(hashlib.sha256(ROOT.joinpath(*name.split("/")).read_bytes()).hexdigest() == digest
               for name, digest in lineage["source_SHA256"].items())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--python", type=Path)
    args = parser.parse_args()
    if args.worker:
        raise SystemExit(worker())
    if not args.execute or args.python is None:
        parser.error("--execute and explicit --python required")
    raise SystemExit(run(args.python.resolve()))
