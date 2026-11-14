"""Applicable synthetic cases from CL-ORACLES-20261113-R1, not empirical gold."""

import json

import pytest

from asof import ledger, trial_manifest
from asof.costs import component_costs
from asof.studies import STUDIES, study_readiness


@pytest.mark.parametrize(
    ("monthly", "directed_event", "scenario", "tfidf", "expected"),
    [
        (3.3, -0.1, 1.0, 2.1, "not_supported"),  # P3-D01
        (3.1, 3.1, 1.0, 2.1, "not_supported"),  # D02
        (3.3, 0.4, -1.0, 2.1, "not_supported"),  # D03
        (3.3, 0.4, 1.0, None, "unavailable"),  # D04: undetermined
        (2.9, 3.3, 1.0, 2.1, "not_supported"),  # D05
        (3.2, 0.1, 1.0, 2.1, "supported"),  # D06: predicate only
        (3.3, 0.4, -1.0, None, "not_supported"),  # D07
        (3.3, 0.0, 1.0, 2.1, "not_supported"),  # D08
        (3.1, 3.3, 1.0, 2.1, "supported"),  # D09
        (3.3, 0.4, 1.0, 2.1, "supported"),  # D10: Holm supplementary
    ],
)
def test_p3_d01_d10(monthly, directed_event, scenario, tfidf, expected) -> None:
    result = trial_manifest.registered_co_primary_decision(
        "H1", monthly_t=monthly, event_change_t=-directed_event,
        delisting_effects={0.0: 1.0, -0.3: 1.0, -1.0: scenario},
        referee_passed=True, requires_tfidf=True, tfidf_t=tfidf,
    )
    assert result.status == expected


def _entry(digest, **config):
    return {"hypothesis": "H0", "period": "development", "config_hash": digest,
            "config": config, "metrics": {}, "logged_at": "synthetic"}


def test_p3_m03_missing_purpose_is_unresolved_not_inferred_scientific() -> None:
    result = trial_manifest.build_manifest([_entry("A"), _entry("B", purpose="scientific")])
    assert result["registered_N_per_hypothesis"]["H0"] == 2
    assert result["attempts"][0]["purpose"] == "unknown"


def test_p3_m04_preserves_vintages_without_equivalence_or_latest_selection() -> None:
    first = {**_entry("A", purpose="scientific"), "lineage": {"git_commit": "c1", "inputs": {"x": "d1"}}}
    second = {**_entry("A", purpose="scientific"), "lineage": {"git_commit": "c2", "inputs": {"x": "d2"}}}
    result = trial_manifest.build_manifest([first, second])
    assert result["registered_N_per_hypothesis"]["H0"] == 1
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["lineage"] != result["attempts"][1]["lineage"]
    assert all(r["matrix_eligibility"] == "unavailable" for r in result["attempts"])


