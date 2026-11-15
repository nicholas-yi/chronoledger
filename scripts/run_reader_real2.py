"""Fresh REAL2 reader run: corrected operational guards, unchanged content and scoring."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError
from reader_real1_memory import OwnedMemory
from run_benchmark_diagnostic import ROOT, load_native, prediction_input, verified_assets
from run_reader_positive_control import (
    DIGEST,
    ENDPOINT,
    MODEL,
    ResourceStop,
    WindowsCPU,
    guarded_request,
)
from run_reader_real1 import TimeoutSequence, real_body, score_rows

from asof import ledger
from asof.benchmark_baseline import TableInput
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid
from asof.reader_real2_guards import SustainedCPU, input_fit, truncation_reason
from asof.reader_real_report import ARMS, report

COUNT, SEED, ORDER_SEED, CALL_LIMIT, WALL_LIMIT = 30, 2026111415, 2026111416, 60, 4500
CONFIG = PROJECT_ROOT / "results" / "reader_real2_config.json"
RECEIPT = PROJECT_ROOT / "results" / "reader_real2_status.json"
PRIVATE = DATA_DIR / "reader_real2"
SERVER_LOG = PRIVATE / "isolated-server.log"
REAL1_CONFIG = PROJECT_ROOT / "results" / "reader_real1_config.json"
REAL1_STATUS = PROJECT_ROOT / "results" / "reader_real1_status.json"
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "reader_real2_guards.py",
           *[PROJECT_ROOT / "scripts" / f for f in (
               "run_reader_real1.py", "reader_real1_memory.py", "run_reader_positive_control.py",
               "run_benchmark_diagnostic.py")],
           *[PROJECT_ROOT / "src" / "asof" / f for f in (
               "reader_positive_control.py", "reader_diagnostic.py", "reader_real_report.py",
               "benchmark_baseline.py", "benchmark_reporting.py", "extraction.py")]]


def arm_orders(ids: list[str]) -> list[dict]:
    rng = random.Random(ORDER_SEED)
    result = []
    for uid in ids:
        arms = list(ARMS)
        rng.shuffle(arms)
        result.append({"id": uid, "arms": arms})
    return result


def freeze() -> None:
    if CONFIG.exists() or RECEIPT.exists():
        raise RuntimeError("REAL2 already frozen/attempted; no overwrite or resampling")
    base = json.loads(REAL1_CONFIG.read_text())
    previous = json.loads(REAL1_STATUS.read_text())
    if any(ledger.file_sha256(PROJECT_ROOT/p) != digest
           for p, digest in base["source_sha256"].items()):
        raise ValueError("verified REAL1/PC1 content or parser source changed")
    excluded = sorted(set(base["excluded_ids"]) | set(base["ids"]))
    if len(excluded) != 100 or [r["id"] for r in previous["items"]] != base["ids"]:
        raise ValueError("REAL1 records and exactly100 previous IDs must reconcile")
    if base["options"] != {
        "temperature": 0, "seed": 2026111411, "num_predict": 512, "num_ctx": 16384,
        "num_thread": 4, "num_gpu": 0, "num_batch": 128,
    }:
        raise ValueError("unchanged runtime options differ from Lead's contract")
    assets = verified_assets()
    if assets != base["native_assets"]:
        raise ValueError("native dataset/scorer pins changed")
    contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
    all_ids = [q["uid"] for c in contexts for q in c["questions"]]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("duplicate development question identities")
    ids = random.Random(SEED).sample(sorted(set(all_ids)-set(excluded)), COUNT)
    template = real_body(TableInput("", (), ()), "report_supplied", base["options"])
    if template["messages"][0]["content"] != base["system_prompt"] or template["format"] != base["schema"]:
        raise ValueError("PC1 prompt/schema changed")
    config = dict(base)
    config.update(
        kind="FRESH REAL2 PUBLIC DEVELOPMENT READER TEST; NOT A REAL1 RESUME",
        seed=SEED, order_seed=ORDER_SEED, ids=ids, excluded_ids=excluded, orders=arm_orders(ids),
        selection="Random(2026111415).sample(sorted(devUIDs minus all100previous),30); "
                  "no filtering/tuning/resampling; arm-order RNG2026111416.",
        REAL1_config_sha256=ledger.file_sha256(REAL1_CONFIG),
        REAL1_result_sha256=ledger.file_sha256(REAL1_STATUS),
        operational_changes="Content-independent, before generation: sustained CPU rule, "
                            "launch wait, estimated-token fit and post-call truncation invalidation. "
                            "Model/options/prompt/schema/parse/native metrics unchanged.",
        source_sha256={str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
        limits={"calls": CALL_LIMIT, "wall_seconds": WALL_LIMIT, "per_call_seconds": 240,
                "owned_process_tree_RSS_bytes": 6 << 30, "launch_wait_seconds": 600,
                "launch_3sample_mean_below_percent": 70,
                "CPU_rolling_mean_seconds": 60, "CPU_abort_mean_above_percent": 95,
                "CPU_consecutive_high_mean_seconds": 120, "sample_interval_seconds": 1,
                "input_estimate": "ceil(full serialized UTF8 request bytes/3)",
                "input_margin_tokens": 256,
                "post_prompt_eval_count_below": 16384-512},
        CPU_definition="Time-weighted60second rolling mean of measured interval-average hostload; "
                       "require a full60second window. Consecutive elapsed duration resets at<=95. "
                       "Arm sustained-stop timer only after launch qualification. "
                       "Record every nominal1second interval with actual endpoints/UTC timestamp; "
                       "launchwait is included in75minwall.",
        truncation_policy="Reject only estimate>ctx-output-256 before sending. Aftereachresponse, "
                          "prompt_eval_count must be integer>=0 and <ctx-output. Provider truncation "
                          "flags, ownserver input-prompt truncation warnings, or output-length/token "
                          "limit invalidate the case; no silent cut, scoring or retry of its answer.",
        stops="60sCPUrollingmean>95for120consecutiveseconds,75minwall,ownedRSS>6GiB, "
              "3consecutive calltimeouts. Integrityfailure invalidates. No retries or REAL1 resume.",
    )
    CONFIG.write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    print({"frozen_questions": 30, "excluded": 100, "config_sha256": ledger.file_sha256(CONFIG)})


class CPURecorder:
    def __init__(self, started: float, cpu, policy: SustainedCPU, trace_file) -> None:
        self.started, self.cpu, self.policy, self.file = started, cpu, policy, trace_file
        self.last = time.monotonic()-started

    async def sample(self) -> bool:
        await asyncio.sleep(1)
        percent = self.cpu.percent()
        end = time.monotonic()-self.started
        stop = self.policy.add(self.last, end, percent, datetime.now(UTC).isoformat())
        self.last = end
        self.file.write(json.dumps(self.policy.trace[-1])+"\n")
        self.file.flush()
        return stop


async def wait_for_launch(recorder: CPURecorder, started: float) -> float:
    wait_start = time.monotonic()
    while True:
        await recorder.sample()
        if time.monotonic()-wait_start > 600:
            raise ResourceStop("launch CPU remained too high for10minutes; no generation")
        if time.monotonic()-started >= WALL_LIMIT:
            raise ResourceStop("75minute total wall limit")
        if len(recorder.policy.trace) >= 3:
            mean = sum(r["host_CPU_percent"] for r in recorder.policy.trace[-3:])/3
            if mean < 70:
                recorder.policy.activate()
                return mean


async def watch_real2(recorder, memory, started) -> None:
    while True:
        if await recorder.sample():
            raise ResourceStop("60second hostCPU mean above95percent for120consecutive seconds")
        if memory.sample() > 6 << 30:
            raise ResourceStop("owned isolated process tree working set exceeds6GiB")
        if time.monotonic()-started >= WALL_LIMIT:
            raise ResourceStop("75minute total wall limit")


def new_log_truncation(offset: int) -> bool:
    with SERVER_LOG.open("rb") as stream:
        stream.seek(offset)
        new = stream.read(262145)
    if len(new) > 262144:
        raise ValueError("server log verification bound exceeded")
    text = new.decode("utf-8", errors="replace")
    return bool(re.search(r"truncat\w*\s+input\s+prompt|input\s+prompt.{0,100}truncat",
                          text, re.IGNORECASE))


async def generate(config, rows, inputs, client, watch, started, predictions, persist) -> str | None:
    sequence, total = TimeoutSequence(), 0
    for row, order in zip(rows, config["orders"], strict=True):
        if row["id"] != order["id"]:
            raise ValueError("frozen order mismatch")
        for arm in order["arms"]:
            item, value = inputs[row["id"]], row[arm]
            body = real_body(item, arm, config["options"])
            if body["messages"][0]["content"] != config["system_prompt"] or body["format"] != config["schema"]:
                raise ValueError("exact PC1 prompt/schema changed")
            encoded = json.dumps(body).encode()
            estimate, bound, fits = input_fit(encoded, config["options"])
            value.update(request_sha256=hashlib.sha256(encoded).hexdigest(),
                         serialized_request_bytes=len(encoded), estimated_tokens=estimate,
                         estimated_token_fit_bound=bound)
            if not fits:
                value.update(outcome="failed", reason="estimated_input_does_not_fit",
                             input_fit_rejected=True)
                persist()
                continue
            remaining = WALL_LIMIT-(time.monotonic()-started)
            if remaining <= 0:
                return "75minute total wall limit"
            if total >= CALL_LIMIT:
                raise ResourceStop("sixty-call ceiling")
            offset = SERVER_LOG.stat().st_size
            total += 1
            value.update(outcome="attempt_started", attempted=True)
            persist()
            call_start = time.monotonic()
            try:
                response = await guarded_request(client, body, watch, min(240, remaining))
            except (TimeoutError, httpx.TimeoutException) as exc:
                value.update(outcome="failed", reason="call_timeout",
                             timeout=True, failure_type=type(exc).__name__)
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
                value["call_wall_seconds"] = time.monotonic()-call_start
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
            (PRIVATE/f"{row['id']}_{arm}.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
            value["ollama_metrics"] = {k: raw.get(k) for k in (
                "total_duration", "load_duration", "prompt_eval_count", "eval_count")}
            try:
                invalid = truncation_reason(raw, config["options"], new_log_truncation(offset))
            except ValueError:
                invalid = "truncation_log_verification_unavailable"
            if invalid:
                value.update(outcome="failed", reason=invalid, truncated_or_invalid=True)
                persist()
                continue
            value["generation_finished"] = raw.get("done") is True and raw.get("done_reason") == "stop"
            if not value["generation_finished"]:
                value.update(outcome="failed", reason="incomplete_generation")
                persist()
                continue
            try:
                answer = ReaderAnswer.model_validate_json(raw["message"]["content"])
            except (ValidationError, KeyError) as exc:
                value.update(outcome="failed", reason="invalid_model_output",
                             failure_type=type(exc).__name__)
            else:
                value.update(outcome="abstain" if answer.abstain else "answered",
                    citation_locations_or_quotes_valid=references_locally_valid(
                        answer, item, supplied_context=arm=="report_supplied"))
                predictions[row["id"]][arm] = (answer.answer, answer.scale)
            persist()
    return None


async def run(server_pid: int) -> None:
    if RECEIPT.exists():
        raise RuntimeError("REAL2 already attempted; no overwrite/retry")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit source/config before generation")
    config = json.loads(CONFIG.read_text())
    if config["native_assets"] != verified_assets() or any(
        ledger.file_sha256(PROJECT_ROOT/p) != digest for p, digest in config["source_sha256"].items()
    ):
        raise ValueError("frozen source/native assets differ")
    if ledger.file_sha256(REAL1_STATUS) != config["REAL1_result_sha256"]:
        raise ValueError("REAL1 record changed")
    contexts = json.loads((ROOT/"tatqa"/"dev.json").read_bytes())
    by_id = {q["uid"]: (c, q) for c in contexts for q in c["questions"]}
    ids = random.Random(SEED).sample(sorted(set(by_id)-set(config["excluded_ids"])), COUNT)
    if ids != config["ids"] or arm_orders(ids) != config["orders"]:
        raise ValueError("REAL2 selection/order mismatch")
    inputs = {uid: prediction_input(*by_id[uid]) for uid in ids}
    predictions = {uid: {a: (None, "") for a in ARMS} for uid in ids}
    native = load_native(ROOT/"tatqa"/"tatqa_metric.py", "tatqa_real2_native")
    started, cpu_start = time.monotonic(), time.process_time()
    config_hash = ledger.file_sha256(CONFIG)
    policy = SustainedCPU()
    output = {"status": "incomplete", "config_sha256": config_hash,
              "lineage": ledger.lineage([CONFIG, *SOURCES]), "host_CPU_trace": policy.trace,
              "items": [{"id": uid, **{a: {"outcome": "not_attempted", "attempted": False}
                                       for a in ARMS}} for uid in ids]}
    PRIVATE.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        RECEIPT.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
        (PRIVATE/"predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")

    persist()
    watch, stop, complete = None, None, False
    memory = OwnedMemory(server_pid)
    with (PRIVATE/"host_CPU_trace.jsonl").open("x", encoding="utf-8") as trace_file:
        recorder = CPURecorder(started, WindowsCPU(), policy, trace_file)
        try:
            output["launch_host_CPU_percent"] = await wait_for_launch(recorder, started)
            output["launch_wait_seconds"] = time.monotonic()-started
            memory.sample()
            watch = asyncio.create_task(watch_real2(recorder, memory, started))
            async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
                tags, version = await client.get("/api/tags"), await client.get("/api/version")
                tags.raise_for_status()
                version.raise_for_status()
                models = [m for m in tags.json()["models"] if m["name"]==MODEL]
                if len(models)!=1 or models[0]["digest"]!=DIGEST or version.json()["version"]!=config["Ollama_version"]:
                    raise ResourceStop("existing model/server pin differs")
                stop = await generate(config, output["items"], inputs, client, watch,
                                      started, predictions, persist)
                complete = stop is None
        except (httpx.HTTPError, TimeoutError, ResourceStop, ValueError, OSError, RuntimeError) as exc:
            stop = str(exc) if isinstance(exc, ResourceStop) else type(exc).__name__
            if isinstance(exc, (ResourceStop, RuntimeError)):
                output["stop_detail"] = str(exc)
        finally:
            if watch is not None:
                watch.cancel()
                await asyncio.gather(watch, return_exceptions=True)
            if not complete and stop is None:
                stop = "unexpected_interruption"
            output["stop_reason"] = stop
            for row in output["items"]:
                for arm in ARMS:
                    if row[arm]["outcome"] in ("not_attempted", "attempt_started"):
                        row[arm].update(
                            outcome="failed" if row[arm]["attempted"] else "not_attempted",
                            reason=f"run_stopped:{stop or 'unexpected_interruption'}")
            # Generation is permanently over before reading any reference answer/type.
            score_rows(output["items"], {uid: by_id[uid][1] for uid in ids},
                       predictions, native.TaTQAEmAndF1)
            output["report"] = report(output["items"])
            source_ok = ledger.file_sha256(CONFIG)==config_hash and all(
                ledger.file_sha256(PROJECT_ROOT/p)==digest for p, digest in config["source_sha256"].items())
            output.update(
                status="complete" if complete and source_ok else "partial",
                frozen_source_and_config_unchanged=source_ok,
                generation_attempts=sum(r[a]["attempted"] for r in output["items"] for a in ARMS),
                CPU_trace_summary=policy.summary(),
                resources={"wall_seconds": time.monotonic()-started,
                           "Python_CPU_seconds": time.process_time()-cpu_start,
                           "owned_tree_working_set_peak_sample_bytes": memory.peak,
                           "transient_exited_children": memory.exited_children,
                           "note": "Nominal1s timestamped samples/time-weightedwindows; cooperative, "
                                   "not OSquota. HostCPU,PythonCPU,andmodelCPU are distinct."})
            persist()
            print(json.dumps({"status": output["status"], "attempts": output["generation_attempts"],
                              "stop": stop, "arms": output["report"]["arms"],
                              "paired": output["report"]["paired_all_selected"]}))


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    parser.add_argument("--server-pid", type=int)
    args = parser.parse_args()
    if args.phase=="freeze":
        freeze()
    else:
        if args.server_pid is None:
            parser.error("--server-pid required")
        asyncio.run(run(args.server_pid))
