import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from asof.reader_ai_review import (
    Opinion,
    account_review_attempts,
    compact_cell_messages,
    review_messages,
    review_record,
    review_tasks,
    source_spans,
    summarize_reviews,
)
from asof.reader_cells import audit_fixture, cell_messages


def test_ai_review_is_separate_labelled_advice_and_cannot_mutate_candidate_or_human_gate():
    task = review_tasks()[0]
    original = task.candidate.model_dump()
    record = review_record(task.case, task.candidate, json.dumps({
        "verdict": "supported", "issues": [], "citations": ["E1"]}))
    assert record["valid"] and record["reviewer_type"] == "AI"
    assert not record["counts_as_independent_human"] and not record["creates_gold"]
    assert not record["candidate_changed"] and task.candidate.model_dump() == original
    for cited in record["source_citations"]:
        assert task.case.source[cited["start"]:cited["end"]] == cited["text"]
    changed = replace(task.case, expected=None)
    assert review_record(changed, task.candidate, json.dumps(record["opinion"])) == record
    assert review_messages(changed, task.candidate) == review_messages(task.case, task.candidate)


def test_unbounded_or_uncited_verdicts_and_foreign_spans_do_not_pass():
    task = review_tasks()[0]
    for raw in (
        {"verdict": "supported", "issues": [], "citations": []},
        {"verdict": "unsupported", "issues": [], "citations": ["E1"]},
        {"verdict": "supported", "issues": [], "citations": ["E1"], "confidence": 1},
        {"verdict": "unsupported", "issues": ["value", "value"], "citations": ["E1"]},
    ):
        with pytest.raises(ValidationError):
            Opinion.model_validate(raw)
        assert not review_record(task.case, task.candidate, json.dumps(raw))["valid"]
    assert not review_record(task.case, task.candidate, json.dumps({
        "verdict": "supported", "issues": [], "citations": ["E999"]}))["valid"]


def test_calibration_keeps_false_support_and_uncertainty_visible_without_creating_gold():
    tasks = review_tasks()
    assert len(tasks) == 12 and sum(task.expected_verdict == "supported" for task in tasks) == 6
    records = {task.case.id: {"ai_review": review_record(task.case, task.candidate, json.dumps({
        "verdict": "supported", "issues": [], "citations": [next(iter(source_spans(task.case)))],
    }))} for task in tasks}
    summary = summarize_reviews(tasks, records)
    assert summary["valid"] == 12 and summary["correct_verdicts"] == 6
    assert summary["false_support"] == 6
    assert summary["human_gold_labels"] == 0 and not summary["promote"]
    assert summarize_reviews(tasks, {})["recorded"] == 0


def test_compact_cell_inputs_retain_source_and_ids_but_reduce_redundant_proof_text():
    for case in audit_fixture()[0]:
        compact = compact_cell_messages(case)
        payload = json.loads(compact[1]["content"])
        assert payload["source"] == case.source and not {"expected", "split", "probe"} & payload.keys()
        assert len(json.dumps(compact)) < len(json.dumps(cell_messages(case)))


def test_interrupted_ai_attempt_is_an_invalid_ai_record_not_a_human_or_unattempted_pass():
    tasks = review_tasks()
    records = account_review_attempts(tasks, {}, [{
        "case_id": tasks[0].case.id, "call_id": 1, "wire_contract": "advisory_review",
        "status": "transport_or_HTTP_failure", "latency_seconds": 90,
    }])
    summary = summarize_reviews(tasks, records)
    assert summary["recorded"] == 1 and summary["valid"] == 0
    assert summary["human_gold_labels"] == 0
