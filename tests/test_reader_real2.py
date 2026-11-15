import asyncio
import importlib.util
import json
import time
from pathlib import Path

import httpx
import pytest

from asof.benchmark_baseline import TableInput
from asof.reader_real2_guards import SustainedCPU, input_fit, truncation_reason
from asof.reader_real_report import ARMS


def script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1]/"scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("run_reader_real2", scripts/"run_reader_real2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cpu_uses_weighted_full_window_and_ignores_brief_spikes():
    trace = SustainedCPU()
    trace.activate()
    assert not trace.add(0, 20, 0, "toy")
    assert trace.trace[-1]["rolling_60second_mean_percent"] is None
    assert not trace.add(20, 60, 100, "toy")
    assert trace.trace[-1]["rolling_60second_mean_percent"] == pytest.approx(200/3)
    for second in range(60, 200):
        assert not trace.add(second, second+1, 100 if second%60 in (0, 1) else 30, "toy")


def test_sustained_guard_requires_exact_elapsed_duration_and_resets_at_threshold():
    trace = SustainedCPU()
    trace.activate()
    for second in range(179):
        assert not trace.add(second, second+1, 100, "toy")
    assert trace.add(179, 180, 100, "toy")
    assert trace.max_high_seconds == 120
    threshold = SustainedCPU()
    threshold.activate()
    for second in range(200):
        assert not threshold.add(second, second+1, 95, "toy")
    waiting = SustainedCPU()
    for second in range(240):
        assert not waiting.add(second, second+1, 100, "toy")
    waiting.activate()
    assert not waiting.add(240, 241, 100, "toy")


def test_fit_and_postcall_bounds_do_not_accept_truncated_answers():
    options = {"num_ctx": 16384, "num_predict": 512}
    assert input_fit(b"x"*46848, options) == (15616, 15616, True)
    assert input_fit(b"x"*46849, options) == (15617, 15616, False)
    good = {"prompt_eval_count": 15871, "eval_count": 50, "done_reason": "stop"}
    assert truncation_reason(good, options) is None
    assert truncation_reason(dict(good, prompt_eval_count=15872), options)
    assert truncation_reason(dict(good, prompt_eval_count=None), options)
    assert truncation_reason(dict(good, done_reason="length"), options)
    assert truncation_reason(good, options, log_sign=True)
    assert truncation_reason(dict(good, message={"truncated": True}), options)


def test_real2_continues_timeout_but_never_scores_a_truncated_response(monkeypatch, tmp_path):
    module = script(monkeypatch)
    monkeypatch.setattr(module, "PRIVATE", tmp_path)
    log = tmp_path/"server.log"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "SERVER_LOG", log)
    options = {"num_ctx": 16384, "num_predict": 512}
    item = TableInput("Toy?", (("toy", "7"),), ())
    template = module.real_body(item, ARMS[0], options)
    config = {"options": options, "system_prompt": template["messages"][0]["content"],
              "schema": template["format"], "orders": [
                  {"id": "one", "arms": list(ARMS)}, {"id": "two", "arms": list(ARMS)}]}
    rows = [{"id": uid, **{a: {"outcome": "not_attempted", "attempted": False} for a in ARMS}}
            for uid in ("one", "two")]
    inputs = {"one": item, "two": item}
    predictions = {uid: {a: (None, "") for a in ARMS} for uid in inputs}
    calls = []

    class Client:
        async def post(self, *args, **kwargs):
            calls.append(1)
            if len(calls)==1:
                raise httpx.ReadTimeout("toy")
            prompt = 15872 if len(calls)==2 else 20
            return httpx.Response(200, request=httpx.Request("POST", "http://local/api/chat"),
                json={"done": True, "done_reason": "stop", "prompt_eval_count": prompt,
                      "eval_count": 30, "message": {"content": json.dumps({
                          "answer": 7, "scale": "", "evidence": [], "abstain": False})}})

    async def run():
        watch = asyncio.create_task(asyncio.sleep(1000))
        try:
            return await module.generate(config, rows, inputs, Client(), watch,
                                         time.monotonic(), predictions, lambda: None)
        finally:
            watch.cancel()
            await asyncio.gather(watch, return_exceptions=True)

    assert asyncio.run(run()) is None
    assert len(calls)==4
    assert rows[0][ARMS[0]]["timeout"]
    assert rows[0][ARMS[1]]["truncated_or_invalid"]
    assert predictions["one"][ARMS[1]] == (None, "")
    assert predictions["two"][ARMS[0]] == (7, "")


def test_launch_wait_rechecks_without_generating_and_stops_at_ten_minutes(monkeypatch):
    module = script(monkeypatch)
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    class Recorder:
        def __init__(self, value):
            self.policy = SustainedCPU()
            self.value = value

        async def sample(self):
            start = clock[0]
            clock[0] += 1
            value = self.value(clock[0])
            return self.policy.add(start, clock[0], value, "toy")

    recorder = Recorder(lambda second: 80 if second < 4 else 50)
    assert asyncio.run(module.wait_for_launch(recorder, 0)) == 60
    assert recorder.policy.active
    clock[0] = 0
    high = Recorder(lambda _: 70)
    with pytest.raises(module.ResourceStop, match="10minutes"):
        asyncio.run(module.wait_for_launch(high, 0))
    assert not high.policy.active
