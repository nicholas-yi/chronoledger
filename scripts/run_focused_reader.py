"""One frozen invented local reader/critic comparison; no corpus, trading or weight training."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx
from pydantic import ValidationError

from asof.focused_reader import (
    Answer,
    Case,
    CompactCritique,
    Critique,
    account_incomplete_attempts,
    choose_final,
    development_lessons,
    messages,
    parser_answer,
    promotion_gate,
    score,
    summarize,
    verified_error_bank,
)
from asof.linked_reader import (
    LinkedResult,
    challenge_cases,
    complete_evidence,
    development_replay,
    linked_parser,
    result_record,
    summarize_challenge,
)
from asof.local_model_runtime import RuntimePolicy, launch_owned_server, verify_supported_package
from asof.reader_fields import (
    contexts,
    field_messages,
    field_record,
    guarded_parser,
    load_field_cases,
    parser_first,
    summarize_fields,
)
from asof.reader_real2_guards import input_fit, truncation_reason
from asof.reader_stress import audit_cases, build_fixture, model_summary, offline_baselines
from asof.runtime import THREAD_VARIABLES, WorkerJob, peak_rss_bytes, write_receipt
from asof.runtime import frozen_receipt as committed_sources
from asof.verified_reader import (
    Verification,
    binding_parser,
    load_robustness_cases,
    summarize_robustness,
    verify_response,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "results" / "focused_reader_plan.json"
FIXTURE = ROOT / "tests" / "fixtures" / "focused_reader.json"
REPORT = ROOT / "results" / "focused_reader.json"
PRIVATE = ROOT / "data" / "focused_reader_v1"
FROZEN = (
    "scripts/run_focused_reader.py", "src/asof/focused_reader.py", "src/asof/runtime.py",
    "src/asof/extraction.py", "src/asof/local_model_runtime.py", "src/asof/reader_real2_guards.py",
    "src/asof/reader_positive_control.py", "src/asof/reader_diagnostic.py",
    "src/asof/benchmark_baseline.py", "src/asof/ledger.py",
    "tests/fixtures/focused_reader.json", "tests/test_focused_reader.py",
    "results/focused_reader_plan.json", "results/local_model_runtime_support.json",
    "requirements-dev.lock", "docs/FOCUSED_READER.md",
)
V1_FROZEN = FROZEN


def select_version(version: str) -> None:
    """Explicit run selection; never recycle the stopped v1 output or attempt marker."""
    global PLAN, REPORT, PRIVATE, FROZEN, FIXTURE
    if version not in ("v1", "v2", "verifier", "stress", "linked", "fields"):
        raise ValueError("unknown focused reader version")
    FIXTURE = ROOT / "tests" / "fixtures" / "focused_reader.json"
    if version in ("verifier", "stress", "linked", "fields"):
        stem = {"stress": "reader_stress", "verifier": "verified_reader",
                "linked": "linked_reader", "fields": "reader_fields"}[version]
        fixture_name = "linked_challenge" if version == "linked" else stem
        PLAN = ROOT / "results" / f"{stem}_plan.json"
        REPORT = ROOT / "results" / f"{stem}.json"
        PRIVATE = ROOT / "data" / f"{stem}_v1"
        FIXTURE = ROOT / "tests" / "fixtures" / f"{fixture_name}.json"
        FROZEN = tuple(
            f"results/{stem}_plan.json" if path == "results/focused_reader_plan.json"
            else f"tests/fixtures/{fixture_name}.json" if path == "tests/fixtures/focused_reader.json"
            else path for path in V1_FROZEN)
        FROZEN = (*FROZEN, "src/asof/verified_reader.py", "tests/test_verified_reader.py",
                  "results/focused_reader.json", "results/focused_reader_v2.json")
        if version == "stress":
            FROZEN = (*FROZEN, "src/asof/reader_stress.py", "tests/test_reader_stress.py",
                      "results/verified_reader.json")
        elif version in ("linked", "fields"):
            FROZEN = (*FROZEN, "src/asof/linked_reader.py", "tests/test_linked_reader.py",
                      "src/asof/reader_stress.py", "tests/fixtures/reader_stress.json",
                      "results/reader_stress.json", "results/verified_reader.json")
            if version == "fields":
                FROZEN = (*FROZEN, "src/asof/reader_fields.py", "tests/test_reader_fields.py",
                          "results/linked_reader.json")
        return
    suffix = "_v2" if version == "v2" else ""
    PLAN = ROOT / "results" / f"focused_reader{suffix}_plan.json"
    REPORT = ROOT / "results" / f"focused_reader{suffix}.json"
    PRIVATE = ROOT / "data" / f"focused_reader_{version}"
    FROZEN = tuple("results/focused_reader_v2_plan.json" if (
        version == "v2" and path == "results/focused_reader_plan.json") else path
                   for path in V1_FROZEN)
    if version == "v2":
        FROZEN = (*FROZEN, "results/focused_reader.json")


def load_cases(path: Path) -> tuple[Case, ...]:
    raw = json.loads(path.read_bytes())
    if path.name == "verified_reader.json":
        return load_robustness_cases(raw)
    if path.name == "reader_stress.json":
        return audit_cases(build_fixture(raw))
    if path.name == "linked_challenge.json":
        return challenge_cases(raw)
    if path.name == "reader_fields.json":
        return load_field_cases(raw)
    if set(raw) != {"development", "evaluation"} or any(len(rows) != 6 for rows in raw.values()):
        raise ValueError("exactly six development and six evaluation invented fixtures required")
    cases = tuple(Case(**{
        **row, "split": split, "expected": tuple(row["expected"]) if row["expected"] else None,
    }) for split in ("development", "evaluation") for row in raw[split])
    if len({case.id for case in cases}) != 12:
        raise ValueError("case identities must be unique")
    if any(not case.id.startswith("D" if case.split == "development" else "E")
           or not case.source.strip() or len(case.source) > 2000 for case in cases):
        raise ValueError("fixture identity, source or input cap invalid")
    if any(case.probe is None for case in cases[:6]) or any(case.probe for case in cases[6:]):
        raise ValueError("wrong-answer calibration probes belong only to development")
    if any(score(case, Answer.model_validate(case.probe))["correct"] for case in cases[:6]):
        raise ValueError("calibration probe must be independently known wrong in its invented fixture")
    return cases


def hashes() -> dict:
    return {path: hashlib.sha256(ROOT.joinpath(*path.split("/")).read_bytes()).hexdigest()
            for path in FROZEN}


def freeze_receipt() -> dict:
    return committed_sources(ROOT, FROZEN)


def validate_plan(plan: dict) -> None:
    fixed = {
        "study": plan.get("study"), "model": "qwen3.5:4b",
        "digest": "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04",
        "endpoint": "http://127.0.0.1:11435", "case_count": 12,
        "max_calls": 36, "wall_seconds": 1200, "controller_stop_seconds": 1180,
        "RAM_bytes": 6 << 30, "controller_RAM_allowance": 128 << 20,
        "call_seconds": 90, "startup_seconds": 60,
        "options": {"temperature": 0, "seed": 202611190611, "num_ctx": 2048,
                    "num_predict": 384, "num_thread": 1, "num_gpu": 0, "num_batch": 64},
    }
    if plan.get("study") == "CL-FOCUS-LAAJ-02":
        fixed["critic_contract"] = "bounded_enums_no_freeform_feedback"
        fixed["critic_num_predict"] = 128
    elif plan.get("study") == "CL-FOCUS-VERIFY-01":
        fixed["case_count"] = fixed["max_calls"] = 24
        fixed["options"]["seed"] = 202611190752
    elif plan.get("study") == "CL-FOCUS-STRESS-01":
        fixed["case_count"] = fixed["max_calls"] = 24
        fixed["options"]["seed"] = 202611190824
        fixed["offline_cases"] = 288
        fixed["output_truncation_policy"] = "count_invalid_and_continue_without_retry"
    elif plan.get("study") == "CL-FOCUS-LINKED-01":
        fixed["case_count"] = fixed["max_calls"] = 24
        fixed["options"]["seed"] = 202611190926
        fixed["evidence_contract"] = "linked-evidence-v1"
        fixed["output_truncation_policy"] = "count_invalid_and_continue_without_retry"
    elif plan.get("study") == "CL-FOCUS-FIELDS-01":
        fixed["case_count"] = fixed["max_calls"] = 24
        fixed["options"]["seed"] = 202611191124
        fixed["evidence_contract"] = "field-record-v1"
        fixed["output_truncation_policy"] = "count_invalid_and_continue_without_retry"
    elif plan.get("study") != "CL-FOCUS-LAAJ-01":
        raise ValueError("unknown focused reader study")
    if plan != fixed:
        raise ValueError("local model plan differs from the approved fixed allocation")


def require_free_port(port: int = 11435) -> None:
    """Test OS port ownership, not whether an HTTP request to an absent listener times out."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError("isolated port is unavailable; never alter another server") from exc