def test_p3_m09_rejects_reduced_history_without_overwriting_registered_n(
    tmp_path, monkeypatch,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    existing = results / "trial_manifest.json"
    existing.write_text(json.dumps({"registered_N_per_hypothesis": {"H0": 3}, "attempts": []}))
    before = existing.read_bytes()
    fake_ledger = results / "trial_ledger.jsonl"
    fake_ledger.write_text("synthetic: read via stub")
    monkeypatch.setattr(ledger, "LEDGER_PATH", fake_ledger)
    monkeypatch.setattr(ledger, "read_ledger", lambda: [_entry("A"), _entry("B")])
    monkeypatch.setattr(trial_manifest, "PROJECT_ROOT", tmp_path)
    with pytest.raises(ValueError, match="registered"):
        trial_manifest.main()
    assert existing.read_bytes() == before


@pytest.mark.parametrize(
    ("study", "overrides", "hypothesis", "extra", "expected"),
    [
        ("CL-P5-B0", {"source_rights": None, "run_ready": True}, None, {}, "gate:source_rights"),
        ("CL-P5-B0", {}, None, {"requested_outcomes": True}, "scope_mismatch"),
        ("CL-P5-X1", {}, "H1", {}, "distinct_study_required"),
        ("CL-P5-G1", {"two_ended_identity": None}, None, {}, "gate:two_ended_identity"),
        ("CL-P5-U1", {"independent_calibration": False}, None, {}, "gate:independent_calibration"),
        ("CL-P5-H1", {"run_authorized": None}, "H1", {}, "gate:run_authorized"),
    ],
)
def test_p5_adversarial_readiness(study, overrides, hypothesis, extra, expected) -> None:
    spec = STUDIES[study]
    gates = {g: True for g in spec.gates}
    gates.update(overrides)
    result = study_readiness(
        study, prerequisite_status={p: "completed" for p in spec.prerequisites},
        gates=gates, hypothesis=hypothesis, **extra)
    assert result.status == "blocked" and expected in result.blockers


@pytest.mark.parametrize(("traded", "expected"), [(1000.0, 0.70), (2000.0, 1.40)])
def test_p6_t01_t02_count_each_traded_leg_once(traded, expected) -> None:
    result = component_costs(
        capital=10000, currency="USD", turnover=traded / 10000, turnover_basis="gross_traded",
        half_spread_bps=4, execution_bps={"fees": 1, "impact": 2},
        holding_bps_of_capital={"borrow": 0, "financing": 0, "distributions": 0},
        borrow_available=True, fills_supported=True, gross_return=None)
    assert result.total_currency_cost == pytest.approx(expected)


def test_p6_t03_separates_distribution_from_execution_and_carry() -> None:
    result = component_costs(
        capital=10000, currency="USD", turnover=1, turnover_basis="gross_traded",
        half_spread_bps=4, execution_bps={"fees": 1, "impact": 0},
        holding_bps_of_capital={"borrow": 15, "financing": 10, "distributions": 50},
        borrow_available=True, fills_supported=True, gross_return=0)
    assert result.total_currency_cost == pytest.approx(80)
    assert result.total_currency_cost is not None
    distribution_ratio = result.component_return_costs["distributions"]
    assert distribution_ratio is not None
    distribution = distribution_ratio * 10000
    execution_carry = result.total_currency_cost - distribution
    assert execution_carry == pytest.approx(30)
    assert -50 - execution_carry == pytest.approx(0 - result.total_currency_cost)


@pytest.mark.parametrize(("half_spread", "net"), [(5, 6), (8, 0), (10, -4)])
def test_p6_t06_break_even_counts_only_incremental_costs(half_spread, net) -> None:
    result = component_costs(
        capital=10000, currency="USD", turnover=2, turnover_basis="gross_traded",
        half_spread_bps=half_spread, execution_bps={"fees": 1, "impact": 0.5},
        holding_bps_of_capital={"borrow": 1, "financing": 0, "distributions": 0},
        borrow_available=True, fills_supported=True, gross_return=20 / 10000)
    assert result.total_currency_cost is not None
    assert 20 - result.total_currency_cost == pytest.approx(net)
    assert result.break_even_one_way_bps == pytest.approx(9.5)


def test_p6_t07_does_not_silently_halve_supplied_frozen_turnover() -> None:
    args = {
        "capital": 10000, "currency": "USD", "half_spread_bps": 4,
        "execution_bps": {"fees": 0, "impact": 0},
        "holding_bps_of_capital": {"borrow": 0, "financing": 0, "distributions": 0},
        "borrow_available": True, "fills_supported": True, "gross_return": None,
    }
    frozen_basis = component_costs(turnover=0.2, turnover_basis="one_way", **args)
    traded_basis = component_costs(turnover=2000 / 10000, turnover_basis="gross_traded", **args)
    assert frozen_basis.total_currency_cost == pytest.approx(1.60)
    assert traded_basis.total_currency_cost == pytest.approx(0.80)
