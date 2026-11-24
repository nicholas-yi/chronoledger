import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from asof.focused_reader import (
    Answer,
    Case,
    CompactCritique,
    Critique,
    abstention,
    account_incomplete_attempts,
    choose_final,
    development_lessons,
    grounded,
    messages,
    parser_answer,
    promotion_gate,
    score,
    summarize,
    verified_error_bank,
)


def cases():
    payload = json.loads((Path(__file__).parent / "fixtures" / "focused_reader.json").read_text())
    return [Case(**{**row, "split": split,
                    "expected": tuple(row["expected"]) if row["expected"] else None})
            for split, rows in payload.items() for row in rows]


def test_task_parser_source_evidence_and_unanswerable_truth_are_distinct():
    values = cases()
    assert score(values[0], parser_answer(values[0]))["correct"]
    assert parser_answer(values[5]).abstain  # unresolved conflict, not choose-first
    assert parser_answer(values[6]).abstain  # wording outside the narrow parser grammar
    assert not score(values[6], parser_answer(values[6]))["correct"]
    misleading = Answer.model_validate(values[2].probe)
    assert grounded(values[2], misleading) == ()
    assert not score(values[2], misleading)["correct"]  # industry number passes token checks
    assert all(not score(case, Answer.model_validate(case.probe))["correct"] for case in values[:6])


def test_missing_or_invalid_responses_are_not_converted_to_successful_abstentions():
    case = cases()[-1]
    with pytest.raises(ValidationError):
        Answer.model_validate_json('{"abstain":true}')
    assert not score(case, None)["correct"]
    assert score(case, abstention("missing_metric"))["correct"]
    summary = summarize(cases(), {})
    assert summary["evaluation"]["single_pass"]["recorded_cases"] == 0
    assert summary["evaluation"]["single_pass"]["accuracy_all_planned"] == 0


def test_grounding_rejects_bad_quote_period_units_and_does_not_consult_gold_for_rollback():
    case = cases()[0]
    initial = parser_answer(case)
    for fields in ({"evidence": "not in source"}, {"unit": "EUR million"},
                   {"period": "2015"}, {"value": "999"}):
        bad = initial.model_copy(update=fields)
        assert grounded(case, bad)
        selected, reason = choose_final(case, initial, bad)
        assert selected == initial and reason == "retained_initial_no_verified_revision"
    # Wrong year/value association can pass necessary checks: do NOT silently use gold to undo it.
    plausible_wrong = Answer.model_validate(case.probe)
    chosen, _ = choose_final(case, initial, plausible_wrong)
    assert chosen == plausible_wrong and not score(case, chosen)["correct"]
    assert choose_final(case, None, None)[0].abstain


def test_model_messages_exclude_gold_probe_and_split_and_critic_errors_are_explicit():
    case = cases()[0]
    for stage in ("generate", "judge", "revise"):
        payload = json.loads(messages(case, stage, draft="{}", critique="{}")[-1]["content"])
        assert not {"expected", "probe", "split", "category"} & payload.keys()
    with pytest.raises(ValidationError):
        Critique(verdict="accept", issues=["wrong_unit"], feedback="fix")
    with pytest.raises(ValidationError):
        Critique(verdict="revise", issues=[], feedback="")
    with pytest.raises(ValueError, match="actual draft"):
        messages(case, "judge")


def test_error_bank_and_adaptation_cannot_consume_evaluation_or_judge_pseudo_gold():
    values = cases()
    records = {case.id: {"single_pass": {"answer": None, "score": score(case, None)}}
               for case in values}
    errors = verified_error_bank(values, records)
    assert len(errors) == 6 and all(item["case_id"].startswith("D") for item in errors)
    lessons = development_lessons(errors)
    assert len(lessons) == 6
    with pytest.raises(ValueError, match="machine-verified"):
        development_lessons([{**errors[0], "verifier": "model_judge"}])
    with pytest.raises(ValueError, match="machine-verified"):
        development_lessons([{**errors[0], "case_id": "E01"}])
    assert not promotion_gate(values, records, independent_audit=True)["promote"]
    assert development_lessons([]) == ()


def test_stopped_attempts_are_not_reported_as_never_attempted_or_zero_cost():
    values = cases()
    records = account_incomplete_attempts(values, {}, [
        {"case_id": "E01", "stage": "generate"}, {"case_id": "E01", "stage": "judge"}])
    assert records["E01"]["single_pass"]["score"]["outcome"] == "invalid_response"
    assert records["E01"]["judge_assisted"]["answer"] is None
    result = summarize(values, records)["evaluation"]["judge_assisted"]
    assert result["recorded_cases"] == result["missing_latency_records"] == 1
    assert result["outcomes"] == {"invalid_response": 1, "not_attempted": 5}


def test_compact_critic_cannot_emit_freeform_feedback_or_unbounded_codes():
    raw = CompactCritique(verdict="revise", issues=["wrong_period", "wrong_unit"])
    expanded = raw.expanded()
    assert expanded.issues == ["wrong_period", "wrong_unit"]
    assert "reporting year" in expanded.feedback and "currency" in expanded.feedback
    assert CompactCritique(verdict="accept", issues=[]).expanded().feedback == ""
    for data in (
        {"verdict": "accept", "issues": [], "feedback": "unbounded prose"},
        {"verdict": "revise", "issues": []},
        {"verdict": "accept", "issues": ["wrong_value"]},
        {"verdict": "revise", "issues": ["invented_code"]},
        {"verdict": "revise", "issues": ["wrong_value"] * 2},
        {"verdict": "revise", "issues": ["wrong_value", "wrong_unit", "missing", "ambiguous"]},
    ):
        with pytest.raises(ValidationError):
            CompactCritique.model_validate(data)
    schema = CompactCritique.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["issues"]["maxItems"] == 3


