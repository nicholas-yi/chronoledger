import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from asof.focused_reader import Answer, Case, parser_answer, score
from asof.verified_reader import (
    binding_parser,
    load_robustness_cases,
    summarize_robustness,
    verify_response,
)


def cases():
    return load_robustness_cases(json.loads(
        (Path(__file__).parent / "fixtures" / "verified_reader.json").read_text()))


def test_missing_unit_is_recovered_only_from_unique_quoted_binding_without_changing_other_fields():
    case = cases()[18]  # Natural subscribers wording, not the narrow baseline grammar.
    content = json.dumps({
        "value": "3700", "unit": "", "period": "2017", "evidence": case.source,
        "abstain": False, "reason": "",
    })
    result = verify_response(case, content)
    assert result.status == "repaired_blank_unit"
    assert result.answer.unit == "subscribers"
    assert result.answer.value == "3700" and result.answer.period == "2017"
    assert score(case, result.answer)["correct"]
    assert not score(case, parser_answer(case))["correct"]
    assert score(case, binding_parser(case))["correct"]  # Fair stronger-parser control.


def test_ambiguous_units_wrong_explicit_units_periods_values_and_quotes_are_never_repaired():
    original = cases()[20]
    data = {"value": "6", "unit": "", "period": "2017", "evidence": original.source,
            "abstain": False, "reason": ""}
    ambiguous = cases()[21]
    result = verify_response(ambiguous, json.dumps({**data, "evidence": ambiguous.source}))
    assert result.answer.abstain and result.status == "rejected"
    for changed in (
        {"unit": "EUR million"}, {"period": "2016"}, {"value": "99"},
        {"evidence": "invented quote"},
    ):
        result = verify_response(original, json.dumps({**data, **changed}))
        assert result.status == "rejected" and result.answer.abstain
    result = verify_response(original, json.dumps({**data, "value": 6}))
    assert result.answer is None and result.status == "invalid_response"


def test_no_gold_used_by_verifier_and_unsupported_language_remains_unavailable():
    case = Case("X", "evaluation", "test", "Fiction", "revenue", "2017",
                "Fiction discussed industry revenue of 9 USD million for 2017.", None)
    content = json.dumps({"value": "9", "unit": "", "period": "2017", "evidence": case.source,
                          "abstain": False, "reason": ""})
    assert verify_response(case, content).answer.abstain
    first = cases()[0]
    correct = binding_parser(first)
    supplied = Case(**{**first.__dict__, "expected": None})
    assert verify_response(first, correct.model_dump_json()) == verify_response(
        supplied, correct.model_dump_json())
    with pytest.raises(ValidationError):
        Answer.model_validate_json(content)


def test_authored_transformations_have_explicit_oracles_and_pair_metrics_do_not_hide_wrong_invariance():
    values = cases()
    fixture = json.loads((Path(__file__).parent / "fixtures" / "verified_reader.json").read_text())
    assert len(values) == 24
    # This fixture intentionally shares the finite supported binding grammar; not independent gold.
    assert all(score(case, binding_parser(case))["correct"] for case in values)
    records = {case.id: {"binding_parser": {
        "answer": binding_parser(case).model_dump(), "score": score(case, binding_parser(case))}}
               for case in values}
    summary = summarize_robustness(values, records, fixture)
    assert summary["arms"]["binding_parser"]["pairs"]["both_correct"] == 12
    assert summary["arms"]["single_pass"]["recorded"] == 0
    assert not summary["promote"] and not summary["independent_gold"]
