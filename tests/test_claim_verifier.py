from dataclasses import replace
from decimal import localcontext

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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


def test_declared_fresh_coverage_and_formerly_deferred_boundaries_resolve_with_proofs():
    result = summarize_structured(fixture(), [])
    assert result["correct"] == result["resolved"] == 24, result["decisions"]
    assert not result["independent_gold"] and not result["model_increment_established"]
    boundary = summarize_structured(boundary_controls(), [])
    assert boundary["requires_review"] == 0 and boundary["correct"] == boundary["resolved"] == 6
    contracts = {row["source_fact"]["contract"] for row in boundary["decisions"].values()}
    assert contracts == {"financial-notation-v2", "compact-eps-claim-v1"}
    assert all(row["proof_valid"] for row in boundary["decisions"].values())


@pytest.mark.parametrize("source", [
    "FictionTest never actually reported revenue of 18 USD million for 2016.",
    "FictionTest did not actually report revenue of 18 USD million for 2016.",
    "FictionTest forecast revenue of 18 USD million for 2016.",
    "FictionTest would report revenue of 18 USD million for 2016.",
    "FictionTest expected revenue of 18 USD million for 2016.",
    ("FictionTest reported revenue of 18 USD million for 2016. "
     "This is an illustrative example, not an actual disclosure."),
    ("FictionTest reported revenue of 18 USD million for 2016.\n"
     "These figures are quarterly, not annual."),
    ("FictionTest reported revenue of 18 USD million for 2016.\n"
     "All amounts are forecasts, not actuals."),
])
def test_nonactual_negated_and_qualified_sources_do_not_prove_actual_annual_facts(source):
    claim = "FictionTest's 2016 revenue was 18 USD million."
    assert verify_claim(source, claim)["verdict"] == "review"


def test_an_unrelated_customer_forecast_does_not_destroy_a_supported_actual():
    source = ("FictionTest reported revenue of 18 USD million for 2016. "
              "Its customer may forecast lower costs.")
    assert verify_claim(source, "FictionTest's 2016 revenue was 18 USD million.")["verdict"] == "supported"


@settings(max_examples=40, derandomize=True, deadline=None)
@given(st.integers(min_value=-(10**40), max_value=10**40),
       st.sampled_from(("USD", "EUR", "GBP")))
def test_exact_denomination_equivalence_and_nearby_inequality_do_not_depend_on_decimal_precision(value, currency):
    source = f"FictionTest reported revenue of {value} {currency} million for 2016."
    exact = f"FictionTest's 2016 revenue was {value*1000} {currency} thousand."
    wrong = f"FictionTest's 2016 revenue was {value*1000+1} {currency} thousand."
    with localcontext() as context:
        context.prec = 2
        decision = verify_claim(source, exact)
        assert decision["verdict"] == "supported"
        assert decision["representation_equivalent"] and decision["no_FX_conversion"]
        assert decision["claim"]["value"] == str(value*1000)
        assert decision["source_fact"]["value"] == str(value)
        assert verify_claim(source, wrong)["verdict"] == "contradicted"


def test_long_parenthesized_negatives_and_explicit_sign_words_are_exact():
    value = "123456789012345678901234567890123456789"
    source = (f"FictionTest reported operating income of ({value}) USD million for 2016. "
              "Parentheses denote a negative amount.")
    with localcontext() as context:
        context.prec = 3
        claim = f"FictionTest's 2016 operating income was negative {value} USD million."
        result = verify_claim(source, claim)
        assert result["verdict"] == "supported"
        assert result["claim"]["value"] == result["source_fact"]["value"] == "-"+value


def test_compact_eps_does_not_mix_share_classes_units_periods_or_unranked_duplicates():
    source = "FictionTest: fiscal2016 EPS(diluted)=GBP2.20; EPS(basic)=EUR2.50."
    claim = "FictionTest's 2016 diluted earnings per share was 2.20 GBP per share."
    result = verify_claim(source, claim)
    assert result["verdict"] == "supported"
    assert result["source_fact"]["contract"] == "compact-eps-claim-v1"
    assert verify_claim(source, claim.replace("2.20", "2.50"))["verdict"] == "contradicted"
    assert verify_claim(source, claim.replace("2016", "2017"))["verdict"] == "review"
    assert verify_claim(source.replace("basic", "diluted"), claim)["verdict"] == "review"
    assert verify_claim("'"+source+"'", claim)["verdict"] == "review"


def test_assurance_reports_policy_success_separately_from_financial_coverage():
    from asof.claim_assurance import evaluate

    report = evaluate()
    assert report["policy_controls"]["correct"] == report["policy_controls"]["planned"]
    assert report["policy_controls"]["expected_review"] > 0
    for row in report["policy_controls"]["records"]:
        result = row["decision"]
        assert result["contract"] == "source-claim-v2"
        assert result["claim_and_source_values_unchanged"] and result["no_FX_conversion"]
        if result["verdict"] != "review":
            assert result["proof_valid"] and result["source_fact"] is not None
    assert report["overall_30_case_coverage"] == {
        "planned": 30, "correct_including_unresolved_as_misses": 30,
        "resolved": 30, "requires_review": 0,
    }
    assert report["no_model_calls"] and not report["independent_gold"]


@pytest.mark.parametrize("source", [
    "FictionTest reported revenue of \uff11\uff18 USD million for 2016.",
    "FictionTest reported revenue of \u0661\u0668 USD million for 2016.",
    "FictionTest reported revenue of 18 USD million for 2016. That figure is incorrect.",
    "FictionTest reported revenue of 18 USD million for 2016. The company denied this.",
    "Suppose the following. FictionTest reported revenue of 18 USD million for 2016.",
    "FictionTest reported revenue of 18 USD million for 2016. Figures are preliminary.",
    "FictionTest reported revenue of 18 USD million for 2016. Figures were later restated.",
    "FictionTest reported revenue of 18 USD million for 2016. Figures were re\u200bstated.",
    "FictionTest reported revenue of 18 USD million for 2016. S\u0430les were restated.",
    "FictionTest reported revenue of 18 USD million for 2016. The board met in Lo\u00addon.",
])
def test_disputed_estimated_or_obfuscated_sources_never_support_an_actual_fact(source):
    assert verify_claim(source, "FictionTest's 2016 revenue was 18 USD million.")["verdict"] == "review"


def test_claims_must_be_plain_ascii_and_latin_accents_or_curly_quotes_in_sources_are_allowed():
    source = "FictionTest reported revenue of 18 USD million for 2016. The caf\u00e9 \u201cMar\u00eda\u201d opened."
    assert verify_claim(source, "FictionTest's 2016 revenue was 18 USD million.")["verdict"] == "supported"
    for claim in ("FictionTest's 2016 revenue was \uff11\uff18 USD million.",
                  "FictionTest's 2016 revenue was 18 USD million.\u200b"):
        assert verify_claim(source, claim)["verdict"] == "review"


def test_per_share_sentence_tolerates_unrelated_text_but_not_other_share_wording():
    fact = "FictionTest reported diluted earnings per share of 2.15 GBP per share for 2015."
    claim = "FictionTest's 2015 diluted earnings per share was 2.15 GBP per share."
    assert verify_claim(f"{fact} The board met in London.", claim)["verdict"] == "supported"
    assert verify_claim(f"Intro. {fact}", claim)["verdict"] == "supported"
    for extra in ("Shares were split two for one.", "Basic EPS is not disclosed.", "Net losses narrowed.",
                  f"{fact}"):
        assert verify_claim(f"{fact} {extra}", claim)["verdict"] == "review", extra
