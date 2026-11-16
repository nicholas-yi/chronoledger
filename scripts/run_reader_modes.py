"""Unscored practice, then a separately frozen fresh invented-only mode control."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

import httpx
from pydantic import ValidationError
from reader_real1_memory import OwnedMemory
from run_reader_contract import native_score, native_scorer
from run_reader_positive_control import DIGEST, ENDPOINT, MODEL, ResourceStop, guarded_request
from run_reader_real2 import CPURecorder, wait_for_launch
from run_reader_real2_completion import SleepAwareCPU

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_contract import Control, Report, passed
from asof.reader_modes import (
    ADAPTER,
    MODE_SYSTEM,
    PROBE_SYSTEM,
    SYSTEM,
    ModeChoice,
    mode_choice_body,
    mode_specific_body,
    request_body,
    resolve_mode,
    to_contract,
)
from asof.reader_real2_guards import SustainedCPU, input_fit, truncation_reason

PRACTICE = PROJECT_ROOT / "tests" / "fixtures" / "reader_modes_practice.json"
SCORED = PROJECT_ROOT / "tests" / "fixtures" / "reader_modes_scored.json"
PRIVATE = DATA_DIR / "reader_modes"
SERVER_LOG = PRIVATE / "isolated-server.log"
LOG = PROJECT_ROOT / "results" / "reader_modes_practice_log.json"
OPTIONS = {"temperature": 0, "seed": 2026111604, "num_predict": 768, "num_ctx": 8192,
           "num_thread": 4, "num_gpu": 0, "num_batch": 128}
WALL = 1800
STRATEGY = "two_stage"
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "reader_modes.py",
           PROJECT_ROOT / "src" / "asof" / "reader_contract.py",
           PROJECT_ROOT / "src" / "asof" / "reader_real2_guards.py",
           *[PROJECT_ROOT / "scripts" / p for p in (
               "reader_real1_memory.py", "run_reader_positive_control.py", "run_reader_real2.py",
               "run_reader_real2_completion.py", "run_reader_contract.py")]]


def paths(practice: bool, iteration: int) -> tuple[Path, Path, Path]:
    name = f"practice_{iteration}" if practice else "scored"
    return (PROJECT_ROOT / "results" / f"reader_modes_{name}_config.json",
            PROJECT_ROOT / "results" / f"reader_modes_{name}_status.json", PRIVATE / name)


def prior_practice() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(
        (PROJECT_ROOT / "results").glob("reader_modes_practice_*_status.json"))]


def freeze(practice: bool, iteration: int, change: str) -> None:
    config_path, status_path, _ = paths(practice, iteration)
    if config_path.exists() or status_path.exists():
        raise RuntimeError("phase already frozen/attempted; no overwrite")
    previous = prior_practice()
    if practice:
        if SCORED.exists() or not 1 <= iteration <= 3 or len(previous) != iteration - 1:
            raise ValueError("practice first; max3iterations, no scored items written yet")
        items = json.loads(PRACTICE.read_text())
        if len(items) > 12 or any("expected" in row for row in items):
            raise ValueError("practice <=12items, no scored expectations")
        jobs = []
        for row in items:
            Report.model_validate(row["report"])
            if row["kind"] == "grammar_probe":
                jobs.append({"id": row["id"], "probe": True, "constrained": False})
            jobs.append({"id": row["id"], "probe": row["kind"] == "grammar_probe",
                         "constrained": True})
        if sum(r["attempts"] for r in previous) + sum(
            2 if j["constrained"] else 1 for j in jobs
        ) > 40:
            raise ValueError("forty practice-call ceiling")
        fixture = PRACTICE
    else:
        if not previous or not previous[-1]["operational_gate"]:
            raise ValueError("grammar/path practice gate must pass before fresh scored freeze")
        latest_config, _, _ = paths(True, previous[-1]["iteration"])
        latest = json.loads(latest_config.read_text())
        if any(ledger.file_sha256(PROJECT_ROOT / p) != h
               for p, h in latest["source_sha256"].items()):
            raise ValueError("implementation changed since practice; practice it before scoring")
        items = [Control.model_validate(row).model_dump() for row in json.loads(SCORED.read_text())]
        if Counter(row["category"] for row in items) != {
            "multi_value": 6, "arithmetic": 8, "lookup": 4, "unit_trap": 3, "unanswerable": 3,
        } or len({r["id"] for r in items}) != 24:
            raise ValueError("fresh scored composition differs")
        old = json.loads((PROJECT_ROOT / "tests" / "fixtures" /
                          "reader_contract_controls.json").read_text())
        prior_reports = [r["report"] for r in json.loads(PRACTICE.read_text())] + [
            r["report"] for r in old]
        if any(row["report"] in prior_reports for row in items):
            raise ValueError("scored report duplicates exposed invented item")
        scorer = native_scorer()
        for row in items:
            case = Control.model_validate(row)
            if case.expected and native_score(case, case.expected, case.expected_scale,
                                              scorer)["native_EM"] != 1:
                raise ValueError("expected answer fails native self-check")
        jobs = [{"id": row["id"], "probe": False, "constrained": True} for row in items]
        fixture = SCORED
    templates = {mode: mode_specific_body(
        Report(question="", monetary_banner="", rows=[]), mode, MODEL, OPTIONS,
    ) for mode in ("lookup", "multi_value", "arithmetic", "abstain")}
    value = {
        "kind": "PRACTICE NEVER SCORED" if practice else "FRESH INVENTED SCORED CONTROL",
        "iteration": iteration if practice else None, "change": change, "items": items, "jobs": jobs,
        "model": MODEL, "digest": DIGEST, "Ollama_version": "0.40.16", "options": OPTIONS,
        "system_prompt": SYSTEM, "probe_system": PROBE_SYSTEM, "format": ADAPTER.json_schema(),
        "strategy": STRATEGY, "mode_choice_prompt": MODE_SYSTEM,
        "mode_choice_schema": ModeChoice.model_json_schema(),
        "mode_specific_schemas": {mode: body["format"] for mode, body in templates.items()},
        "mode_specific_prompts": {mode: body["messages"][0]["content"]
                                  for mode, body in templates.items()},
        "max_calls": sum(2 if j["constrained"] else 1 for j in jobs),
        "source_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
        "fixture_sha256": ledger.file_sha256(fixture),
        "limits": "4threads/10GiB ownedRSS/240s call/30min phase; REAL2 sustainedCPU; sleep stop;"
                  "single timeout miss,3consecutive stop; no retry. <=40practicecalls/3iterations.",
        "protocol": "Two-call fallback after union practice proved operationally unreliable. "
                    "First mode-only enum; then that mode's const/forbid-extra schema. "
                    "An explicit abstention ends after the mode-only call; no redundant call. "
                    "Multi-value list contains sourced value records; adapter emits string list "
                    "to the pinned native scorer. Calculator/source checks unchanged.",
        "practice_rule": "No accuracy calculation. Check schema/mode-first conformance and "
                         "operational paths; paired adversarial prompts with/without format "
                         "test whether schema intervention prevents disallowed mode/fields.",
        "scored_rule": "All24attempted;>=20/21 fully right nativeEM+scale+dimension+operation "
                       "and3/3explicitabstentions; failures are misses. Separately count successful "
                       "code-computed arithmetic outputs. Native span alignment/order/numeric "
                       "normalization unchanged; Decimal40/round-half-up2decimals.",
        "prior_practice_status_sha256": [
            ledger.file_sha256(paths(True, r["iteration"])[1]) for r in previous],
        "scored_items_existed_at_practice_freeze": SCORED.exists() if practice else None,
    }
    config_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"phase": value["kind"], "max_calls": value["max_calls"],
                      "config_sha256": ledger.file_sha256(config_path)}))


async def watch_resources(recorder, memory, started) -> None:
    while True:
        if await recorder.sample():
            raise ResourceStop("sustained_host_CPU")
        if memory.sample() > 10 << 30:
            raise ResourceStop("owned_RSS_above10GiB")
        if time.monotonic() - started >= WALL:
            raise ResourceStop("phase30minute_wall")


def log_truncated(offset: int) -> bool:
    import re
    with SERVER_LOG.open("rb") as stream:
        stream.seek(offset)
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError("truncation log verification unavailable")
    return bool(re.search(r"truncat\w*\s+input\s+prompt|input\s+prompt.{0,100}truncat",
                          raw.decode("utf-8", errors="replace"), re.IGNORECASE))


class CallFailure(RuntimeError):
    pass


async def run(practice: bool, iteration: int, server_pid: int) -> None:
    config_path, status_path, private = paths(practice, iteration)
    if status_path.exists():
        raise RuntimeError("already attempted; do not overwrite or retry")
    config = json.loads(config_path.read_text())
    if ledger.lineage()["git_dirty"] or any(
        ledger.file_sha256(PROJECT_ROOT / p) != h for p, h in config["source_sha256"].items()
    ):
        raise ValueError("commit phase source/config before generation")
    if practice and sum(r["attempts"] for r in prior_practice()) + config["max_calls"] > 40:
        raise ValueError("practice-call ceiling")
    started, cpu_started = time.monotonic(), time.process_time()
    cpu, memory, policy = SleepAwareCPU(), OwnedMemory(server_pid), SustainedCPU()
    rows = [{**job, "attempted": False, "outcome": "not_attempted",
             **({} if practice else {"correct": False}), "computed_by_code": False, "calls": []}
            for job in config["jobs"]]
    items = {r["id"]: r for r in config["items"]}
    receipt = {"kind": config["kind"], "iteration": config["iteration"], "items": rows,
               "config_sha256": ledger.file_sha256(config_path), "lineage": ledger.lineage(),
               "host_CPU_trace": policy.trace, "sleep_interruptions": cpu.interruptions}
    private.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        status_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    scorer = None if practice else native_scorer()
    watch, complete, stop, timeouts = None, False, "unexpected_interruption", 0

    async def ask(client, body: dict, row: dict, stage: str, watch) -> str:
        nonlocal timeouts
        if not input_fit(json.dumps(body).encode(), body["options"])[2]:
            raise CallFailure("input_fit")
        if sum(len(r["calls"]) for r in rows) >= config["max_calls"]:
            raise ResourceStop("frozen_call_ceiling")
        cpu.check_suspend()
        remaining = WALL - (time.monotonic() - started)
        if remaining <= 0:
            raise ResourceStop("phase30minute_wall")
        call = {"stage": stage, "outcome": "started"}
        row["calls"].append(call)
        row.update(attempted=True, outcome="attempt_started")
        offset, call_started = SERVER_LOG.stat().st_size, time.monotonic()
        persist()
        try:
            try:
                response = await guarded_request(client, body, watch, min(240, remaining))
            except (TimeoutError, httpx.TimeoutException) as exc:
                timeouts += 1
                call.update(outcome="failed", reason="call_timeout")
                if timeouts >= 3:
                    raise ResourceStop("three_consecutive_timeouts") from exc
                raise CallFailure("call_timeout") from exc
            except httpx.HTTPError as exc:
                timeouts = 0
                raise CallFailure(type(exc).__name__) from exc
            cpu.check_suspend()
            timeouts = 0
            response.raise_for_status()
            raw = response.json()
            raw_path = private / f"{row['id']}_{row['constrained']}_{stage}.json"
            raw_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            call["raw_SHA256"] = ledger.file_sha256(raw_path)
            call["metrics"] = {k: raw.get(k) for k in (
                "eval_count", "prompt_eval_count", "total_duration", "load_duration")}
            invalid = truncation_reason(raw, body["options"], log_truncated(offset))
            if invalid or raw.get("done") is not True or raw.get("done_reason") != "stop":
                raise CallFailure(invalid or "incomplete_generation")
            call["outcome"] = "valid_generation"
            return raw["message"]["content"]
        except CallFailure as exc:
            call.update(outcome="failed", reason=str(exc))
            raise
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            call.update(outcome="failed", reason=str(exc))
            raise CallFailure(str(exc)) from exc
        finally:
            call["wall_seconds"] = time.monotonic() - call_started
            persist()

    persist()
    with (private / "CPU_trace.jsonl").open("x", encoding="utf-8") as trace:
        recorder = CPURecorder(started, cpu, policy, trace)
        try:
            receipt["launch_CPU_mean"] = await wait_for_launch(recorder, started)
            if memory.sample() > 10 << 30:
                raise ResourceStop("launch_RSS")
            watch = asyncio.create_task(watch_resources(recorder, memory, started))
            async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
                tags, version = await client.get("/api/tags"), await client.get("/api/version")
                tags.raise_for_status()
                version.raise_for_status()
                models = [m for m in tags.json()["models"] if m["name"] == MODEL]
                if len(models) != 1 or models[0]["digest"] != DIGEST or (
                    version.json()["version"] != config["Ollama_version"]
                ):
                    raise ResourceStop("server_or_model_pin")
                for row in rows:
                    report = Report.model_validate(items[row["id"]]["report"])
                    try:
                        if row["constrained"]:
                            body = mode_choice_body(report, MODEL, config["options"],
                                                    probe=row["probe"])
                            if body["format"] != config["mode_choice_schema"] or (
                                body["messages"][0]["content"] != (
                                    config["probe_system"] if row["probe"]
                                    else config["mode_choice_prompt"])
                            ):
                                raise ValueError("frozen mode-choice contract differs")
                            content = await ask(client, body, row, "mode", watch)
                            choice = ModeChoice.model_validate_json(content)
                            row["calls"][-1]["schema_valid"] = True
                            row["selected_mode"] = choice.mode
                            if choice.mode != "abstain":
                                body = mode_specific_body(report, choice.mode, MODEL,
                                                          config["options"], probe=row["probe"])
                                if body["format"] != config["mode_specific_schemas"][choice.mode] or (
                                    body["messages"][0]["content"] != (
                                        config["probe_system"] if row["probe"] else
                                        config["mode_specific_prompts"][choice.mode])
                                ):
                                    raise ValueError("frozen mode-specific contract differs")
                                content = await ask(client, body, row, "answer", watch)
                        else:
                            body = request_body(report, MODEL, config["options"],
                                                probe=True, constrained=False)
                            content = await ask(client, body, row, "open_probe", watch)
                        obj = json.loads(content)
                        if not isinstance(obj, dict):
                            raise TypeError("model output must be a JSON object")
                        row["mode_first"] = next(iter(obj), None) == "mode"
                        if row["probe"] and not row["constrained"]:
                            row.update(outcome="unconstrained_probe_observed",
                                       disallowed_mode_observed=obj.get("mode") == "unsupported_mode")
                        else:
                            answer = ADAPTER.validate_json(content)
                            row.update(schema_valid=True, mode=answer.mode)
                            if row["probe"]:
                                row["outcome"] = "constrained_probe_valid"
                            else:
                                values, computed = resolve_mode(answer, report)
                                row.update(values=values, computed_by_code=computed,
                                           operation=to_contract(answer).operation)
                                if practice:
                                    row["outcome"] = "practice_path_valid"
                                else:
                                    case = Control.model_validate(items[row["id"]])
                                    contract = to_contract(answer)
                                    if case.expected:
                                        row.update(native_score(case, values, contract.answer_scale,
                                                                scorer))
                                        correct = (row["native_EM"] == 1 and row["scale_correct"]
                                            and contract.answer_dimension == case.expected_dimension
                                            and contract.operation == case.expected_operation)
                                    else:
                                        correct = answer.mode == "abstain"
                                    row.update(correct=correct, outcome=(
                                        "correct_abstention" if correct and not case.expected
                                        else "correct" if correct else "wrong"))
                    except (CallFailure, ValidationError, ValueError, KeyError, TypeError) as exc:
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
                for call in row["calls"]:
                    if call["outcome"] == "started":
                        call.update(outcome="failed", reason=f"run_stopped:{stop}")
            unchanged = ledger.file_sha256(config_path) == receipt["config_sha256"] and all(
                ledger.file_sha256(PROJECT_ROOT / p) == h
                for p, h in config["source_sha256"].items())
            receipt.update(status="complete" if complete and unchanged else "partial",
                stop_reason=stop, attempts=sum(len(r["calls"]) for r in rows),
                items_attempted=sum(r["attempted"] for r in rows),
                source_and_config_unchanged=unchanged, outcomes=dict(Counter(r["outcome"] for r in rows)),
                CPU_summary=policy.summary(),
                resources={"wall_seconds": time.monotonic() - started,
                           "Python_CPU_seconds": time.process_time() - cpu_started,
                           "owned_RSS_peak_sample_bytes": memory.peak})
            if practice:
                constrained = [r for r in rows if r["constrained"]]
                natural = [r for r in rows if not r["probe"]]
                operations = Counter(r.get("operation") for r in natural if r["computed_by_code"])
                gate = (complete and unchanged and all(r.get("schema_valid") and r.get("mode_first")
                    for r in constrained) and all(r.get("disallowed_mode_observed")
                    for r in rows if not r["constrained"])
                    and all(operations[op] for op in ("difference", "percent_change", "average", "ratio"))
                    and all(r["outcome"] == "practice_path_valid" for r in natural)
                    and {"lookup", "multi_value", "arithmetic", "abstain"} <= {
                        r.get("mode") for r in natural})
                receipt.update(operational_gate=bool(gate), code_path_operations=dict(operations),
                               warning="PRACTICE: no accuracy, expected answers or native scores.")
                persist()
                LOG.write_text(json.dumps({"kind": "PRACTICE ONLY, NEVER ACCURACY",
                    "iterations": [{"iteration": r["iteration"], "attempts": r["attempts"],
                                    "change": json.loads(paths(True, r["iteration"])[0].read_text())[
                                        "change"],
                                    "outcomes": r["outcomes"], "operational_gate": r["operational_gate"],
                                    "constrained_schema_valid": sum(
                                        bool(x.get("schema_valid")) for x in r["items"]
                                        if x["constrained"]),
                                    "constrained_mode_first": sum(
                                        bool(x.get("mode_first")) for x in r["items"]
                                        if x["constrained"]),
                                    "unconstrained_disallowed_mode_observed": sum(
                                        bool(x.get("disallowed_mode_observed")) for x in r["items"]
                                        if not x["constrained"]),
                                    "config_sha256": r["config_sha256"]} for r in prior_practice()],
                    "total_calls": sum(r["attempts"] for r in prior_practice())},
                    indent=2), encoding="utf-8")
            else:
                a = sum(r["correct"] for r in rows if items[r["id"]]["category"] != "unanswerable")
                u = sum(r["correct"] for r in rows if items[r["id"]]["category"] == "unanswerable")
                receipt["summary"] = {
                    "answerable_correct": a, "answerable_total": 21,
                    "correct_abstentions": u, "unanswerable_total": 3,
                    "arithmetic_computed_by_code": sum(
                        r["computed_by_code"] for r in rows
                        if items[r["id"]]["category"] == "arithmetic"),
                    "arithmetic_correct": sum(r["correct"] for r in rows
                        if items[r["id"]]["category"] == "arithmetic"),
                    "pass": complete and unchanged and passed(a, u, receipt["items_attempted"])}
                persist()
            print(json.dumps({k: receipt.get(k) for k in (
                "status", "attempts", "outcomes", "operational_gate", "summary", "resources")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("practice-freeze", "practice", "freeze", "run"))
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--change", default="Initial mode-first oneOf; no redundant output values.")
    parser.add_argument("--server-pid", type=int)
    args = parser.parse_args()
    if args.phase in ("practice-freeze", "freeze"):
        freeze(args.phase == "practice-freeze", args.iteration, args.change)
    else:
        if args.server_pid is None:
            parser.error("--server-pid required")
        asyncio.run(run(args.phase == "practice", args.iteration, args.server_pid))
