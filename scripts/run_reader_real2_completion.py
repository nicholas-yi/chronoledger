"""Complete only the forty declared REAL2 cases, without touching its stopped records."""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import re
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
    ResourceStop,
    WindowsCPU,
    guarded_request,
)
from run_reader_real1 import TimeoutSequence, real_body, score_rows
from run_reader_real2 import CPURecorder, wait_for_launch

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_completion import combine, completion_plan, effective_config
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid
from asof.reader_real2_guards import SustainedCPU, input_fit, truncation_reason
from asof.reader_real_report import ARMS, arm_summary

BASE = PROJECT_ROOT / "results" / "reader_real2_config.json"
ORIGINAL = PROJECT_ROOT / "results" / "reader_real2_status.json"
ORIGINAL_REVIEW = PROJECT_ROOT / "results" / "reader_real2_review.json"
AMENDMENT = PROJECT_ROOT / "results" / "reader_real2_completion_config.json"
RECEIPT = PROJECT_ROOT / "results" / "reader_real2_completion_status.json"
COMBINED = PROJECT_ROOT / "results" / "reader_real2_combined.json"
PRIVATE = DATA_DIR / "reader_real2_completion"
SERVER_LOG = PRIVATE / "isolated-server.log"
EXPECTED_BASE_SHA256 = "efe477b5948bfbbf212bb927cae7c589557ffe4b8ebc09e036bccb62b3567bf7"
WALL_LIMIT = 4500
NEW_SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "reader_completion.py"]


def suspend_clocks() -> tuple[float, float]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetTickCount64.restype = ctypes.c_ulonglong
    unbiased = ctypes.c_ulonglong()
    if not kernel.QueryUnbiasedInterruptTime(ctypes.byref(unbiased)):
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel.GetTickCount64()/1000, unbiased.value/10_000_000


class SleepAwareCPU(WindowsCPU):
    def __init__(self, clocks=suspend_clocks) -> None:
        super().__init__()
        self.clocks = clocks
        self.previous_clocks = clocks()
        self.interruptions: list[dict] = []

    def check_suspend(self) -> None:
        current = self.clocks()
        asleep = (current[0]-self.previous_clocks[0]) - (current[1]-self.previous_clocks[1])
        self.previous_clocks = current
        if asleep > 2:
            self.interruptions.append({"suspend_seconds_detected": asleep,
                                       "uptime_seconds": current[0],
                                       "awake_uptime_seconds": current[1]})
            raise ResourceStop("host_sleep_interruption; no automatic continuation")

    def percent(self) -> float:
        self.check_suspend()
        return super().percent()


def freeze() -> None:
    if any(p.exists() for p in (AMENDMENT, RECEIPT, COMBINED)):
        raise RuntimeError("completion already frozen/attempted; no overwrite")
    if ledger.file_sha256(BASE) != EXPECTED_BASE_SHA256:
        raise ValueError("REAL2 config differs from the declared amendment base")
    base, original = json.loads(BASE.read_text()), json.loads(ORIGINAL.read_text())
    if base["native_assets"] != verified_assets() or any(
        ledger.file_sha256(PROJECT_ROOT/p) != digest for p, digest in base["source_sha256"].items()
    ):
        raise ValueError("original frozen assets/content/runtime source changed")
    jobs, protected = completion_plan(base, original)
    effective = effective_config(base)
    check = json.loads(json.dumps(effective))
    check["limits"]["owned_process_tree_RSS_bytes"] = 6 << 30
    if check != base:
        raise ValueError("effective contract changes more than owned-memory cap")
    raw_hashes = {}
    for case in protected:
        path = DATA_DIR/"reader_real2"/f"{case['id']}_{case['arm']}.json"
        raw_hashes[str(path.relative_to(DATA_DIR))] = ledger.file_sha256(path)
    amendment = {
        "kind": "REAL2 DECLARED OPERATIONAL COMPLETION, NOT A NEW DESIGN OR SAMPLE",
        "base_config_sha256": EXPECTED_BASE_SHA256,
        "original_artifacts_sha256": {
            str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p)
            for p in (BASE, ORIGINAL, ORIGINAL_REVIEW)},
        "only_runtime_change": {"field": "limits.owned_process_tree_RSS_bytes",
                                "from": 6 << 30, "to": 10 << 30},
        "effective_limits": effective["limits"],
        "cases_in_original_frozen_order": jobs,
        "protected_finished_cases": protected, "protected_raw_sha256": raw_hashes,
        "source_sha256": {
            **base["source_sha256"],
            str((PROJECT_ROOT/"scripts"/"run_reader_real2.py").relative_to(PROJECT_ROOT)):
                ledger.file_sha256(PROJECT_ROOT/"scripts"/"run_reader_real2.py"),
            **{str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in NEW_SOURCES}},
        "protocol": "Same options/model/server/PC1prompt/schema/parse/fit/native scorer/CPU/"
                    "timeouts and75minwall for this completion launch, with fresh11435server. "
                    "Generate exactly39never-attempted+1memory-cancelledcases; no finishedcase "
                    "rerun. All completion generation ends before any new gold/type access. "
                    "New files only. Original failed attempt retained in stopped history.",
        "interpretation": "Amendment declared after initial results were known, based solely on "
                          "memory requirements; no content-dependent changes, tuning or resampling. "
                          "No-report abstention cannot rule out training exposure. Public sample "
                          "only, not historical usability/formalH1/returns.",
        "interruption_handling": "Per user's post-sleep clarification, compare Windows uptime "
                                 "including suspend with unbiased awake uptime. A >2second "
                                 "suspend difference stops/cancels immediately on resumption, "
                                 "records interruption and never resumes automatically.",
    }
    AMENDMENT.write_text(json.dumps(amendment, indent=2, allow_nan=False), encoding="utf-8")
    print({"completion_cases": len(jobs), "protected_cases": len(protected),
           "amendment_sha256": ledger.file_sha256(AMENDMENT)})


