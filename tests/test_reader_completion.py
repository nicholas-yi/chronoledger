import asyncio
import copy
import importlib.util
import json
import time
from pathlib import Path

import httpx
import pytest

from asof.benchmark_baseline import TableInput
from asof.reader_completion import combine, completion_plan, effective_config
from asof.reader_real_report import ARMS


def fixture():
    ids = [f"toy{i}" for i in range(30)]
    base = {"ids": ids, "orders": [{"id": uid, "arms": list(ARMS)} for uid in ids],
            "limits": {"owned_process_tree_RSS_bytes": 6 << 30, "wall_seconds": 4500},
            "options": {"num_thread": 4}}
    rows = []
    for i, uid in enumerate(ids):
        row = {"id": uid, "answer_type": "span"}
        for arm in ARMS:
            finished = i < 10
            row[arm] = {"attempted": finished, "generation_finished": finished,
                        "outcome": "abstain" if finished else "not_attempted",
                        "native_EM": 0, "native_F1": 0, "native_scale_accuracy": 0}
        rows.append(row)
    rows[10][ARMS[0]].update(attempted=True, outcome="failed",
        reason="run_stopped:owned isolated process tree working set exceeds6GiB")
    original = {"items": rows, "generation_attempts": 21, "report": {"preserved": True}}
    return base, original


def test_forty_case_route_is_exact_original_order_and_protects_twenty():
    base, original = fixture()
    jobs, protected = completion_plan(base, original)
    assert len(jobs)==40 and len(protected)==20
    assert jobs[0]=={"id": "toy10", "arm": ARMS[0], "eligibility": "memory_cancelled"}
    assert jobs[1]=={"id": "toy10", "arm": ARMS[1], "eligibility": "never_attempted"}
    assert all(int(j["id"][3:])>=10 for j in jobs)
    invalid = copy.deepcopy(original)
    invalid["items"][0][ARMS[0]]["generation_finished"] = False
    with pytest.raises(ValueError):
        completion_plan(base, invalid)


def test_only_memory_changes_and_combination_preserves_original_case_records():
    base, original = fixture()
    before = copy.deepcopy(base)
    effective = effective_config(base)
    assert base==before
    assert effective["limits"]["owned_process_tree_RSS_bytes"]==10<<30
    effective["limits"]["owned_process_tree_RSS_bytes"]=6<<30
    assert effective==base
    jobs, _ = completion_plan(base, original)
    new_rows = copy.deepcopy(original["items"][10:])
    for row in new_rows:
        for arm in ARMS:
            row[arm].update(outcome="correct", attempted=True, generation_finished=True,
                            native_EM=1, native_F1=1, native_scale_accuracy=1)
    completion = {"status": "complete", "items": new_rows, "generation_attempts": 40}
    merged = combine(base, original, completion, jobs)
    assert merged["items"][0][ARMS[0]]==original["items"][0][ARMS[0]]
    assert merged["items"][0]["case_record_source"][ARMS[0]]=="REAL2"
    assert merged["items"][10]["case_record_source"][ARMS[0]]=="REAL2-C"
    assert merged["combined_report"]["arms"][ARMS[0]]["native_EM"]==20/30
    assert merged["attempt_accounting"]["total_generation_attempts"]==61
    assert merged["as_stopped_report"]==original["report"]
    with pytest.raises(ValueError):
        combine(base, original, completion, list(reversed(jobs)))


def test_completion_generation_sends_only_frozen_unfinished_cases(monkeypatch, tmp_path):
    scripts = Path(__file__).resolve().parents[1]/"scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "run_reader_real2_completion", scripts/"run_reader_real2_completion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "PRIVATE", tmp_path)
    log = tmp_path/"server.log"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "SERVER_LOG", log)
    base, original = fixture()
    jobs, _ = completion_plan(base, original)
    rows = [{"id": f"toy{i}", **{a: {"outcome": "not_attempted", "attempted": False} for a in ARMS}}
            for i in range(10, 30)]
    inputs = {r["id"]: TableInput(r["id"], (), ()) for r in rows}
    options = {"num_ctx": 16384, "num_predict": 512}
    template = module.real_body(inputs["toy10"], ARMS[0], options)
    config = {"options": options, "system_prompt": template["messages"][0]["content"],
              "schema": template["format"]}
    predictions = {r["id"]: {a: (None, "") for a in ARMS} for r in rows}
    questions = []

    class Client:
        async def post(self, path, **kwargs):
            questions.append(json.loads(kwargs["json"]["messages"][1]["content"])["question"])
            return httpx.Response(200, request=httpx.Request("POST", "http://local/api/chat"),
                json={"done": True, "done_reason": "stop", "prompt_eval_count": 20,
                      "eval_count": 24, "message": {
                          "content": '{"answer":null,"scale":"","evidence":[],"abstain":true}'}})

    async def run():
        watch = asyncio.create_task(asyncio.sleep(1000))
        try:
            return await module.generate(jobs, config, rows, inputs, Client(), watch,
                                         time.monotonic(), predictions, lambda: None, lambda: None)
        finally:
            watch.cancel()
            await asyncio.gather(watch, return_exceptions=True)

    assert asyncio.run(run()) is None
    assert questions==[j["id"] for j in jobs]
    assert len(questions)==40 and all(int(q[3:])>=10 for q in questions)


def test_sleep_clock_difference_stops_instead_of_resuming(monkeypatch):
    scripts = Path(__file__).resolve().parents[1]/"scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "completion_sleep", scripts/"run_reader_real2_completion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.WindowsCPU, "__init__", lambda self: None)
    monkeypatch.setattr(module.WindowsCPU, "percent", lambda self: 25.0)
    clocks = iter(((100.0, 100.0), (101.0, 101.0), (131.0, 102.0)))
    cpu = module.SleepAwareCPU(lambda: next(clocks))
    assert cpu.percent()==25.0
    with pytest.raises(module.ResourceStop, match="host_sleep_interruption"):
        cpu.percent()
    assert cpu.interruptions[0]["suspend_seconds_detected"]==29.0
