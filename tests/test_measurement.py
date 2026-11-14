from dataclasses import replace
from datetime import UTC, datetime

import pytest

from asof.measurement import MeasurementCase, score_measurement, validate_measurement_splits


def _case(name, gold_labels, prediction, **overrides):
    args = {
        "case_id": name, "issuer_id": name, "split": "test",
        "knowledge_time": datetime(2022, 1, 1, tzinfo=UTC),
        "gold": frozenset(gold_labels), "prediction": None if prediction is None else frozenset(prediction),
        "gold_refs": ("synthetic_adjudication",), "prediction_refs": ("synthetic_quote",),
        "gold_verified": True, "gold_complete": True,
        "abstention_reason": "no_supported_claim" if prediction is None else None,
    }
    args.update(overrides)
    return MeasurementCase(**args)


def test_abstentions_reduce_recall_and_coverage_instead_of_becoming_negative_labels():
    cases = [_case("A", ["a"], ["a"]), _case("B", ["b"], None),
             _case("C", [], ["c"]), _case("D", [], None)]
    result = score_measurement(cases)
    assert (result.true_positive, result.false_positive, result.false_negative) == (1, 1, 1)
    assert result.precision == result.recall == result.prediction_coverage == 0.5
    assert result.exact_match_accuracy == 0.25
    assert result.selective_exact_match_accuracy == 0.5
    assert result.scored_abstentions == 2


def test_unknown_and_partial_gold_are_not_silent_negatives_or_accuracy_denominators():
    unknown = _case("A", [], ["a"], gold=None, gold_verified=False,
                    gold_complete=False, gold_reason="no_independent_gold")
    partial = _case("B", ["b"], ["b"], gold_complete=False)
    unverified = _case("C", ["c"], ["c"], gold_verified=False)
    result = score_measurement([unknown, partial, unverified])
    assert result.scored_cases == 0 and result.cases == 3
    assert (result.gold_unknown_cases, result.gold_incomplete_cases, result.gold_unverified_cases) == (1, 1, 1)
    assert result.precision is result.recall is result.exact_match_accuracy is None
    empty = score_measurement([_case("D", [], [])])
    assert empty.exact_match_accuracy == 1 and empty.precision is None


def test_issuer_and_time_split_leaks_and_duplicate_cases_fail_explicitly():
    bounds = {"train_end": datetime(2020, 1, 1, tzinfo=UTC),
              "validation_end": datetime(2021, 1, 1, tzinfo=UTC),
              "test_end": datetime(2023, 1, 1, tzinfo=UTC)}
    train = _case("A", [], [], split="train", knowledge_time=datetime(2019, 1, 1, tzinfo=UTC))
    test = _case("B", [], [])
    validate_measurement_splits([train, test], **bounds)
    with pytest.raises(ValueError, match="across"):
        validate_measurement_splits([train, replace(test, issuer_id="A")], **bounds)
    with pytest.raises(ValueError, match="chronological"):
        validate_measurement_splits([replace(train, knowledge_time=bounds["train_end"])], **bounds)
    with pytest.raises(ValueError, match="duplicate"):
        score_measurement([test, test])


def test_evidence_and_abstention_metadata_are_not_optional_success_fallbacks():
    positive = _case("A", ["a"], ["a"])
    with pytest.raises(ValueError, match="predicted"):
        score_measurement([replace(positive, prediction_refs=())])
    with pytest.raises(ValueError, match="gold"):
        score_measurement([replace(positive, gold_refs=())])
    with pytest.raises(ValueError, match="abstention"):
        score_measurement([replace(positive, prediction=None)])
