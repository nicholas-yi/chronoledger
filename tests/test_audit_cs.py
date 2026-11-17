import importlib.util
import itertools
import math
import sys
from fractions import Fraction
from functools import cache
from pathlib import Path

import pytest

from asof.audit_cs import audit_confidence_set


def exact_members(population: int, drawn: int, errors: int, unread: int, delta: Fraction) -> set:
    def probability(total: int, successes: int) -> Fraction:
        if successes > total or drawn - successes > population - total:
            return Fraction(0)
        return Fraction(
            math.comb(total, successes) * math.comb(population - total, drawn - successes),
            math.comb(population, drawn))

    return {
        total for total in range(population + 1)
        if any(probability(total, s) >= delta / (drawn + 1)
               for s in range(errors, errors + unread + 1))
    }


@cache
def members(population: int, drawn: int, errors: int, unread: int, delta: float) -> set:
    result = audit_confidence_set(population, drawn, errors, unread, delta)
    return {k for k in range(population + 1) if result.contains(k)}


def test_all_small_states_match_independent_rational_unread_union() -> None:
    for population in range(1, 9):
        for drawn in range(population + 1):
            for unread in range(drawn + 1):
                for errors in range(drawn - unread + 1):
                    assert members(population, drawn, errors, unread, 0.05) == exact_members(
                        population, drawn, errors, unread, Fraction(1, 20))


def test_exact_anytime_coverage_over_all_small_random_orders() -> None:
    saw_noncoverage = False
    for population, delta in itertools.product((6, 10), (Fraction(1, 20), Fraction(1, 5))):
        for total in range(population + 1):
            failed = [0, 0, 0]
            for positive_positions in itertools.combinations(range(population), total):
                positives = set(positive_positions)
                successes = 0
                missed = [False, False, False]
                for drawn in range(1, population + 1):
                    successes += drawn - 1 in positives
                    # Full observation, hiding every error, hiding every non-error.
                    states = ((successes, 0), (0, successes), (successes, drawn - successes))
                    full = members(population, drawn, successes, 0, float(delta))
                    for i, (errors, unread) in enumerate(states):
                        current = members(population, drawn, errors, unread, float(delta))
                        assert full <= current
                        missed[i] |= total not in current
                failed = [n + miss for n, miss in zip(failed, missed, strict=True)]
            denominator = math.comb(population, total)
            assert all(Fraction(n, denominator) <= delta for n in failed)
            saw_noncoverage |= failed[0] > 0
    assert saw_noncoverage, "include nontrivial rejection paths, not just full-width sets"


def test_no_observations_and_unread_census_preserve_unknowns() -> None:
    assert audit_confidence_set(100, 0, 0).intervals == ((0, 100),)
    assert audit_confidence_set(100, 100, 0, 100).intervals == ((0, 100),)
    assert audit_confidence_set(100, 100, 12, 7).intervals == ((12, 19),)
    for total in (0, 1, 50, 100):
        assert audit_confidence_set(100, 100, total).intervals == ((total, total),)


def test_equality_boundary_and_project_scale_support() -> None:
    assert audit_confidence_set(40, 1, 0).contains(39)
    assert not audit_confidence_set(40, 1, 0).contains(40)
    assert audit_confidence_set(16_921, 1, 0).intervals == ((0, 16_497),)
    assert audit_confidence_set(16_921, 16_921, 8_000, 6).intervals == ((8_000, 8_006),)


@pytest.mark.parametrize("arguments", [
    (0, 0, 0, 0, 0.05), (100_001, 0, 0, 0, 0.05),
    (True, 0, 0, 0, 0.05), (10, 1.0, 0, 0, 0.05), (10, 1, False, 0, 0.05),
    (10, 11, 0, 0, 0.05), (10, 2, 0, 3, 0.05), (10, 2, 2, 1, 0.05),
    (10, 1, -1, 0, 0.05), (10, 1, 0, -1, 0.05),
    (10, 1, 0, 0, float("nan")), (10, 1, 0, 0, float("inf")),
    (10, 1, 0, 0, 0), (10, 1, 0, 0, 1), (10, 1, 0, 0, True),
])
def test_invalid_counts_and_levels_fail_explicitly(arguments: tuple) -> None:
    with pytest.raises(ValueError):
        audit_confidence_set(*arguments)


def test_backend_numeric_failure_is_not_a_full_set_fallback(monkeypatch) -> None:
    import asof.audit_cs as module

    monkeypatch.setattr(module.hypergeom, "logpmf", lambda *args: float("nan"))
    with pytest.raises(ArithmeticError, match="invalid log probability"):
        audit_confidence_set(10, 1, 0)


def test_counts_cli_declares_conditional_scope_and_rejects_bad_inputs(capsys) -> None:
    import json

    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_confidence_sequence.py"
    spec = importlib.util.spec_from_file_location("audit_cs_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.main(["--population", "10", "--drawn", "10", "--errors", "2",
                        "--unread", "3"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["total_error_intervals_inclusive"] == [[2, 5]]
    assert output["sampling_verified"] is False
    assert output["scientific_acceptance"] is False
    with pytest.raises(SystemExit) as exc:
        module.main(["--population", "10", "--drawn", "11", "--errors", "0"])
    assert exc.value.code == 2
    assert "drawn <= population" in capsys.readouterr().err
