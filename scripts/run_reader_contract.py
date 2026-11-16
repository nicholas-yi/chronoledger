"""Freeze and run one invented-only typed-reader control. Never opens benchmark items."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
from pydantic import ValidationError
from reader_real1_memory import OwnedMemory
from run_reader_positive_control import DIGEST, ENDPOINT, MODEL, ResourceStop, guarded_request
from run_reader_real2 import CPURecorder, wait_for_launch
from run_reader_real2_completion import SleepAwareCPU

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_contract import SYSTEM, ContractAnswer, Control, passed, request_body, resolve
from asof.reader_real2_guards import SustainedCPU, input_fit, truncation_reason

CONFIG = PROJECT_ROOT / "results" / "reader_contract_config.json"
STATUS = PROJECT_ROOT / "results" / "reader_contract_status.json"
ITEMS = PROJECT_ROOT / "tests" / "fixtures" / "reader_contract_controls.json"
PRIVATE = DATA_DIR / "reader_contract"
SERVER_LOG = PRIVATE / "isolated-server.log"
WALL = 1800
OPTIONS = {"temperature": 0, "seed": 2026111602, "num_predict": 768, "num_ctx": 8192,
           "num_thread": 4, "num_gpu": 0, "num_batch": 128}
NATIVE = {
    "tatqa_metric.py": "2aeeac479f89f8c76300af1cc0e8d098eb86af84bc386b38b6ab4af484a6dea8",
    "tatqa_utils.py": "a84bb2f960737cf0a53733637a674cc4b20ef030a2be6a4b21dc2c4356f415ec",
}
SOURCES = [Path(__file__), ITEMS, PROJECT_ROOT / "src" / "asof" / "reader_contract.py",
           *[PROJECT_ROOT / "scripts" / p for p in (
               "reader_real1_memory.py", "run_reader_positive_control.py", "run_reader_real2.py",
               "run_reader_real2_completion.py")],
           PROJECT_ROOT / "src" / "asof" / "reader_real2_guards.py"]


def controls() -> list[Control]:
    return [Control.model_validate(row) for row in json.loads(ITEMS.read_text())]


def native_scorer():
    root = DATA_DIR / "bench_1" / "tatqa"
    for name, digest in NATIVE.items():
        if ledger.file_sha256(root / name) != digest:
            raise ValueError("native scorer code changed; do not substitute")
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("contract_native_metric", root / "tatqa_metric.py")
    if spec is None or spec.loader is None:
        raise ImportError("pinned native scorer unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TaTQAEmAndF1


def native_score(case: Control, values: list[str], scale: str, scorer_type) -> dict:
    scorer = scorer_type()
    arithmetic = case.category == "arithmetic"
    scorer(ground_truth={
        "answer_type": "arithmetic" if arithmetic else
                       "multi-span" if len(case.expected) > 1 else "span",
        "answer": case.expected[0] if arithmetic else case.expected,
        "scale": case.expected_scale,
    }, prediction=values, pred_scale=scale)
    detail = scorer.get_raw()[-1]
    return {"native_EM": detail["em"], "native_F1": detail["f1"],
            "scale_correct": scale == case.expected_scale}


def freeze() -> None:
    if CONFIG.exists() or STATUS.exists():
        raise RuntimeError("invented contract already frozen/attempted; no overwrite")
    items = controls()
    if len({c.id for c in items}) != 24 or Counter(c.category for c in items) != {
        "multi_value": 6, "arithmetic": 8, "lookup": 4, "unit_trap": 3, "unanswerable": 3,
    }:
        raise ValueError("invented composition differs")
    scorer = native_scorer()
    for case in items:
        if case.expected and (
            native_score(case, case.expected, case.expected_scale, scorer)["native_EM"] != 1
        ):
            raise ValueError("invented expected answer fails native scorer self-check")
    order = [c.id for c in items]
    random.Random(2026111603).shuffle(order)
    config = {
        "kind": "INVENTED ONLY: contract positive control, not real-data accuracy",
        "items": [c.model_dump() for c in items], "order": order, "order_seed": 2026111603,
        "arms": ["typed_contract"], "comparison_arm": None,
        "model": MODEL, "API_digest": DIGEST, "Ollama_version": "0.40.16",
        "endpoint": ENDPOINT, "options": OPTIONS, "think": False,
        "system_prompt": SYSTEM, "schema": ContractAnswer.model_json_schema(),
        "normalization": "Unmodified pinned TAT-QA EM/F1: element-wise best span alignment, "
                         "order-independent lists with exact-match cardinality, native numeric/"
                         "text normalization. Separate exact scale, dimension and operation gates. "
                         "Code Decimal precision40, round-half-up to2decimal places, no rescaling.",
        "pass_rule": "All24attempted and completed; >=20/21answerable nativeEM1+scale+dimension+"
                     "operation correct with source-checked operands AND3/3explicitabstentions. "
                     "Failures/invalid/timeout/unattempted are misses. Separately count arithmetic "
                     "outputs computed by code and correct among the8arithmetic controls.",
        "limits": {"calls": 24, "wall_seconds": WALL, "per_call_seconds": 240,
                   "owned_tree_RSS_bytes": 10 << 30, "launch_mean3_below": 70,
                   "launch_wait_seconds": 600, "CPU_mean_window_seconds": 60,
                   "CPU_abort_mean_above": 95, "CPU_high_consecutive_seconds": 120,
                   "sleep_seconds_stop_above": 2},
        "stop_policy": "No retry. Single240s timeout is a miss;3consecutive stop. "
                       "SustainedCPU/memory/wall/sleep stop and record every remaining case. "
                       "Input byte/3 conservative fit and post-call prompt/output truncation checks.",
        "scope": "Invented authored controls only; no real questions/answers, no dataset read, "
                 "old-result rescore, model pull, training, financial/sealed data or trial-ledger row.",
        "native_code_sha256": NATIVE,
        "source_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
    }
    CONFIG.write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"frozen": 24, "config_sha256": ledger.file_sha256(CONFIG)}))


async def watch_resources(recorder, memory, started) -> None:
    while True:
        if await recorder.sample():
            raise ResourceStop("sustained_host_CPU")
        if memory.sample() > 10 << 30:
            raise ResourceStop("owned_RSS_above10GiB")
        if time.monotonic() - started >= WALL:
            raise ResourceStop("30minute_wall")


def log_truncated(offset: int) -> bool:
    with SERVER_LOG.open("rb") as stream:
        stream.seek(offset)
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("server log bound exceeded; cannot verify truncation")
    return bool(re.search(r"truncat\w*\s+input\s+prompt|input\s+prompt.{0,100}truncat",
                          raw.decode("utf-8", errors="replace"), re.IGNORECASE))


async def run(server_pid: int) -> None:
    if STATUS.exists():
        raise RuntimeError("already attempted; do not rerun or overwrite")
    config = json.loads(CONFIG.read_text())
    if ledger.lineage()["git_dirty"] or any(
        ledger.file_sha256(PROJECT_ROOT / p) != h for p, h in config["source_sha256"].items()
    ):
        raise ValueError("commit frozen contract and preserve its source before generation")
    if config["items"] != [c.model_dump() for c in controls()]:
        raise ValueError("invented controls changed")
    scorer_type = native_scorer()
    started, cpu_started = time.monotonic(), time.process_time()
    config_hash = ledger.file_sha256(CONFIG)
    items = {c.id: c for c in controls()}
    policy, memory, cpu = SustainedCPU(), OwnedMemory(server_pid), SleepAwareCPU()
    rows = [{"id": uid, "category": items[uid].category, "outcome": "not_attempted",
             "attempted": False, "correct": False, "computed_by_code": False}
            for uid in config["order"]]
    receipt = {"status": "incomplete", "config_sha256": config_hash,
               "lineage": ledger.lineage([CONFIG]), "items": rows,
               "host_CPU_trace": policy.trace, "host_sleep_interruptions": cpu.interruptions}
    PRIVATE.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        STATUS.write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")

    persist()
    watch, stop, complete, timeouts = None, "unexpected_interruption", False, 0
    with (PRIVATE / "host_CPU_trace.jsonl").open("x", encoding="utf-8") as trace:
        recorder = CPURecorder(started, cpu, policy, trace)
        try:
            receipt["launch_host_CPU_percent"] = await wait_for_launch(recorder, started)
            if memory.sample() > 10 << 30:
                raise ResourceStop("launch_RSS_above10GiB")
            watch = asyncio.create_task(watch_resources(recorder, memory, started))
            async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
                tags, version = await client.get("/api/tags"), await client.get("/api/version")
                tags.raise_for_status()
                version.raise_for_status()
                models = [m for m in tags.json()["models"] if m["name"] == MODEL]
                if len(models) != 1 or models[0]["digest"] != DIGEST or (
                    version.json()["version"] != config["Ollama_version"]
                ):
                    raise ResourceStop("model_or_server_pin_differs")
                for row in rows:
                    case = items[row["id"]]
                    body = request_body(case.report, MODEL, config["options"])
                    if body["messages"][0]["content"] != config["system_prompt"] or (
                        body["format"] != config["schema"]
                    ):
                        raise ValueError("frozen prompt/schema changed")
                    _, _, fits = input_fit(json.dumps(body).encode(), config["options"])
                    if not fits:
                        row.update(outcome="failed", reason="input_does_not_fit")
                        persist()
                        continue
                    cpu.check_suspend()
                    remaining = WALL - (time.monotonic() - started)
                    if remaining <= 0:
                        raise ResourceStop("30minute_wall")
                    offset = SERVER_LOG.stat().st_size
                    row.update(attempted=True, outcome="attempt_started")
                    persist()
                    call_started = time.monotonic()
                    try:
                        response = await guarded_request(client, body, watch, min(240, remaining))
                    except (TimeoutError, httpx.TimeoutException):
                        timeouts += 1
                        row.update(outcome="failed", reason="call_timeout")
                        if timeouts >= 3:
                            raise ResourceStop("three_consecutive_timeouts") from None
                        continue
                    except httpx.HTTPError as exc:
                        timeouts = 0
                        row.update(outcome="failed", reason=type(exc).__name__)
                        continue
                    finally:
                        row["call_wall_seconds"] = time.monotonic() - call_started
                        persist()
                    cpu.check_suspend()
                    timeouts = 0
                    try:
                        response.raise_for_status()
                        raw = response.json()
                        raw_path = PRIVATE / f"{case.id}.json"
                        raw_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
                        row["raw_response_sha256"] = ledger.file_sha256(raw_path)
                        row["ollama_metrics"] = {k: raw.get(k) for k in (
                            "eval_count", "prompt_eval_count", "total_duration", "load_duration")}
                        invalid = truncation_reason(raw, config["options"], log_truncated(offset))
                        if invalid or raw.get("done") is not True or raw.get("done_reason") != "stop":
                            raise ValueError(invalid or "incomplete_generation")
                        answer = ContractAnswer.model_validate_json(raw["message"]["content"])
                        values, computed = resolve(answer, case.report)
                        row.update(values=values, answer_scale=answer.answer_scale,
                                   answer_dimension=answer.answer_dimension,
                                   operation=answer.operation, computed_by_code=computed)
                        if case.expected:
                            row.update(native_score(case, values, answer.answer_scale, scorer_type))
                            correct = (row["native_EM"] == 1 and row["scale_correct"]
                                       and answer.answer_dimension == case.expected_dimension
                                       and answer.operation == case.expected_operation)
                            row.update(correct=correct, outcome="correct" if correct else "wrong")
                        else:
                            correct = answer.operation == "abstain"
                            row.update(correct=correct, outcome=(
                                "correct_abstention" if correct else "answered_unanswerable"))
                    except (httpx.HTTPError, ValidationError, ValueError, KeyError) as exc:
                        row.update(outcome="failed", reason=str(exc), failure_type=type(exc).__name__)
                    persist()
                complete, stop = True, None
        except (ResourceStop, httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
            stop = str(exc)
        finally:
            if watch is not None:
                watch.cancel()
                await asyncio.gather(watch, return_exceptions=True)
            for row in rows:
                if row["outcome"] in ("not_attempted", "attempt_started"):
                    row.update(outcome="failed" if row["attempted"] else "not_attempted",
                               reason=f"run_stopped:{stop}")
            a = sum(r["correct"] for r in rows if r["category"] != "unanswerable")
            u = sum(r["correct"] for r in rows if r["category"] == "unanswerable")
            attempted = sum(r["attempted"] for r in rows)
            unchanged = ledger.file_sha256(CONFIG) == config_hash and all(
                ledger.file_sha256(PROJECT_ROOT / p) == h
                for p, h in config["source_sha256"].items())
            receipt.update(status="complete" if complete and unchanged else "partial",
                stop_reason=stop, frozen_source_unchanged=unchanged,
                summary={"answerable_correct": a, "answerable_total": 21,
                         "correct_abstentions": u, "unanswerable_total": 3,
                         "attempted": attempted, "pass": complete and unchanged and passed(a, u, attempted),
                         "arithmetic_computed_by_code": sum(
                             r["computed_by_code"] for r in rows if r["category"] == "arithmetic"),
                         "arithmetic_correct": sum(
                             r["correct"] for r in rows if r["category"] == "arithmetic"),
                         "outcomes": dict(Counter(r["outcome"] for r in rows))},
                CPU_trace_summary=policy.summary(),
                resources={"wall_seconds": time.monotonic() - started,
                           "Python_CPU_seconds": time.process_time() - cpu_started,
                           "owned_RSS_peak_sample_bytes": memory.peak},
                meaning="Invented contract control only. No real-data accuracy or historical claim.")
            persist()
            print(json.dumps({"summary": receipt["summary"], "stop": stop,
                              "resources": receipt["resources"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    parser.add_argument("--server-pid", type=int)
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze()
    else:
        if args.server_pid is None:
            parser.error("--server-pid required")
        asyncio.run(run(args.server_pid))
