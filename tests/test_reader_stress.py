import json
from pathlib import Path

import pytest

from asof.focused_reader import Answer, score
from asof.reader_stress import FAMILIES, audit_cases, build_fixture, model_summary


def fixture():
    return build_fixture(json.loads(
        (Path(__file__).parent / "fixtures" / "reader_stress.json").read_text()))


def test_stress_fixture_is_balanced_and_sampling_is_outcome_independent():
    data = fixture()
    assert len(data["pairs"]) == 144
    assert len({case.id for pair in data["pairs"] for case in pair["cases"]}) == 288
    selected = audit_cases(data)
    assert len(selected) == 24 and len({case.category for case in selected}) == 12
    assert all(sum(case.category == name for case in selected) == 2 for name in FAMILIES)
    original_ids = [case.id for case in selected]
    for pair in data["pairs"]:
        pair["relation"] = "tampered-without-changing-inputs"
    assert [case.id for case in audit_cases(data)] == original_ids


def test_tuple_diagnostic_exposes_contract_limit_without_regrading_primary_score():
    cases = audit_cases(fixture())
    case = next(c for c in cases if c.category == "parentheses_negative" and c.id.endswith("-1"))
    value, unit, period = case.expected
    answer = Answer(value=value, unit=unit, period=period, evidence=case.source,
                    abstain=False, reason="")
    primary = score(case, answer)
    assert not primary["correct"] and "value_not_in_evidence" in primary["grounding"]
    record = {case.id: {"single_pass": {"answer": answer.model_dump(), "score": primary}}}
    result = model_summary(cases, record)["stress_formats"]["single_pass"]
    assert result["contract_correct"] == 0
    assert result["tuple_correct_without_evidence_requirement"] == 1
    assert result["recorded"] == 1 and result["outcomes"]["not_attempted"] == 11


def test_definition_changes_refuse_a_different_unapproved_allocation():
    with pytest.raises(ValueError, match="frozen 288/24"):
        build_fixture({"seed": 7, "replicates_per_family": 12, "model_pairs_per_family": 1})
