import json

from asof.focused_reader import Answer, Case, abstention
from asof.reader_ai_review import ReviewTask
from asof.reader_ai_review_v3 import Probe
from asof.review_pipeline_v2 import (
    account_attempts,
    ai_verdict,
    disclosure_messages,
    finish_entry,
    first_step,
    next_step,
    record_step,
    request,
    start_entry,
    summarize,
)

PROSE = ("FictionTest's annual report gives revenue for 2021 of GBP 640 million on page 4 and "
         "GBP 655 million on page 38.")
TABLE = "Company: FictionTest.\n| Item | 2020 (GBP million) | 2021 (GBP million) |\n| Revenue | 600 | 640 |"


def _probe(identifier, source, candidate, expected):
    case = Case(identifier, "evaluation", "unit", "FictionTest", "revenue", "2021", source, None, None)
    return Probe(ReviewTask(case, candidate, expected), "stated", None, "unit")


def _answer(value, source=PROSE):
    return Answer(value=value, unit="GBP million", period="2021", evidence=source, abstain=False, reason="")


VALUE_OK = json.dumps({"verdict": "supported", "issues": [], "citations": ["E1"]})
VALUE_NO = json.dumps({"verdict": "unsupported", "issues": ["value"], "citations": ["E1"]})


def _disclosure(answer):
    return json.dumps({"answer": answer, "citations": ["E1"] if answer in ("stated", "conflicting") else []})


def test_support_needs_value_check_and_an_agreeing_single_amount_disclosure():
    task = _probe("A", PROSE, _answer("655"), "unsupported").task
    assert first_step(task) == "value"
    first = [record_step(task, "value", VALUE_OK)]
    assert next_step(task, first) == "disclosure"
    for answer, verdict in (("stated", "supported"), ("conflicting", "unsupported"),
                            ("not_stated", "unsupported"), ("cannot_tell", "uncertain")):
        rows = [*first, record_step(task, "disclosure", _disclosure(answer))]
        assert ai_verdict(task, rows)[0] == verdict
    assert ai_verdict(task, first)[0] == "uncertain"
    rejected = [record_step(task, "value", VALUE_NO)]
    assert next_step(task, rejected) is None and ai_verdict(task, rejected)[0] == "unsupported"


def test_abstentions_use_only_the_revised_disclosure_question_and_fixed_mapping():
    task = _probe("B", PROSE, abstention("no_answer_given"), "supported").task
    assert first_step(task) == "disclosure"
    prompt = disclosure_messages(task)[0]["content"]
    assert "supersedes" in prompt and "forecasts" in prompt and "conflicting" in prompt
    assert "candidate" not in disclosure_messages(task)[1]["content"]
    row = [record_step(task, "disclosure", _disclosure("conflicting"))]
    assert next_step(task, row) is None and ai_verdict(task, row)[0] == "supported"
    assert not record_step(task, "disclosure", json.dumps({"answer": "stated", "citations": []}))["valid"]
    assert not record_step(task, "disclosure", json.dumps({"answer": "stated", "citations": ["E9"]}))["valid"]
    assert request(task, "value")["wire"] == "value_check"


def test_rules_decide_first_without_model_calls_and_summary_keeps_all_denominators():
    ruled = _probe("C", TABLE, _answer("640", TABLE), "supported")
    deferred = _probe("D", PROSE, _answer("655"), "unsupported")
    assert start_entry(ruled)["decided_by"] == "rules" and start_entry(deferred)["decided_by"] is None
    entry = start_entry(deferred)
    entry["ai_steps"] = [record_step(deferred.task, "value", VALUE_OK),
                         record_step(deferred.task, "disclosure", _disclosure("conflicting"))]
    records = {"C": {"pipeline_v2": finish_entry(ruled, start_entry(ruled))},
               "D": {"pipeline_v2": finish_entry(deferred, entry)}}
    report = summarize((ruled, deferred), records)
    assert report["pipeline"]["correct_verdicts"] == 2 and report["pipeline"]["false_support"] == 0
    assert report["ablation_value_check_alone_on_deferred_answered"]["false_support"] == 1
    assert report["decided_by"] == {"rules": 1, "ai_fallback": 1} and report["ai_calls_recorded"] == 2
    assert not report["promote"] and report["human_gold_labels"] == 0


def test_started_but_unrecorded_calls_become_invalid_steps_and_never_support():
    deferred = _probe("D", PROSE, _answer("655"), "unsupported")
    calls = [{"call_id": 1, "case_id": "D", "status": "started", "wire_contract": "value_check"}]
    records = account_attempts((deferred,), {}, calls)
    report = summarize((deferred,), records)
    assert report["pipeline"]["uncertain_or_invalid"] == 1 and report["pipeline"]["false_support"] == 0
