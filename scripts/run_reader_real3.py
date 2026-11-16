"""Archived experimental format comparison, not the default answer-first reader."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import socket
import subprocess
import time
from pathlib import Path

import httpx
from pydantic import ValidationError
from reader_real1_memory import OwnedMemory
from run_benchmark_diagnostic import ROOT as BENCH_ROOT
from run_benchmark_diagnostic import load_native
from run_reader_positive_control import DIGEST, ENDPOINT, MODEL, ResourceStop, guarded_request
from run_reader_real1 import real_body
from run_reader_real2 import CPURecorder, wait_for_launch
from run_reader_real2_completion import SleepAwareCPU

from asof import ledger
from asof.benchmark_baseline import TableInput
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.local_model_runtime import RuntimePolicy, verify_runtime_receipt
from asof.reader_columns import ModeChoice, resolve_content
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid
from asof.reader_real2_guards import SustainedCPU, input_fit, truncation_reason
from asof.reader_real3_data import ARMS, blind_inputs, report
from asof.reader_tatqa_mapping import (
    MappingError,
    map_input,
    mapped_answer_body,
    mapped_mode_body,
)

ROOT = PROJECT_ROOT
PRIVATE = DATA_DIR / "reader_real3"
SERVER_LOG = PRIVATE / "isolated-server.log"
BASE = ROOT / "results" / "reader_real2_config.json"
PRACTICE = ROOT / "tests" / "fixtures" / "reader_real3_practice.json"
DATASET = BENCH_ROOT / "tatqa" / "dev.json"
PROTECTED = [ROOT / "src" / "asof" / p for p in (
    "reader_columns.py", "reader_roles.py", "reader_presence.py", "reader_modes.py",
    "reader_contract.py", "reader_diagnostic.py", "reader_positive_control.py")]
SOURCES = [Path(__file__), ROOT / "src" / "asof" / "reader_tatqa_mapping.py",
           ROOT / "src" / "asof" / "reader_real3_data.py",
           ROOT / "src" / "asof" / "reader_real_report.py",
           ROOT / "src" / "asof" / "benchmark_reporting.py", *PROTECTED,
           ROOT / "src" / "asof" / "local_model_runtime.py",
           *[ROOT / "scripts" / p for p in (
               "reader_real1_memory.py", "run_reader_real2.py", "run_reader_real2_completion.py",
               "run_reader_positive_control.py", "run_reader_real1.py")]]


def paths(practice: bool, iteration: int):
    name = f"practice_{iteration}" if practice else "scored"
    stem = f"reader_real3_practice_{iteration}" if practice else "reader_real3"
    return (ROOT / "results" / f"{stem}_config.json",
            ROOT / "results" / f"{stem}_status.json", PRIVATE / name)


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def practice_history():
    return [json.loads(p.read_text()) for p in sorted(
        (ROOT / "results").glob("reader_real3_practice_*_status.json"))]


def practice_inputs() -> dict[str, TableInput]:
    return {r["id"]: TableInput(r["question"], tuple(tuple(c) for c in r["table"]),
                               tuple(r["paragraphs"])) for r in json.loads(PRACTICE.read_text())}


def native_pins() -> dict:
    expected = json.loads(BASE.read_text())["native_assets"]
    result = {}
    for relative in (r"tatqa\dev.json", r"tatqa\tatqa_metric.py",
                     r"tatqa\tatqa_utils.py", r"tatqa\tatqa_eval.py"):
        value = expected[relative]
        if ledger.file_sha256(BENCH_ROOT / relative) != value["sha256"]:
            raise ValueError("native_dataset_or_scorer_pin_changed")
        result[relative] = value
    return result


def baseline_body(item: TableInput, options: dict, base: dict) -> dict:
    body = real_body(item, "report_supplied", options)
    if body["messages"][0]["content"] != base["system_prompt"] or body["format"] != base["schema"]:
        raise ValueError("REAL2_exact_prompt_or_schema_changed")
    return body


def freeze(practice: bool, iteration: int, change: str) -> None:
    cp, sp, _ = paths(practice, iteration)
    if cp.exists() or sp.exists():
        raise RuntimeError("phase_already_frozen_or_attempted")
    subprocess.run(["git", "diff", "--exit-code", "4e53f49", "--",
                    *[str(p.relative_to(ROOT)) for p in PROTECTED]],
                   cwd=ROOT, check=True, capture_output=True)
    base = json.loads(BASE.read_text())
    options = dict(base["options"], num_ctx=16384, num_predict=768)
    previous = practice_history()
    if practice:
        if not 1 <= iteration <= 2 or len(previous) != iteration - 1:
            raise ValueError("two_practice_iterations_max")
        inputs = practice_inputs()
        if len(inputs) > 12 or sum(r["generation_calls"] for r in previous) + 3 * len(inputs) > 40:
            raise ValueError("practice_item_or_call_cap")
        ids = list(inputs)
        excluded, pins = [], None
    else:
        if not previous or previous[-1]["status"] != "complete":
            raise ValueError("completed_operational_practice_required")
        pins = native_pins()
        excluded = sorted(set(base["excluded_ids"]) | set(base["ids"]))
        if len(excluded) != 130:
            raise ValueError("exact130prior_real_exclusions_required")
        inputs = blind_inputs(DATASET)
        ids = random.Random(2026111701).sample(sorted(set(inputs) - set(excluded)), 30)
    rng = random.Random(2026111702)
    orders = []
    requests, mappings = {}, {}
    for uid in ids:
        arms = list(ARMS)
        rng.shuffle(arms)
        orders.append({"id": uid, "arms": arms})
        requests[uid] = {"B": fingerprint(baseline_body(inputs[uid], options, base))}
        try:
            mapped = map_input(inputs[uid])
        except MappingError as exc:
            mappings[uid] = {"failure": str(exc)}
        else:
            mappings[uid] = mapped.summary
            requests[uid].update(
                A_mode=fingerprint(mapped_mode_body(mapped, MODEL, options)),
                **{f"A_{m}": fingerprint(mapped_answer_body(mapped, m, MODEL, options))
                   for m in ("lookup", "multi_value", "arithmetic", "text_span", "abstain")})
    value = {
        "kind": "PRACTICE NEVER ACCURACY" if practice else "REAL3 PAIRED PUBLIC FORMAT COMPARISON",
        "user_decision": "run despite invented-control miss (18/21 + 2/3)",
        "iteration": iteration if practice else None, "practice_change": change,
        "ids": ids, "excluded_ids": excluded, "orders": orders,
        "seed": 2026111701, "order_seed": 2026111702,
        "selection": "Random(2026111701).sample(sorted(devUIDs minus all130exposed),30),"
                     "no type/answer/success filtering or resampling.",
        "arms": {"column_format": "A=current unchanged column-label/named-role/text-span logic",
                 "answer_first": "B=exactREAL2answer-first system/schema/ReaderAnswerparse"},
        "model": MODEL, "digest": DIGEST, "server": "0.40.16", "options": options,
        "server_runtime": RuntimePolicy().manifest(),
        "reader_status": "column_format_stopped_experimental;answer_first_is_default",
        "runtime_change": "Botharms use num_predict768 rather than historicalREAL2's512, "
                          "num_ctx16384;otherwiseREAL2options. A<=2calls,B1: not matched compute.",
        "baseline_system": base["system_prompt"], "baseline_schema": base["schema"],
        "baseline_config_SHA256": ledger.file_sha256(BASE),
        "request_SHA256": requests, "mapping_metadata": mappings,
        "mapping_contract": "Complete rawtable+unchanged paragraphs plus source-only typed-cell "
            "serialization. Stable row-index/unit and column-index/first-header locators; "
            "canonical accounting decimals; explicit source in-units banner; unmarked numerics "
            "declared unscaledUSD assumption;count scaling prototype limitation recorded. "
            "Conflicting banners fail A explicitly, no input cuts/replacement. A outputs string "
            "lists+code-derived native scale unchanged;B numeric scalar->string preserveszero.",
        "native_assets": pins, "protected_logic_SHA256": {
            str(p.relative_to(ROOT)): ledger.file_sha256(p) for p in PROTECTED},
        "source_SHA256": {str(p.relative_to(ROOT)): ledger.file_sha256(p) for p in SOURCES},
        "practice_fixture_SHA256": ledger.file_sha256(PRACTICE) if practice else None,
        "practice_status_SHA256": [ledger.file_sha256(paths(True, r["iteration"])[1]) for r in previous],
        "SEC_receipt_SHA256": ledger.file_sha256(DATA_DIR / "p0_SEC_request_receipt.json"),
        "limits": {"wall_seconds": 1200 if practice else 7200, "per_call_seconds": 240,
                   "max_calls": 3 * len(ids), "practice_all_iterations_calls": 40,
                   "threads": 4, "owned_RSS_bytes": 10 << 30,
                   "CPU": "REAL2duration rule:60smean>95%for120consecutive seconds",
                   "sleep": "record-and-stop;no automatic continuation",
                   "timeouts": "singlemiss continues,no retry;3consecutive stop"},
        "blindness": "Blind decoder whitelists UID/question and table/paragraph source; "
                    "inference has no annotation objects. No gold/type/support fields consulted. "
                    "Allgeneration closes and own server stops BEFORE separate score command.",
        "metrics": "NativeEM/F1/scale andcoverage,all30eacharm;failures/abstentions/unattempted=miss. "
                   "Wilson95EM/scale/coverage,notF1. All30pairedAonly/Bonly/both/neither and "
                   "exactdescriptiveMcNemar;separatevalidpairs;span/multi-span/arithmetic/count "
                   "breakdown(emptygroupsunavailable);model/systemdeclines;codearithmetic;everyUID.",
        "scope": "Smallpublicsample,possibletrainingexposure;not historicalusability,H1orreturns. "
                 "No realQ/answertextGit,ledgerrow,SEC,prices,returns,sealeddata,pull/training,"
                 "keys/paidcalls,pushortags.",
    }
    cp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"frozen": len(ids), "practice": practice, "config_SHA256": ledger.file_sha256(cp)}))


def verify(cfg: dict) -> None:
    for path, digest in cfg["source_SHA256"].items():
        if ledger.file_sha256(ROOT / path) != digest:
            raise ValueError("frozen_source_changed")
    if ledger.file_sha256(BASE) != cfg["baseline_config_SHA256"]:
        raise ValueError("baseline_pin_changed")


async def generate(practice: bool, iteration: int, pid: int,
                   runtime_receipt: Path | None = None) -> None:
    cp, sp, private = paths(practice, iteration)
    if sp.exists():
        raise RuntimeError("already_attempted_no_retry")
    cfg = json.loads(cp.read_text())
    verify(cfg)
    if "server_runtime" not in cfg:
        raise RuntimeError("archived_runtime_contract_requires_separate_new_run_decision")
    verify_runtime_receipt(runtime_receipt or DATA_DIR/"local_reader_server"/"runtime.json",
                           pid, cfg["server_runtime"])
    if ledger.lineage()["git_dirty"]:
        raise ValueError("commit_frozen_source_and_config_first")
    if practice:
        if ledger.file_sha256(PRACTICE) != cfg["practice_fixture_SHA256"]:
            raise ValueError("practice_source_changed")
        inputs = practice_inputs()
    else:
        if native_pins() != cfg["native_assets"]:
            raise ValueError("native_pins_changed")
        inputs = blind_inputs(DATASET)
    base = json.loads(BASE.read_text())
    private.mkdir(parents=True, exist_ok=True)
    predictions = {uid: {a: [None, ""] for a in ARMS} for uid in cfg["ids"]}
    rows = [{"id": uid, **{a: {"outcome": "not_attempted", "attempted": False, "calls": []}
                           for a in ARMS}} for uid in cfg["ids"]]
    output = {"kind": cfg["kind"], "iteration": cfg["iteration"], "items": rows,
              "config_SHA256": ledger.file_sha256(cp), "lineage": ledger.lineage(),
              "generation_closed": False}
    pred_path = private / "predictions.json"
    start, cpu_start = time.monotonic(), time.process_time()
    if practice:
        deadline_path = PRIVATE / "practice_deadline.json"
        if not deadline_path.exists():
            deadline_path.write_text(json.dumps({"deadline": start + 1200}), encoding="utf-8")
        deadline = json.loads(deadline_path.read_text())["deadline"]
    else:
        deadline = start + 7200
    memory_context = {"phase":"practice" if practice else "real_generation",
                      "options_SHA256":fingerprint(cfg["options"])}
    cpu = SleepAwareCPU()
    memory = OwnedMemory(pid,telemetry_path=private/"process_memory.jsonl",context=memory_context)
    policy = SustainedCPU()
    output.update(CPU_trace=policy.trace, sleep_interruptions=cpu.interruptions)

    def persist():
        pred_path.write_text(json.dumps(predictions, indent=2), encoding="utf-8")
        sp.write_text(json.dumps(output, indent=2), encoding="utf-8")

    async def monitor(recorder):
        while True:
            if await recorder.sample():
                raise ResourceStop("sustained_CPU")
            if memory.sample() > 10 << 30:
                raise ResourceStop("owned_RSS10GiB")
            if time.monotonic() >= deadline:
                raise ResourceStop("whole_run_wall")

    consecutive = 0

    async def ask(client, body, value, uid, arm, stage, watch):
        nonlocal consecutive
        if fingerprint(body) != cfg["request_SHA256"][uid][stage]:
            raise ResourceStop("request_differs_from_freeze")
        estimate, bound, fits = input_fit(json.dumps(body).encode(), body["options"])
        if not fits:
            value.update(estimated_input_tokens=estimate, input_bound=bound)
            raise ValueError("input_does_not_fit")
        n = sum(len(r[a]["calls"]) for r in rows for a in ARMS)
        prior = sum(r["generation_calls"] for r in practice_history()
                    if r["iteration"] < iteration) if practice else 0
        if n >= cfg["limits"]["max_calls"] or (practice and prior + n >= 40):
            raise ResourceStop("generation_call_cap")
        cpu.check_suspend()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResourceStop("whole_run_wall")
        call = {"stage": stage, "outcome": "started"}
        memory_context.update(uid=uid,arm=arm,stage=stage,call_id=n+1)
        value["calls"].append(call)
        value.update(attempted=True, outcome="attempt_started")
        offset, t = SERVER_LOG.stat().st_size, time.monotonic()
        persist()
        try:
            response = await guarded_request(client, body, watch, min(240, remaining))
            consecutive = 0
            cpu.check_suspend()
            response.raise_for_status()
            value["response_received"] = True
            raw = response.json()
            path = private / f"{uid}_{arm}_{stage}.json"
            path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            call["raw_SHA256"] = ledger.file_sha256(path)
            call["metrics"] = {k: raw.get(k) for k in (
                "eval_count", "prompt_eval_count", "total_duration", "load_duration")}
            with SERVER_LOG.open("rb") as stream:
                stream.seek(offset)
                log = stream.read(262145)
            if len(log) > 262144:
                raise ValueError("truncation_log_unavailable")
            sign = bool(re.search(r"truncat\w*\s+input\s+prompt|input\s+prompt.{0,100}truncat",
                                 log.decode("utf-8", errors="replace"), re.IGNORECASE))
            invalid = truncation_reason(raw, body["options"], sign)
            if invalid or raw.get("done") is not True or raw.get("done_reason") != "stop":
                raise ValueError(invalid or "incomplete_generation")
            call["outcome"] = "complete"
            return raw["message"]["content"]
        except (TimeoutError, httpx.TimeoutException) as exc:
            consecutive += 1
            value["timeout"] = True
            call.update(outcome="failed", reason="call_timeout")
            if consecutive >= 3:
                raise ResourceStop("three_consecutive_timeouts") from exc
            raise ValueError("call_timeout") from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            consecutive = 0
            call.update(outcome="failed", failure_type=type(exc).__name__)
            raise
        finally:
            call["wall_seconds"] = time.monotonic() - t
            persist()

    watch, complete, stop = None, False, "unexpected_interruption"
    persist()
    with (private / "CPU_trace.jsonl").open("x", encoding="utf-8") as trace:
        try:
            recorder = CPURecorder(start, cpu, policy, trace)
            output["launch_CPU_mean"] = await wait_for_launch(recorder, start)
            watch = asyncio.create_task(monitor(recorder))
            async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
                tags, version = await client.get("/api/tags"), await client.get("/api/version")
                tags.raise_for_status()
                version.raise_for_status()
                models = [m for m in tags.json()["models"] if m["name"] == MODEL]
                if len(models) != 1 or models[0]["digest"] != DIGEST or version.json()["version"] != cfg["server"]:
                    raise ResourceStop("model_or_server_pin")
                for row, order in zip(rows, cfg["orders"], strict=True):
                    uid, item = row["id"], inputs[row["id"]]
                    for arm in order["arms"]:
                        value = row[arm]
                        try:
                            if arm == ARMS[0]:
                                mapped = map_input(item)
                                content = await ask(client, mapped_mode_body(mapped, MODEL, cfg["options"]),
                                                    value, uid, arm, "A_mode", watch)
                                mode = ModeChoice.model_validate_json(content).mode
                                if mode != "abstain":
                                    content = await ask(client, mapped_answer_body(
                                        mapped, mode, MODEL, cfg["options"]), value, uid, arm,
                                        f"A_{mode}", watch)
                                parsed_mode, result = resolve_content(content, mapped.report)
                                if parsed_mode != mode:
                                    raise ValueError("selected_mode_changed")
                                answer, scale = result.values, result.scale
                                abstain = result.abstention_source is not None
                                value.update(mode=mode, abstention_source=result.abstention_source,
                                    decline_reason=result.decline_reason, computed_by_code=result.computed_by_code)
                            else:
                                content = await ask(client, baseline_body(item, cfg["options"], base),
                                                    value, uid, arm, "B", watch)
                                parsed = ReaderAnswer.model_validate_json(content)
                                answer, scale, abstain = parsed.answer, parsed.scale, parsed.abstain
                                if isinstance(answer, (int, float)):
                                    answer = str(answer)
                                value.update(abstention_source="model" if abstain else None,
                                    citation_locations_or_quotes_valid=references_locally_valid(
                                        parsed, item, supplied_context=True))
                            predictions[uid][arm] = [None if abstain else answer, scale]
                            value.update(outcome="abstain" if abstain else "answered",
                                         generation_finished=True)
                        except MappingError as exc:
                            value.update(outcome="failed", reason="mapping_failure", mapping_code=str(exc))
                        except (httpx.HTTPError, ValidationError, ValueError, KeyError) as exc:
                            # Do not publish exception strings: validation errors contain model text.
                            value.update(outcome="failed", reason="request_or_output_failure",
                                         failure_type=type(exc).__name__)
                        persist()
            complete, stop = True, None
        except (ResourceStop, httpx.HTTPError, ValueError, OSError, RuntimeError) as exc:
            stop = str(exc) if isinstance(exc, ResourceStop) else type(exc).__name__
        finally:
            if watch:
                watch.cancel()
                await asyncio.gather(watch, return_exceptions=True)
            for row in rows:
                for arm in ARMS:
                    value = row[arm]
                    if value["outcome"] in ("not_attempted", "attempt_started"):
                        value.update(outcome="failed" if value["attempted"] else "not_attempted",
                                     reason=f"run_stopped:{stop}")
                    for call in value["calls"]:
                        if call["outcome"] == "started":
                            call.update(outcome="failed", reason=f"run_stopped:{stop}")
            try:
                verify(cfg)
                source_ok = ledger.file_sha256(cp) == output["config_SHA256"]
            except ValueError:
                source_ok = False
            output.update(status="complete" if complete and source_ok else "partial",
                generation_closed=True, stop_reason=stop, frozen_source_and_config_unchanged=source_ok,
                generation_calls=sum(len(r[a]["calls"]) for r in rows for a in ARMS),
                CPU_summary=policy.summary(),
                resources={"wall_seconds": time.monotonic() - start,
                           "Python_CPU_seconds": time.process_time() - cpu_start,
                           "owned_RSS_peak_sample_bytes": memory.peak})
            if practice:
                output["operational_mapping_check"] = complete and source_ok and all(
                    r[a]["outcome"] in ("answered", "abstain") for r in rows for a in ARMS)
                output["warning"] = "PRACTICE: no gold/native scoring/accuracy."
            persist()
            output["sealed_predictions_SHA256"] = ledger.file_sha256(pred_path)
            persist()
            print(json.dumps({k: output.get(k) for k in (
                "status", "generation_calls", "operational_mapping_check", "stop_reason", "resources")}))


def score() -> None:
    cp, sp, private = paths(False, 1)
    target = ROOT / "results" / "reader_real3_report.json"
    if target.exists():
        raise RuntimeError("already_scored_no_overwrite")
    cfg, receipt = json.loads(cp.read_text()), json.loads(sp.read_text())
    if not receipt["generation_closed"] or not receipt["frozen_source_and_config_unchanged"]:
        raise RuntimeError("generation_not_closed_or_integrity_failed")
    try:
        with socket.create_connection(("127.0.0.1", 11435), timeout=1):
            raise RuntimeError("stop_owned_server_before_gold_phase")
    except ConnectionRefusedError:
        pass
    verify(cfg)
    if native_pins() != cfg["native_assets"]:
        raise ValueError("native_pins_changed_before_gold_phase")
    pred_path = private / "predictions.json"
    if ledger.file_sha256(pred_path) != receipt["sealed_predictions_SHA256"]:
        raise ValueError("sealed_predictions_changed")
    predictions = json.loads(pred_path.read_text())
    # First application access to gold/type fields occurs only in this separate closed phase.
    contexts = json.loads(DATASET.read_bytes())
    gold = {q["uid"]: q for c in contexts for q in c["questions"]}
    native = load_native(BENCH_ROOT / "tatqa" / "tatqa_metric.py", "real3_native_scoring")
    rows = json.loads(json.dumps(receipt["items"]))
    for row in rows:
        uid, annotation = row["id"], gold[row["id"]]
        row["answer_type"] = annotation["answer_type"]
        for arm in ARMS:
            value = row[arm]
            value.update(native_EM=0, native_F1=0, native_scale_accuracy=0)
            if value["outcome"] == "answered":
                answer, scale = predictions[uid][arm]
                scorer = native.TaTQAEmAndF1()
                scorer(ground_truth=annotation, prediction=answer, pred_scale=scale)
                detail = scorer.get_raw()[-1]
                value.update(native_EM=detail["em"], native_F1=detail["f1"],
                             native_scale_accuracy=int(scale == annotation["scale"]),
                             outcome="correct" if detail["em"] == 1 else "wrong")
    output = {"status": receipt["status"], "items": rows, "report": report(rows),
              "generation_receipt_SHA256": ledger.file_sha256(sp),
              "sealed_predictions_SHA256": receipt["sealed_predictions_SHA256"],
              "config_SHA256": ledger.file_sha256(cp),
              "resources": receipt["resources"], "CPU_summary": receipt["CPU_summary"]}
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["report"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("practice-freeze", "practice", "freeze", "run", "score"))
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--change", default="Initial source-only TAT-shaped operational mapping.")
    parser.add_argument("--server-pid", type=int)
    parser.add_argument("--runtime-receipt", type=Path)
    args = parser.parse_args()
    if args.phase in ("practice-freeze", "freeze"):
        freeze(args.phase == "practice-freeze", args.iteration, args.change)
    elif args.phase == "score":
        score()
    else:
        if args.server_pid is None:
            parser.error("--server-pid required")
        asyncio.run(generate(args.phase == "practice", args.iteration, args.server_pid,
                             args.runtime_receipt))