def worker(plan: dict, channel) -> None:
    if channel.recv() != "focused-reader-owned-job-ready":
        raise RuntimeError("owned-process containment handshake required")
    if plan["study"] == "CL-FOCUS-LAAJ-02":
        select_version("v2")  # Spawned workers do not inherit CLI module-global selection.
    stress = plan["study"] == "CL-FOCUS-STRESS-01"
    field_mode = plan["study"] == "CL-FOCUS-FIELDS-01"
    linked_mode = field_mode or plan["study"] == "CL-FOCUS-LINKED-01"
    verified = plan["study"] in (
        "CL-FOCUS-VERIFY-01", "CL-FOCUS-STRESS-01", "CL-FOCUS-LINKED-01", "CL-FOCUS-FIELDS-01")
    if verified:
        select_version("fields" if field_mode else "linked" if linked_mode else "stress" if stress else "verifier")
    server = None
    records: dict[str, dict] = {}
    calls = []
    calibration = []
    status, reason = "stopped", None
    started = time.monotonic()
    candidate = None
    offline = None
    cases = load_cases(FIXTURE)
    field_labels = contexts(json.loads(FIXTURE.read_bytes())) if field_mode else {}

    def check_time() -> None:
        if time.monotonic()-started >= plan["controller_stop_seconds"]-15:
            raise TimeoutError("worker wall ceiling")

    def checkpoint(stage: str) -> None:
        channel.send({"kind": "checkpoint", "records": records, "calls": calls,
                      "judge_calibration": calibration, "phase": stage, "candidate": candidate,
                      "offline_baselines": offline})

    try:
        if stress:
            offline = offline_baselines(build_fixture(json.loads(FIXTURE.read_bytes())))
            checkpoint("offline_288_baselines_complete")
        elif linked_mode and not field_mode:
            offline = development_replay(
                json.loads((ROOT / "tests" / "fixtures" / "reader_stress.json").read_bytes()),
                json.loads((ROOT / "results" / "reader_stress.json").read_bytes()))
            checkpoint("posthoc_development_replay_complete")
        executable = shutil.which("ollama")
        if executable is None:
            raise FileNotFoundError("existing Ollama executable absent; no install or pull")
        verify_supported_package(Path(executable))
        # Scoped to this owned worker and descendants, never the existing 11434 service.
        os.environ.update(CUDA_VISIBLE_DEVICES="-1", ROCR_VISIBLE_DEVICES="-1",
                          GGML_VK_VISIBLE_DEVICES="-1", OLLAMA_LLM_LIBRARY="cpu_avx2")
        server = launch_owned_server(
            Path(executable), PRIVATE / "server.log", PRIVATE / "server_receipt.json",
            RuntimePolicy(0))
        channel.send({"kind": "server", "pid": server.pid})
        with httpx.Client(base_url=plan["endpoint"], trust_env=False,
                          follow_redirects=False, timeout=3) as client:
            ready = False
            while time.monotonic()-started < plan["startup_seconds"]:
                check_time()
                if server.poll() is not None:
                    raise RuntimeError("owned server exited during startup")
                try:
                    response = client.get("/api/tags")
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    time.sleep(0.25)
                    continue
                response.raise_for_status()
                models = response.json().get("models", [])
                if not any(item.get("name") == plan["model"] and item.get("digest") == plan["digest"]
                           for item in models):
                    raise ValueError("cached model/digest absent; pulling is forbidden")
                ready = True
                break
            if not ready:
                raise TimeoutError("owned server readiness timeout")

            def call(case: Case, stage: str, *, draft=None, critique=None, lessons=()):
                check_time()
                if len(calls) >= plan["max_calls"]:
                    raise RuntimeError("model-call ceiling before next attempt")
                compact = plan["study"] == "CL-FOCUS-LAAJ-02"
                body = {
                    "model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                    "messages": messages(case, stage, draft=draft, critique=critique, lessons=lessons,
                                         compact_critic=compact),
                    "options": {**plan["options"], "num_predict": (
                        plan.get("critic_num_predict", 256) if stage == "judge" else 384)},
                }
                if field_mode:
                    body["messages"] = field_messages(case)
                if compact and stage == "judge":
                    body["format"] = CompactCritique.model_json_schema()
                encoded = json.dumps(body, sort_keys=True).encode()
                if not input_fit(encoded, body["options"])[2]:
                    raise ValueError("frozen input estimate exceeds context margin; no truncation")
                attempt = {"call_id": len(calls)+1, "case_id": case.id, "stage": stage,
                           "request_sha256": hashlib.sha256(encoded).hexdigest(),
                           "status": "started", "latency_seconds": None, "generated_tokens": None}
                calls.append(attempt)
                write_receipt(PRIVATE / f"call_{attempt['call_id']:02d}_start.json", attempt)
                checkpoint("before_model_attempt")
                begin = time.monotonic()
                try:
                    response = client.post("/api/chat", json=body, timeout=min(
                        plan["call_seconds"], plan["controller_stop_seconds"]-(begin-started)-5))
                    response.raise_for_status()
                except httpx.HTTPError:
                    attempt.update(status="transport_or_HTTP_failure",
                                   latency_seconds=time.monotonic()-begin)
                    checkpoint("failed_model_attempt")
                    raise
                if len(response.content) > 65536:
                    raise ValueError("response exceeds 64KiB")
                raw = response.json()
                attempt["latency_seconds"] = time.monotonic()-begin
                attempt["generated_tokens"] = raw.get("eval_count")
                if type(attempt["generated_tokens"]) is not int:
                    raise ValueError("model generation token telemetry unavailable")
                attempt["status"] = "received"
                write_receipt(PRIVATE / f"call_{attempt['call_id']:02d}.json",
                              {"attempt": attempt, "response": raw})
                issue = truncation_reason(raw, body["options"])
                output_limited = (stress or linked_mode) and issue == "output_token_limit_or_truncation"
                if (issue and not output_limited) or raw.get("done") is not True:
                    attempt["status"] = "truncated_or_incomplete"
                    checkpoint("invalid_complete_response")
                    raise ValueError(f"generation incomplete:{issue}")
                content = raw.get("message", {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    if output_limited:
                        content = ""
                    else:
                        attempt["status"] = "empty_visible_response"
                        raise ValueError("model returned empty visible content")
                if output_limited:
                    parsed = None
                    attempt["status"] = "output_truncated_invalid_case"
                else:
                    try:
                        if compact and stage == "judge":
                            parsed = CompactCritique.model_validate_json(content).expanded()
                        else:
                            parsed = (Critique if stage == "judge" else Answer).model_validate_json(content)
                        attempt["status"] = "schema_valid"
                    except ValidationError:
                        parsed = None
                        attempt["status"] = "schema_invalid"
                model_state = client.get("/api/ps")
                model_state.raise_for_status()
                loaded = model_state.json().get("models", [])
                if not loaded or any(item.get("size_vram") != 0 for item in loaded):
                    raise RuntimeError("CPU-only execution not verified by owned server model state")
                checkpoint("after_model_attempt")
                # Feedback in v2 is a deterministic expansion, not new model-generated claims.
                effective = parsed.model_dump_json() if compact and stage == "judge" and parsed else content
                return parsed, effective, attempt.copy()

            def judge_record(case: Case, draft: str, gold_correct: bool, label: str):
                opinion, content, cost = call(case, "judge", draft=draft)
                calibration.append({
                    "case_id": case.id, "draft_kind": label, "draft_known_correct": gold_correct,
                    "verdict": opinion.verdict if opinion else None,
                    "judge_valid": opinion is not None,
                    "label_provenance": "authored_invented_fixture_not_human_or_judge_gold",
                })
                return opinion, content, cost

            # Calibration/development first. No revisions here; six probes are deliberately wrong.
            for case in (() if verified else cases[:6]):
                base, text, cost = call(case, "generate")
                records[case.id] = {
                    "parser": {"answer": parser_answer(case).model_dump(),
                               "score": score(case, parser_answer(case))},
                    "single_pass": {"answer": base.model_dump() if base else None,
                                    "score": score(case, base),
                                    "latency_seconds": cost["latency_seconds"],
                                    "generated_tokens": cost["generated_tokens"]},
                }
                judge_record(case, text, score(case, base)["correct"], "actual_development_draft")
                judge_record(case, json.dumps(case.probe), False, "known_wrong_probe")
                checkpoint("development_case_complete")

            lessons = ()
            if not verified:
                errors = verified_error_bank(cases, records)
                lessons = development_lessons(errors)
                candidate = {
                    "lessons": list(lessons), "development_error_ids": [e["case_id"] for e in errors],
                    "adaptive_rule": "fixed reminder selection from verified development errors only",
                    "before_any_evaluation_model_call": True, "weights_updated": False,
                }
                candidate["sha256"] = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
                write_receipt(PRIVATE / "verified_development_errors.json", {"errors": errors})
                write_receipt(PRIVATE / "candidate_before_evaluation.json", candidate)
                checkpoint("candidate_frozen_before_evaluation")
            for case in (cases if verified else cases[6:]):
                base, text, cost = call(case, "generate")
                records[case.id] = {
                    "parser": {"answer": parser_answer(case).model_dump(),
                               "score": score(case, parser_answer(case))},
                    "single_pass": {"answer": base.model_dump() if base else None,
                                    "score": score(case, base),
                                    "latency_seconds": cost["latency_seconds"],
                                    "generated_tokens": cost["generated_tokens"]},
                }
                if verified:
                    before = time.perf_counter()
                    stronger = binding_parser(case)
                    parser_seconds = time.perf_counter()-before
                    before = time.perf_counter()
                    verification = (Verification(None, "invalid_response", ("output_truncated",))
                                    if cost["status"] == "output_truncated_invalid_case"
                                    else verify_response(case, text))
                    verify_seconds = time.perf_counter()-before
                    records[case.id]["binding_parser"] = {
                        "answer": stronger.model_dump(), "score": score(case, stronger),
                        "latency_seconds": parser_seconds, "generated_tokens": 0}
                    records[case.id]["verified"] = {
                        "answer": verification.answer.model_dump() if verification.answer else None,
                        "score": score(case, verification.answer), "status": verification.status,
                        "reasons": list(verification.reasons),
                        "latency_seconds": cost["latency_seconds"]+verify_seconds,
                        "verification_seconds": verify_seconds,
                        "generated_tokens": cost["generated_tokens"],
                        "same_initial_generation_as_single_pass": True}
                    if linked_mode:
                        before = time.perf_counter()
                        source_result = linked_parser(case)
                        source_seconds = time.perf_counter()-before
                        before = time.perf_counter()
                        completed = (LinkedResult(None, None, "invalid_response", ("output_truncated",))
                                     if cost["status"] == "output_truncated_invalid_case"
                                     else complete_evidence(case, text))
                        linked_seconds = time.perf_counter()-before
                        records[case.id]["linked_parser"] = {
                            **result_record(case, source_result), "latency_seconds": source_seconds,
                            "generated_tokens": 0}
                        records[case.id]["linked"] = {
                            **result_record(case, completed),
                            "latency_seconds": cost["latency_seconds"]+linked_seconds,
                            "evidence_completion_seconds": linked_seconds,
                            "generated_tokens": cost["generated_tokens"],
                            "same_initial_generation_as_single_pass": True}
                        if field_mode:
                            before = time.perf_counter()
                            guarded = guarded_parser(case)
                            guarded_seconds = time.perf_counter()-before
                            before = time.perf_counter()
                            decision = parser_first(
                                case, "" if cost["status"] == "output_truncated_invalid_case" else text)
                            decision_seconds = time.perf_counter()-before
                            for name, result, seconds in (
                                ("linked_parser", source_result, source_seconds),
                                ("linked", completed, cost["latency_seconds"]+linked_seconds),
                                ("guarded_parser", guarded, guarded_seconds),
                                ("parser_first", decision.result, decision_seconds+(
                                    cost["latency_seconds"] if decision.model_required else 0)),
                            ):
                                records[case.id][name] = {
                                    **field_record(case, result, field_labels[case.id]),
                                    "latency_seconds": seconds,
                                    "latency_basis": "selected_arm_excluding_unused_audit_generation_not_wall",
                                    "same_input_and_common_field_contract": True,
                                }
                            records[case.id]["parser_first"].update(
                                route=decision.route,
                                counterfactual_model_calls=int(decision.model_required),
                                original_generation_saved_separately=True)
                    write_receipt(PRIVATE / f"case_{case.id}.json", records[case.id])
                    checkpoint("verifier_case_complete")
                    continue
                opinion, feedback, judge_cost = call(case, "judge", draft=text, lessons=lessons)
                revision = None
                revision_cost = {"latency_seconds": 0, "generated_tokens": 0}
                if opinion is not None and opinion.verdict != "accept":
                    revision, _, revision_cost = call(
                        case, "revise", draft=text, critique=feedback, lessons=lessons)
                final, selection = choose_final(case, base, revision)
                records[case.id]["judge_assisted"] = {
                    "answer": final.model_dump(), "score": score(case, final),
                    "selection": selection, "judge_verdict": opinion.verdict if opinion else None,
                    "latency_seconds": sum(c["latency_seconds"]
                                           for c in (cost, judge_cost, revision_cost)),
                    "generated_tokens": sum(c["generated_tokens"]
                                           for c in (cost, judge_cost, revision_cost)),
                    "same_initial_generation_as_single_pass": True,
                }
                write_receipt(PRIVATE / f"case_{case.id}.json", records[case.id])
                checkpoint("evaluation_case_complete")
            status = "complete_invented_comparison"
    except (OSError, ValueError, RuntimeError, httpx.HTTPError, TimeoutError) as exc:
        reason = f"{type(exc).__name__}:{exc}"
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3)
    checkpoint("final")
    channel.send({"kind": "final", "status": status, "stop_reason": reason,
                  "records": records, "calls": calls, "judge_calibration": calibration,
                  "candidate": candidate, "worker_wall_seconds": time.monotonic()-started,
                  "offline_baselines": offline})
    channel.close()


def run() -> int:
    if REPORT.exists() or (PRIVATE / "attempt.json").exists():
        raise FileExistsError("already attempted; no automatic retry/resume")
    plan = json.loads(PLAN.read_bytes())
    validate_plan(plan)
    load_cases(FIXTURE)
    if any(os.environ.get(key) != "1" for key in THREAD_VARIABLES):
        raise ValueError("all numerical thread environment variables must be one")
    require_free_port()
    lineage = freeze_receipt()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    write_receipt(PRIVATE / "attempt.json", {"lineage": lineage, "plan": plan})
    started = time.monotonic()
    report = {"study": plan["study"], "plan": plan, "lineage": lineage, "status": "stopped",
              "stop_reason": None, "records": {}, "calls": [], "judge_calibration": [],
              "candidate": None, "real_data_read": False, "weights_updated": False,
              "production_ledger_rows": 0}
    job = process = parent = child = None
    original_affinity = None
    peak = 0
    all_pids: set[int] = set()
    try:
        job = WorkerJob(memory_bytes=plan["RAM_bytes"]-plan["controller_RAM_allowance"],
                        max_processes=4)
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=worker, args=(plan, child))
        process.start()
        child.close()
        if process.pid is None:
            raise RuntimeError("owned worker has no PID")
        report["worker_pid"] = process.pid
        mask = job.attach(process.pid)
        original_affinity = job.pin(os.getpid(), mask)
        report["affinity_mask"] = mask
        parent.send("focused-reader-owned-job-ready")
        final = None
        while final is None:
            if time.monotonic()-started >= plan["controller_stop_seconds"]:
                raise TimeoutError("controller wall ceiling")
            snapshot = job.sample()
            all_pids.update(row["pid"] for row in snapshot["processes"])
            if any(row["affinity_mask"] != mask for row in snapshot["processes"]):
                raise RuntimeError("owned process did not inherit single-CPU affinity")
            peak = max(peak, snapshot["RSS_bytes"]+peak_rss_bytes())
            if peak >= plan["RAM_bytes"]:
                raise RuntimeError("six-GiB combined working-set ceiling")
            with (PRIVATE / "resources.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"elapsed": time.monotonic()-started, **snapshot})+"\n")
            if not parent.poll(0.5):
                if not process.is_alive():
                    raise RuntimeError("worker exited without a final receipt")
                continue
            message = parent.recv()
            if message["kind"] in ("checkpoint", "final"):
                report.update({k: v for k, v in message.items() if k != "kind"})
                if message["kind"] == "final":
                    final = message
            elif message["kind"] == "server":
                report["server_pid"] = message["pid"]
            else:
                raise ValueError("unknown owned-worker message")
        process.join(timeout=5)
        if process.is_alive() or process.exitcode != 0:
            raise RuntimeError("owned worker did not exit cleanly")
    except (OSError, ValueError, RuntimeError, EOFError, TimeoutError) as exc:
        report["status"], report["stop_reason"] = "stopped", f"{type(exc).__name__}:{exc}"
    finally:
        if job is not None:
            try:
                if original_affinity is not None:
                    job.pin(os.getpid(), original_affinity)
            except OSError as exc:
                report["status"] = "stopped"
                report["cleanup_issue"] = f"controller_affinity_restore_failed:{exc}"
                report["stop_reason"] = report["stop_reason"] or report["cleanup_issue"]
            finally:
                job.close()
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            report["worker_exit_code"] = process.exitcode
            process.close()
        for channel in (parent, child):
            if channel is not None:
                channel.close()
    cases = load_cases(FIXTURE)
    report["records"] = account_incomplete_attempts(cases, report["records"], report["calls"])
    if plan["study"] == "CL-FOCUS-FIELDS-01":
        report["summary"] = summarize_fields(
            cases, report["records"], contexts(json.loads(FIXTURE.read_bytes())))
        report["promotion"] = {"promote": False, "reason": "authored field challenge; human review blocked"}
    elif plan["study"] == "CL-FOCUS-LINKED-01":
        report["summary"] = summarize_challenge(cases, report["records"])
        report["development_replay"] = report.pop("offline_baselines", None)
        report["promotion"] = {"promote": False, "reason": "new evidence contract on authored cases; no real gold"}
    elif plan["study"] == "CL-FOCUS-STRESS-01":
        report["summary"] = model_summary(cases, report["records"])
        report["promotion"] = {"promote": False, "reason": "template stress diagnostic, no independent gold"}
    elif plan["study"] == "CL-FOCUS-VERIFY-01":
        report["summary"] = summarize_robustness(
            cases, report["records"], json.loads(FIXTURE.read_bytes()))
        report["promotion"] = {"promote": False, "reason": "authored grammar fixtures, no independent gold"}
    else:
        report["summary"] = summarize(cases, report["records"])
        report["promotion"] = promotion_gate(cases, report["records"], independent_audit=False)
    report["controller_wall_seconds"] = time.monotonic()-started
    report["observed_combined_peak_RSS_bytes"] = peak
    report["owned_pids_observed"] = sorted(all_pids)
    report["source_unchanged"] = hashes() == lineage["source_SHA256"]
    report["resource_check_passed"] = (
        report["controller_wall_seconds"] < plan["wall_seconds"]
        and peak < plan["RAM_bytes"] and report.get("affinity_mask", 0).bit_count() == 1
        and len(report["calls"]) <= plan["max_calls"])
    if not report["source_unchanged"] or not report["resource_check_passed"]:
        report["status"] = "stopped"
        report["stop_reason"] = report["stop_reason"] or "source_or_resource_contract_failed"
    # Invented answer records are retained; real corpus payloads can never enter this runner.
    write_receipt(REPORT, report)
    print(json.dumps({key: report[key] for key in (
        "status", "stop_reason", "resource_check_passed", "source_unchanged",
        "controller_wall_seconds", "summary", "promotion")}, indent=2))
    return 0 if report["status"] == "complete_invented_comparison" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--version", choices=("v1", "v2", "verifier", "stress", "linked", "fields"), default="v1")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute required for the single frozen local-model experiment")
    select_version(args.version)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
