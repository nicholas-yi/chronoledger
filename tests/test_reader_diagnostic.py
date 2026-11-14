import importlib.util
import json
import random
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from asof.benchmark_baseline import TableInput
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid, request_body

ITEM = TableInput("What is the toy amount?", (("label", "value"), ("toy", "7")),
                  ("The toy value is seven.",))


def test_context_withholding_uses_same_question_without_report_or_gold():
    options = {"num_thread": 1, "num_gpu": 0}
    grounded = request_body(ITEM, model="toy", supplied_context=True, options=options)
    empty = request_body(ITEM, model="toy", supplied_context=False, options=options)
    assert grounded["messages"][0] == empty["messages"][0]
    visible = json.loads(empty["messages"][1]["content"])
    assert visible["question"] == ITEM.question
    assert "table" not in visible and "paragraphs" not in visible
    assert "The toy value" not in json.dumps(empty["messages"])
    assert grounded["options"] == options and grounded["think"] is False


def test_strict_answers_do_not_turn_malformed_output_into_abstention():
    for raw in (
        {"abstain": False, "answer": None, "scale": "", "evidence": []},
        {"abstain": True, "answer": 7, "scale": "", "evidence": []},
        {"abstain": False, "answer": True, "scale": "", "evidence": []},
    ):
        with pytest.raises(ValidationError):
            ReaderAnswer.model_validate(raw)


def test_citation_locations_and_quotes_are_checked_but_not_claimed_as_answer_proof():
    good = ReaderAnswer.model_validate({
        "abstain": False, "answer": 999, "scale": "",
        "evidence": [{"source": "table", "row": 1, "column": 1}],
    })
    # A real location can still fail to support the asserted answer.
    assert references_locally_valid(good, ITEM, supplied_context=True) is True
    assert references_locally_valid(good, ITEM, supplied_context=False) is False
    bad = good.model_copy(update={"evidence": [
        good.evidence[0].model_copy(update={"row": 99}),
    ]})
    assert references_locally_valid(bad, ITEM, supplied_context=True) is False
    quote = ReaderAnswer.model_validate({
        "abstain": False, "answer": "seven", "scale": "",
        "evidence": [{"source": "paragraph", "paragraph": 0, "quote": "value is seven"}],
    })
    assert references_locally_valid(quote, ITEM, supplied_context=True) is True
    abstain = ReaderAnswer.model_validate({
        "abstain": True, "answer": None, "scale": "", "evidence": [],
    })
    assert references_locally_valid(abstain, ITEM, supplied_context=True) is None


def test_transport_failure_stops_calls_without_retry_and_keeps_all_selected_items(monkeypatch, tmp_path):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("run_reader_diagnostic", scripts / "run_reader_diagnostic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "assets"
    (root / "tatqa").mkdir(parents=True)
    questions = [
        {"uid": f"toy{i}", "question": "Toy amount?", "answer": "PRIVATE_GOLD"}
        for i in range(10)
    ]
    (root / "tatqa" / "dev.json").write_text(json.dumps([{
        "table": {"table": [["toy", "7"]]}, "paragraphs": [{"text": "PRIVATE_REPORT"}],
        "questions": questions,
    }]), encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "seed": module.SEED, "excluded_ids": [],
        "ids": random.Random(module.SEED).sample(sorted(q["uid"] for q in questions), 10),
        "assets": {}, "source_sha256": {}, "options": {},
        "limits": {"serialized_request_bytes": 12000},
        "model": {"name": module.MODEL, "digest": module.DIGEST, "ollama_version": "toy"},
    }), encoding="utf-8")

    class Metric:
        def __call__(self, **kwargs):
            pass

        def get_raw(self):
            return [{"em": 0, "f1": 0}]

        def get_overall_metric(self):
            return 0, 0, 0, 0

    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, path):
            data = ({"models": [{"name": module.MODEL, "digest": module.DIGEST}]}
                    if path == "/api/tags" else {"version": "toy"})
            return httpx.Response(200, json=data, request=httpx.Request("GET", module.ENDPOINT + path))

        def post(self, path, **kwargs):
            calls.append(kwargs["content"])
            raise httpx.ReadTimeout("PRIVATE_TRANSPORT_DETAIL")

    for key, value in {
        "ROOT": root, "CONFIG": config, "RECEIPT": tmp_path / "receipt.json",
        "PRIVATE": tmp_path / "private", "SOURCE_FILES": [],
    }.items():
        monkeypatch.setattr(module, key, value)
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(module.ledger, "lineage", lambda *args: {"git_dirty": False})
    monkeypatch.setattr(module, "verified_assets", dict)
    monkeypatch.setattr(module, "load_native", lambda *args: SimpleNamespace(TaTQAEmAndF1=Metric))
    monkeypatch.setattr(module.httpx, "Client", Client)
    module.run()
    result = json.loads(module.RECEIPT.read_text())
    assert result["generation_attempts"] == len(calls) == 1
    assert len(result["items"]) == 10 and result["status"] == "partial"
    assert "PRIVATE_GOLD" not in calls[0].decode()
    assert "PRIVATE" not in module.RECEIPT.read_text()
    assert result["summaries"]["grounded"]["native_EM"] == 0
