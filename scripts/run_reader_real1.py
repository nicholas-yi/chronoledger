"""Freeze and execute one thirty-question reader test, with no model retries or data tuning."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import time
from pathlib import Path

import httpx
from pydantic import ValidationError
from reader_real1_memory import OwnedMemory
from run_benchmark_diagnostic import ROOT, load_native, prediction_input, verified_assets
from run_reader_positive_control import (
    DIGEST,
    ENDPOINT,
    MODEL,
    LoadHistory,
    ResourceStop,
    WindowsCPU,
    guarded_request,
)

from asof import ledger
from asof.benchmark_baseline import TableInput
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid
from asof.reader_positive_control import SyntheticCase, control_body
from asof.reader_real_report import ARMS, report

COUNT, SEED, CALL_LIMIT, WALL_LIMIT = 30, 2026111412, 60, 4500
CONFIG = PROJECT_ROOT / "results" / "reader_real1_config.json"
RECEIPT = PROJECT_ROOT / "results" / "reader_real1_status.json"
PRIVATE = DATA_DIR / "reader_real1"
PC_CONFIG = PROJECT_ROOT / "results" / "reader_pc1_config.json"
PC_STATUS = PROJECT_ROOT / "results" / "reader_pc1_status.json"
SOURCES = [Path(__file__), PROJECT_ROOT / "scripts" / "reader_real1_memory.py",
           PROJECT_ROOT / "scripts" / "run_reader_positive_control.py",
           PROJECT_ROOT / "scripts" / "run_benchmark_diagnostic.py",
           *[PROJECT_ROOT / "src" / "asof" / f for f in (
               "reader_positive_control.py", "reader_diagnostic.py", "reader_real_report.py",
               "benchmark_baseline.py", "benchmark_reporting.py", "extraction.py")]]


class TimeoutSequence:
    def __init__(self) -> None:
        self.consecutive = 0

    def timeout(self) -> bool:
        self.consecutive += 1
        return self.consecutive >= 3

    def completed_call(self) -> None:
        self.consecutive = 0


def real_body(item: TableInput, arm: str, options: dict) -> dict:
    if arm not in ARMS:
        raise ValueError("unknown REAL1 arm")
    visible = item if arm == "report_supplied" else TableInput(item.question, (), ())
    return control_body(SyntheticCase("real", "real", visible, None), "answer_first",
                        model=MODEL, options=options)


def arm_orders(ids: list[str]) -> list[dict]:
    rng = random.Random(SEED + 1)
    result = []
    for uid in ids:
        arms = list(ARMS)
        rng.shuffle(arms)
        result.append({"id": uid, "arms": arms})
    return result


def freeze() -> None:
    if CONFIG.exists() or RECEIPT.exists():
        raise RuntimeError("REAL1 already frozen/attempted; no overwrite or resampling")
    pc, pc_status = json.loads(PC_CONFIG.read_text()), json.loads(PC_STATUS.read_text())
    if pc_status["verdict"] != "PASS" or any(
        ledger.file_sha256(PROJECT_ROOT / p) != digest for p, digest in pc["source_sha256"].items()
    ):
        raise ValueError("PC1 qualification/source changed")
    proposal_path = PROJECT_ROOT / "results" / "reader_next_real_proposal.json"
    proposal = json.loads(proposal_path.read_text())
    excluded = proposal["sample"]["excluded_question_ids"]
    original = json.loads((PROJECT_ROOT / "results" / "benchmark_diagnostic_config.json").read_text())
    paired = json.loads((PROJECT_ROOT / "results" / "tatqa_average_comparison_config.json").read_text())
    previous_reader = json.loads((PROJECT_ROOT / "results" / "reader_diagnostic_config_v2.json").read_text())
    actual_prior = set(original["tatqa_ids"]) | set(paired["ids"]) | set(previous_reader["ids"])
    if len(excluded) != len(set(excluded)) or len(excluded) != 70:
        raise ValueError("exactly seventy previous unique question IDs required")
    if set(excluded) != actual_prior:
        raise ValueError("proposal exclusions differ from the actual seventy prior questions")
    assets = verified_assets()
    native = load_native(ROOT / "tatqa" / "tatqa_metric.py", "tatqa_real1_preflight")
    native.TaTQAEmAndF1()
    contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
    all_ids = [q["uid"] for c in contexts for q in c["questions"]]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("duplicate development question identities")
    ids = random.Random(SEED).sample(sorted(set(all_ids) - set(excluded)), COUNT)
    options = dict(pc["options"], num_ctx=16384)
    template = real_body(TableInput("", (), ()), "report_supplied", options)
    config = {
        "kind": "CURRENT LOCAL READER, PUBLIC DEVELOPMENT SAMPLE; not historical usability/H1/returns",
        "seed": SEED, "ids": ids, "excluded_ids": excluded, "orders": arm_orders(ids),
        "selection": "Random(2026111412).sample(sorted(unique devUIDs minus prior70),30); "
                     "no answer/type/success filtering or resampling.",
        "arms": ARMS, "model": MODEL, "API_digest": DIGEST,
        "Ollama_version": pc["expected_Ollama_version"], "endpoint": ENDPOINT, "options": options,
        "PC1_runtime_change": "num_ctx8192->16384 explicitly declared; other options unchanged.",
        "system_prompt": template["messages"][0]["content"], "schema": template["format"],
        "parse": "Exact PC1 ReaderAnswer; lists allowed, no PC1 scalar normalizer on benchmark. "
                 "Numeric scalars converted to strings at native str/list input boundary so0 "
                 "is not mistaken for an empty prediction; abstention remains None.",
        "input": "Question/table/paragraph only. No-report keeps question but emptytable/paragraphs. "
                 "ALLgeneration ends before ANYgold/type/scoring field is accessed.",
        "limits": {"calls": CALL_LIMIT, "wall_seconds": WALL_LIMIT, "per_call_seconds": 240,
                   "serialized_request_bytes": 12000, "owned_process_tree_RSS_bytes": 6 << 30,
                   "launch_CPU_mean3samples_below_percent": 70, "abort_CPU_above_percent": 90,
                   "consecutive_1second_CPU_samples": 3},
        "timeout_policy": "A single call timeout fails only that case, never retried. "
                          "Reset timeout streak after any non-timeout call. "
                          "Three consecutive call timeouts stop all remaining cases. "
                          "Oversized non-calls do not reset a timeout streak.",
        "stops": "Hostload>90for3consecutive1ssamples,75minwall,ownedmemory>6GiB; "
                 "model/source integrity failures invalidate the run. No retry/replacement.",
        "metrics": "Native TATQA EM/F1/scale on all30perarm, errors/abstentions/unattempted=miss. "
                   "Coverage; Wilson95binaryEM/scale/coverage, no F1binomialCI. "
                   "All30paired2x2+exactdescriptiveMcNemar, and separately completed-valid-pair "
                   "contrast/denominators. Four answer-type groups, zero-denominator unavailable.",
        "native_assets": assets, "PC1_config_sha256": ledger.file_sha256(PC_CONFIG),
        "PC1_result_sha256": ledger.file_sha256(PC_STATUS),
        "proposal_sha256": ledger.file_sha256(proposal_path),
        "source_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
        "scope": "No new model/download/training/keys/paidcalls/marketoutcomes/sealeddata. "
                 "No-report correctness may be memorization or guessing. Public-benchmark "
                 "training contamination and repeated-report dependence are not ruled out.",
    }
    CONFIG.write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    print({"frozen_questions": COUNT, "max_calls": CALL_LIMIT,
           "config_sha256": ledger.file_sha256(CONFIG)})


async def watch_real1(started, cpu, loads, memory) -> None:
    while True:
        await asyncio.sleep(1)
        loads.add(cpu.percent())
        if memory.sample() > 6 << 30:
            raise ResourceStop("owned isolated process tree working set exceeds6GiB")
        if time.monotonic() - started >= WALL_LIMIT:
            raise ResourceStop("75minute total wall limit")


async def generate(config, rows, inputs, client, watch, started, predictions, persist) -> str | None:
    sequence = TimeoutSequence()
    total = 0
    for row, order in zip(rows, config["orders"], strict=True):
        if row["id"] != order["id"]:
            raise ValueError("frozen per-item order mismatch")
        for arm in order["arms"]:
            item = inputs[row["id"]]
            body = real_body(item, arm, config["options"])
            if body["messages"][0]["content"] != config["system_prompt"] or body["format"] != config["schema"]:
                raise ValueError("PC1 prompt/schema changed")
            encoded = json.dumps(body).encode()
            value = row[arm]
            value["request_sha256"] = hashlib.sha256(encoded).hexdigest()
            if len(encoded) > config["limits"]["serialized_request_bytes"]:
                value.update(outcome="failed", reason="oversized_input_not_truncated")
                continue
            if total >= CALL_LIMIT:
                raise ResourceStop("sixty-call ceiling")
            total += 1
            value.update(outcome="attempt_started", attempted=True)
            persist()
            call_start = time.monotonic()
            try:
                response = await guarded_request(
                    client, body, watch, min(240, WALL_LIMIT - (time.monotonic() - started)))
            except (TimeoutError, httpx.TimeoutException) as exc:
                value.update(outcome="failed", reason="call_timeout",
                             failure_type=type(exc).__name__, timeout=True)
                stop = sequence.timeout()
                value["consecutive_call_timeouts"] = sequence.consecutive
                persist()
                if stop:
                    return "three_consecutive_call_timeouts"
                continue
            except httpx.HTTPError as exc:
                sequence.completed_call()
                value.update(outcome="failed", reason="HTTP_transport_error",
                             failure_type=type(exc).__name__)
                persist()
                continue
            finally:
                value["call_wall_seconds"] = time.monotonic() - call_start
            sequence.completed_call()
            value["response_received"] = True
            try:
                response.raise_for_status()
                raw = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                value.update(outcome="failed", reason="HTTP_or_outer_JSON_error",
                             failure_type=type(exc).__name__)
                persist()
                continue
            (PRIVATE / f"{row['id']}_{arm}.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
            value["ollama_metrics"] = {k: raw.get(k) for k in (
                "total_duration", "load_duration", "prompt_eval_count", "eval_count",
            )}
            value["generation_finished"] = raw.get("done") is True and raw.get("done_reason") == "stop"
            if not value["generation_finished"]:
                value.update(outcome="failed", reason="incomplete_generation_or_token_limit")
                continue
            try:
                answer = ReaderAnswer.model_validate_json(raw["message"]["content"])
            except (ValidationError, KeyError) as exc:
                value.update(outcome="failed", reason="invalid_model_output",
                             failure_type=type(exc).__name__)
            else:
                value.update(outcome="abstain" if answer.abstain else "answered",
                    citation_locations_or_quotes_valid=references_locally_valid(
                        answer, item, supplied_context=arm == "report_supplied"))
                predictions[row["id"]][arm] = (answer.answer, answer.scale)
            persist()
    return None


def score_rows(rows, gold_by_id, predictions, metric_class) -> None:
    for row in rows:
        gold = gold_by_id[row["id"]]
        row["answer_type"] = gold["answer_type"]
        for arm in ARMS:
            answer, scale = predictions[row["id"]][arm]
            if isinstance(answer, (int, float)):
                answer = str(answer)
            metric = metric_class()
            metric(ground_truth=gold, prediction=answer, pred_scale=scale)
            em, f1, scale_accuracy, _ = metric.get_overall_metric()
            row[arm].update(native_EM=em, native_F1=f1, native_scale_accuracy=scale_accuracy)
            if row[arm]["outcome"] == "answered":
                row[arm]["outcome"] = "correct" if em == 1 else "wrong"


async def run(server_pid: int) -> None:
    if RECEIPT.exists():
        raise RuntimeError("REAL1 already attempted; no retry or result overwrite")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit source and prospective config before inference")
    config = json.loads(CONFIG.read_text())
    if config["native_assets"] != verified_assets() or any(
        ledger.file_sha256(PROJECT_ROOT / p) != digest for p, digest in config["source_sha256"].items()
    ):
        raise ValueError("frozen source/native assets changed")
    contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
    by_id = {q["uid"]: (context, q) for context in contexts for q in context["questions"]}
    ids = random.Random(SEED).sample(sorted(set(by_id)-set(config["excluded_ids"])), COUNT)
    if ids != config["ids"] or arm_orders(ids) != config["orders"]:
        raise ValueError("frozen selection/order does not reconcile")
    inputs = {uid: prediction_input(*by_id[uid]) for uid in ids}
    predictions = {uid: {a: (None, "") for a in ARMS} for uid in ids}
    native = load_native(ROOT / "tatqa" / "tatqa_metric.py", "tatqa_real1_native")
    start, cpu_start = time.monotonic(), time.process_time()
    config_hash = ledger.file_sha256(CONFIG)
    output = {"status": "incomplete", "config_sha256": config_hash,
              "lineage": ledger.lineage([CONFIG, *SOURCES]), "items": [
                  {"id": uid, **{a: {"outcome": "not_attempted", "attempted": False} for a in ARMS}}
                  for uid in ids]}
    PRIVATE.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        RECEIPT.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
        (PRIVATE / "predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")

    persist()
    watch = None
    cpu, loads, memory = WindowsCPU(), LoadHistory(), OwnedMemory(server_pid)
    stop = None
    phase_completed = False
    try:
        for _ in range(3):
            await asyncio.sleep(1)
            loads.add(cpu.percent())
        output["launch_host_CPU_percent"] = sum(loads.samples)/3
        if output["launch_host_CPU_percent"] >= 70:
            raise ResourceStop("launch CPU mean is not below70percent")
        memory.sample()
        watch = asyncio.create_task(watch_real1(start, cpu, loads, memory))
        async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
            tags, version = await client.get("/api/tags"), await client.get("/api/version")
            tags.raise_for_status()
            version.raise_for_status()
            matches = [m for m in tags.json()["models"] if m["name"] == MODEL]
            if len(matches) != 1 or matches[0]["digest"] != DIGEST or version.json()["version"] != config["Ollama_version"]:
                raise ResourceStop("existing model/server identity changed")
            stop = await generate(config, output["items"], inputs, client, watch, start, predictions, persist)
            phase_completed = stop is None
    except (httpx.HTTPError, TimeoutError, ResourceStop, ValueError, OSError, RuntimeError) as exc:
        stop = str(exc) if isinstance(exc, ResourceStop) else type(exc).__name__
        if isinstance(exc, (ResourceStop, RuntimeError)):
            output["stop_detail"] = str(exc)
    finally:
        if watch is not None:
            watch.cancel()
            await asyncio.gather(watch, return_exceptions=True)
        if not phase_completed and stop is None:
            stop = "unexpected_interruption"
        output["stop_reason"] = stop
        for row in output["items"]:
            for arm in ARMS:
                if row[arm]["outcome"] in ("not_attempted", "attempt_started"):
                    row[arm].update(outcome="not_attempted" if not row[arm]["attempted"] else "failed",
                                    reason=f"run_stopped:{stop or 'unexpected_interruption'}")
        # No model request is possible after this point. Only now read gold/type fields.
        score_rows(output["items"], {uid: by_id[uid][1] for uid in ids}, predictions,
                   native.TaTQAEmAndF1)
        output["report"] = report(output["items"])
        source_ok = ledger.file_sha256(CONFIG) == config_hash and all(
            ledger.file_sha256(PROJECT_ROOT / p) == digest for p, digest in config["source_sha256"].items())
        output.update(status="complete" if phase_completed and source_ok else "partial",
            frozen_source_and_config_unchanged=source_ok,
            generation_attempts=sum(r[a]["attempted"] for r in output["items"] for a in ARMS),
            resources={"wall_seconds": time.monotonic()-start,
                       "Python_CPU_seconds": time.process_time()-cpu_start,
                       "host_CPU_samples": len(loads.samples),
                       "host_CPU_mean_percent": sum(loads.samples)/len(loads.samples) if loads.samples else None,
                       "host_CPU_max_percent": max(loads.samples) if loads.samples else None,
                       "owned_tree_working_set_peak_sample_bytes": memory.peak,
                       "transient_exited_children": memory.exited_children,
                       "note": "One-second cooperative sampling, not an OS quota; CPU Python/host/model are distinct."})
        persist()
        print(json.dumps({"status": output["status"], "attempts": output["generation_attempts"],
                          "stop_reason": stop, "arms": output["report"]["arms"],
                          "paired": output["report"]["paired_all_selected"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    parser.add_argument("--server-pid", type=int)
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze()
    else:
        if args.server_pid is None:
            parser.error("--server-pid is required for owned-memory monitoring")
        asyncio.run(run(args.server_pid))
