import asyncio
import importlib.util
import time
from pathlib import Path

import httpx
import pytest
from scipy.stats import binomtest

from asof.benchmark_baseline import TableInput
from asof.reader_positive_control import SyntheticCase, control_body
from asof.reader_real_report import ARMS, contrast, exact_mcnemar, report


def script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("run_reader_real1", scripts / "run_reader_real1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_denominators_pairing_and_empty_answer_type_are_not_silent_zeroes():
    rows = []
    for i in range(30):
        rows.append({"id": str(i), "answer_type": "span", **{
            a: {"native_EM": 0, "native_F1": 0, "native_scale_accuracy": 0,
                "outcome": "not_attempted", "attempted": False} for a in ARMS
        }})
    for i in range(8):
        rows[i][ARMS[0]].update(native_EM=1, native_F1=1, native_scale_accuracy=1,
                                outcome="correct", attempted=True, response_received=True,
                                generation_finished=True)
        rows[i][ARMS[1]].update(outcome="abstain", attempted=True,
                                response_received=True, generation_finished=True)
    rows[8][ARMS[1]].update(native_EM=1, native_F1=1, outcome="correct", attempted=True)
    rows[9][ARMS[0]].update(outcome="wrong", native_F1=0.5, attempted=True)
    result = report(rows)
    assert result["arms"][ARMS[0]]["n"] == 30
    assert result["arms"][ARMS[0]]["native_EM"] == 8/30
    assert result["arms"][ARMS[0]]["native_F1"] == 8.5/30
    assert result["arms"][ARMS[0]]["coverage"] == 9/30
    assert result["paired_all_selected"]["right_only_with_report"] == 8
    assert result["paired_all_selected"]["right_only_without_report"] == 1
    assert result["completed_pairs"]["both_predictions_valid"] == 8
    assert result["by_answer_type"]["count"][ARMS[0]]["native_EM"] is None
    assert result["by_answer_type"]["count"][ARMS[0]]["EM_Wilson95"] is None
    assert contrast([])["exact_McNemar_p_descriptive"] is None
    assert exact_mcnemar(8, 1) == pytest.approx(binomtest(8, 9, 0.5).pvalue)


def test_pc1_prompt_schema_and_parse_inputs_are_exact_with_no_gold(monkeypatch):
    module = script(monkeypatch)
    item = TableInput("Invented question?", (("toy", "7"),), ("Synthetic paragraph.",))
    original = control_body(SyntheticCase("toy", "toy", item, "PRIVATE_GOLD"),
                            "answer_first", model=module.MODEL, options={"num_ctx": 16384})
    assert module.real_body(item, ARMS[0], {"num_ctx": 16384}) == original
    missing = module.real_body(item, ARMS[1], {"num_ctx": 16384})
    assert missing["messages"][0] == original["messages"][0]
    assert missing["format"] == original["format"]
    assert "Synthetic paragraph" not in missing["messages"][1]["content"]
    assert "PRIVATE_GOLD" not in str(original)


def test_single_timeouts_continue_and_only_three_consecutive_calls_stop(monkeypatch, tmp_path):
    module = script(monkeypatch)
    monkeypatch.setattr(module, "PRIVATE", tmp_path)
    ids = ["one", "two", "three", "four", "five"]
    inputs = {uid: TableInput("Toy?", (), ()) for uid in ids}
    rows = [{"id": uid, **{a: {"outcome": "not_attempted", "attempted": False} for a in ARMS}}
            for uid in ids]
    body = module.real_body(inputs["one"], ARMS[0], {})
    config = {"orders": [{"id": uid, "arms": list(ARMS)} for uid in ids],
              "options": {}, "system_prompt": body["messages"][0]["content"],
              "schema": body["format"], "limits": {"serialized_request_bytes": 12000}}
    predictions = {uid: {a: (None, "") for a in ARMS} for uid in ids}
    sequence = [True, False, True, True, False, True, True, True]
    calls = []

    class Client:
        async def post(self, path, **kwargs):
            timeout = sequence[len(calls)]
            calls.append(path)
            if timeout:
                raise httpx.ReadTimeout("synthetic timeout")
            return httpx.Response(200, request=httpx.Request("POST", "http://local/api/chat"),
                json={"done": True, "done_reason": "stop", "message": {
                    "content": '{"answer":null,"scale":"","evidence":[],"abstain":true}'}})

    async def run():
        watch = asyncio.create_task(asyncio.sleep(1000))
        try:
            return await module.generate(config, rows, inputs, Client(), watch,
                                         time.monotonic(), predictions, lambda: None)
        finally:
            watch.cancel()
            await asyncio.gather(watch, return_exceptions=True)

    assert asyncio.run(run()) == "three_consecutive_call_timeouts"
    assert len(calls) == 8
    assert rows[0][ARMS[0]]["timeout"] is True
    assert rows[0][ARMS[1]]["outcome"] == "abstain"
    assert not rows[4][ARMS[0]]["attempted"]
    assert rows[3][ARMS[1]]["consecutive_call_timeouts"] == 3


def test_native_zero_adapter_and_gold_only_after_generation(monkeypatch):
    module = script(monkeypatch)
    finished = False

    class Gold(dict):
        def __getitem__(self, key):
            assert finished, "gold accessed before prediction phase completed"
            return super().__getitem__(key)

    class Metric:
        def __call__(self, ground_truth, prediction, pred_scale):
            assert ground_truth["answer"] == "0"
            assert prediction == "0"

        def get_overall_metric(self):
            return 1, 1, 1, 0

    rows = [{"id": "zero", **{a: {"outcome": "answered"} for a in ARMS}}]
    gold = {"zero": Gold(answer="0", answer_type="count")}
    predictions = {"zero": {a: (0, "") for a in ARMS}}
    finished = True
    module.score_rows(rows, gold, predictions, Metric)
    assert rows[0][ARMS[0]]["outcome"] == "correct"
    assert rows[0]["answer_type"] == "count"
