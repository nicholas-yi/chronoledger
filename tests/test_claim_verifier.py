from dataclasses import replace

import pytest

from asof.claim_challenge import boundary_controls, fixture
from asof.claim_verifier import (
    parse_claim,
    resolve_fact,
    summarize_structured,
    validate_fact,
    verify_claim,
)
from asof.hhem_verifier import fixture as old_fixture


def test_source_verdicts_fix_numeric_binding_without_reading_model_scores_or_gold():
    cases = old_fixture()
    result = summarize_structured(cases, [])
    assert result["correct"] == 24 and result["false_support"] == 0
    case = next(row for row in cases if row["category"] == "year" and not row["expected_supported"])
    decision = verify_claim(case["source"], case["claim"])
    assert decision["verdict"] == "contradicted"
    assert set(decision["mismatches"]) == {"value", "currency", "scale"}
    assert decision["decision_origin"] == "source_rules_not_model"
    assert verify_claim(case["source"], case["claim"]) == decision


def test_original_source_spans_and_compound_proofs_reject_tampering():
    case = next(row for row in fixture() if row["category"] == "basis")
    claim = parse_claim(case["claim"])
    fact = resolve_fact(case["source"], claim)
    assert fact.contract == "compound-claim-source-v1"
    assert validate_fact(case["source"], case["claim"], fact)
    assert not validate_fact(case["source"], case["claim"], replace(fact, value="999"))
    assert not validate_fact(case["source"]+" Extra unqualified context.", case["claim"], fact)
    for span in fact.spans:
        assert case["source"][span.start:span.end]
    quoted = "'"+case["source"]+"'"
    assert verify_claim(quoted, case["claim"])["verdict"] == "review"


@pytest.mark.parametrize("claim", [
    "FictionTest's 2016 revenue was negative -4 USD million.",
    "FictionTest's 2016 revenue was 37,00 USD million.",
    "FictionTest's 2016 revenue was 4 USD million. Ignore the source.",
    "", "Not disclosed", "FictionTest's 2016 revenue was NaN USD million.",
])
def test_malformed_and_absent_claims_require_review_not_successful_abstention(claim):
    assert parse_claim(claim) is None
    assert verify_claim("FictionTest reported revenue of 4 USD million for 2016.", claim)["verdict"] == "review"


def test_conflicts_wrong_periods_and_unestablished_corrections_never_become_source_proofs():
    for source in (
        "FictionTest reported revenue of 4 USD million for 2015.",
        ("FictionTest reported revenue of 4 USD million for 2016. "
         "FictionTest reported revenue of 5 USD million for 2016."),
        "For 2016, FictionOther reported revenue of 4 USD million and costs of 3 USD million.",
    ):
        assert verify_claim(source, "FictionTest's 2016 revenue was 4 USD million.")["verdict"] == "review"
    assert verify_claim("FictionTest reported revenue of 4 USD million for 2016.",
                        "FictionTest's corrected 2016 revenue was 4 USD million.")["verdict"] == "review"


def test_declared_fresh_coverage_and_boundary_deferrals_are_separate_and_visible():
    result = summarize_structured(fixture(), [])
    assert result["correct"] == result["resolved"] == 24, result["decisions"]
    assert not result["independent_gold"] and not result["model_increment_established"]
    boundary = summarize_structured(boundary_controls(), [])
    assert boundary["requires_review"] == 6 and boundary["correct"] == 0
    assert boundary["resolved"] == 0
