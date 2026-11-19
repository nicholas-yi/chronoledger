from pathlib import Path

from asof.reader_regression import regression_matrix


def test_current_candidate_regressions_keep_old_contracts_and_denominators_explicit():
    matrix = regression_matrix(Path(__file__).resolve().parents[1])
    assert not matrix["historical_results_rewritten"] and not matrix["independent_gold"]
    assert matrix["new_model_calls"] == 0
    for name, cohort in matrix["cohorts"].items():
        assert cohort["correct"] == cohort["planned"], (name, cohort["misses"])
        assert cohort["proof_checks"]["answered"] == cohort["proof_checks"]["valid"]
        assert cohort["wrong_admitted_answers"] == 0
    assert matrix["cohorts"]["grammar_robustness24"]["correct"] == 24
    assert matrix["cohorts"]["harder_all288"]["planned"] == 288
    assert matrix["cohorts"]["context_coverage192"]["planned"] == 192
    assert matrix["cohorts"]["reader_fields"]["contract"] == "field-record-v1"