def verify_original(amendment: dict) -> None:
    for path, digest in amendment["original_artifacts_sha256"].items():
        if ledger.file_sha256(PROJECT_ROOT/path) != digest:
            raise ValueError("stopped REAL2 artifact changed")
    for path, digest in amendment["protected_raw_sha256"].items():
        if ledger.file_sha256(DATA_DIR/path) != digest:
            raise ValueError("finished original raw prediction changed")


async def watch_completion(recorder, memory, started) -> None:
    while True:
        if await recorder.sample():
            raise ResourceStop("60second hostCPU mean above95percent for120consecutive seconds")
        if memory.sample() > 10 << 30:
            raise ResourceStop("owned isolated process tree working set exceeds10GiB")
        if time.monotonic()-started >= WALL_LIMIT:
            raise ResourceStop("75minute total wall limit")


def log_truncation(offset: int) -> bool:
    with SERVER_LOG.open("rb") as stream:
        stream.seek(offset)
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("server log verification bound exceeded")
    return bool(re.search(r"truncat\w*\s+input\s+prompt|input\s+prompt.{0,100}truncat",
                          raw.decode("utf-8", errors="replace"), re.IGNORECASE))


async def generate(jobs, config, rows, inputs, client, watch, started, predictions,
                   persist, check_suspend):
    indexed = {r["id"]: r for r in rows}
    sequence, total = TimeoutSequence(), 0
    for job in jobs:
        uid, arm = job["id"], job["arm"]
        value, item = indexed[uid][arm], inputs[uid]
        body = real_body(item, arm, config["options"])
        if body["messages"][0]["content"] != config["system_prompt"] or body["format"] != config["schema"]:
            raise ValueError("PC1 prompt/schema changed")
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
        if total >= len(jobs):
            raise ResourceStop("forty-case completion ceiling")
        check_suspend()
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
        check_suspend()
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
        (PRIVATE/f"{uid}_{arm}.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
        value["ollama_metrics"] = {k: raw.get(k) for k in (
            "total_duration", "load_duration", "prompt_eval_count", "eval_count")}
        try:
            invalid = truncation_reason(raw, config["options"], log_truncation(offset))
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
            predictions[uid][arm] = (answer.answer, answer.scale)
        persist()
    return None


async def run(server_pid: int) -> None:
    if RECEIPT.exists() or COMBINED.exists():
        raise RuntimeError("completion already attempted; no retry/overwrite")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit amendment/source before generation")
    amendment = json.loads(AMENDMENT.read_text())
    verify_original(amendment)
    if any(ledger.file_sha256(PROJECT_ROOT/p) != h for p, h in amendment["source_sha256"].items()):
        raise ValueError("frozen completion source changed")
    base, original = json.loads(BASE.read_text()), json.loads(ORIGINAL.read_text())
    config = effective_config(base)
    if config["native_assets"] != verified_assets() or config["limits"] != amendment["effective_limits"]:
        raise ValueError("native assets/effective limits changed")
    jobs, protected = completion_plan(base, original)
    if jobs != amendment["cases_in_original_frozen_order"] or protected != amendment["protected_finished_cases"]:
        raise ValueError("declared completion/protected cases changed")
    ids = list(dict.fromkeys(j["id"] for j in jobs))
    contexts = json.loads((ROOT/"tatqa"/"dev.json").read_bytes())
    by_id = {q["uid"]: (c, q) for c in contexts for q in c["questions"]}
    inputs = {uid: prediction_input(*by_id[uid]) for uid in ids}
    predictions = {uid: {a: (None, "") for a in ARMS} for uid in ids}
    native = load_native(ROOT/"tatqa"/"tatqa_metric.py", "tatqa_real2_completion_native")
    started, cpu_start = time.monotonic(), time.process_time()
    amendment_hash = ledger.file_sha256(AMENDMENT)
    policy = SustainedCPU()
    output = {"status": "incomplete", "amendment_sha256": amendment_hash,
              "lineage": ledger.lineage([AMENDMENT, BASE, ORIGINAL]),
              "host_CPU_trace": policy.trace,
              "items": [{"id": uid, **{a: {"outcome": "not_attempted", "attempted": False}
                                       for a in ARMS}} for uid in ids]}
    PRIVATE.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        RECEIPT.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
        (PRIVATE/"predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")

    persist()
    watch, stop, complete = None, None, False
    memory = OwnedMemory(server_pid)
    with (PRIVATE/"host_CPU_trace.jsonl").open("x", encoding="utf-8") as trace:
        cpu = SleepAwareCPU()
        output["host_sleep_interruptions"] = cpu.interruptions
        recorder = CPURecorder(started, cpu, policy, trace)
        try:
            output["launch_host_CPU_percent"] = await wait_for_launch(recorder, started)
            output["launch_wait_seconds"] = time.monotonic()-started
            memory.sample()
            watch = asyncio.create_task(watch_completion(recorder, memory, started))
            async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
                tags, version = await client.get("/api/tags"), await client.get("/api/version")
                tags.raise_for_status()
                version.raise_for_status()
                models = [m for m in tags.json()["models"] if m["name"]==MODEL]
                if len(models)!=1 or models[0]["digest"]!=DIGEST or version.json()["version"]!=config["Ollama_version"]:
                    raise ResourceStop("existing model/server pin differs")
                stop = await generate(jobs, config, output["items"], inputs, client, watch,
                                      started, predictions, persist, cpu.check_suspend)
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
            # Only the forty completion cases are scored; original twenty are never rescored.
            score_rows(output["items"], {uid: by_id[uid][1] for uid in ids},
                       predictions, native.TaTQAEmAndF1)
            verify_original(amendment)
            source_ok = ledger.file_sha256(AMENDMENT)==amendment_hash and all(
                ledger.file_sha256(PROJECT_ROOT/p)==h for p, h in amendment["source_sha256"].items())
            output.update(
                status="complete" if complete and source_ok else "partial",
                frozen_source_and_amendment_unchanged=source_ok,
                generation_attempts=sum(r[a]["attempted"] for r in output["items"] for a in ARMS),
                remaining_case_summaries={a: arm_summary(output["items"], a) for a in ARMS},
                CPU_trace_summary=policy.summary(),
                resources={"wall_seconds": time.monotonic()-started,
                           "Python_CPU_seconds": time.process_time()-cpu_start,
                           "owned_tree_working_set_peak_sample_bytes": memory.peak,
                           "transient_exited_children": memory.exited_children,
                           "note": "Completion launch has its own unchanged75minlimit; "
                                   "original resource use is separately preserved."})
            persist()
            combined = combine(base, original, output, jobs)
            combined.update(
                original_receipt_sha256=ledger.file_sha256(ORIGINAL),
                completion_receipt_sha256=ledger.file_sha256(RECEIPT),
                amendment_sha256=amendment_hash,
                resources_by_run={
                    "REAL2": {"resources": original["resources"],
                              "CPU_trace_summary": original["CPU_trace_summary"]},
                    "REAL2-C": {"resources": output["resources"],
                                "CPU_trace_summary": output["CPU_trace_summary"]}},
                CPU_trace_sources={"REAL2": str(ORIGINAL.relative_to(PROJECT_ROOT)),
                                   "REAL2-C": str(RECEIPT.relative_to(PROJECT_ROOT))})
            COMBINED.write_text(json.dumps(combined, indent=2, allow_nan=False), encoding="utf-8")
            print(json.dumps({"status": output["status"], "attempts": output["generation_attempts"],
                              "stop": stop, "arms": combined["combined_report"]["arms"],
                              "paired": combined["combined_report"]["paired_all_selected"]}))


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
