from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from asof.studies import (
    STUDIES,
    RunBudget,
    RunPermit,
    RunRequest,
    contract_dry_run,
    study_readiness,
    validate_run_contract,
)


def test_dependencies_and_authorizations_cannot_be_omitted() -> None:
    spec = STUDIES["CL-P5-H1"]
    gates = {g: True for g in spec.gates}
    result = study_readiness("CL-P5-H1", prerequisite_status={"CL-P5-B0": "blocked"},
                             gates=gates, hypothesis="H1")
    assert result.status == "blocked" and "prerequisite:CL-P5-B0" in result.blockers
    gates["run_authorized"] = None
    assert study_readiness("CL-P5-H1", prerequisite_status={"CL-P5-B0": "completed"},
                           gates=gates, hypothesis="H1").status == "blocked"
    gates["run_authorized"] = True
    assert study_readiness("CL-P5-H1", prerequisite_status={"CL-P5-B0": "completed"},
                           gates=gates, hypothesis="H1").status == "ready"
    assert study_readiness("CL-P5-H1", prerequisite_status={"CL-P5-B0": "completed"},
                           gates=gates, hypothesis="H1n").status == "blocked"
    with pytest.raises(ValueError, match="H1n"):
        study_readiness("H1n", prerequisite_status={}, gates=gates, hypothesis="H1")


def test_network_and_uncertainty_keep_their_extra_support_gates() -> None:
    for study, required in (("CL-P5-G1", "two_ended_identity"),
                            ("CL-P5-U1", "independent_calibration")):
        spec = STUDIES[study]
        gates = {g: True for g in spec.gates if g != required}
        result = study_readiness(study, prerequisite_status={p: "ready" for p in spec.prerequisites},
                                 gates=gates, hypothesis=None)
        assert result.status == "blocked" and f"gate:{required}" in result.blockers
    assert not STUDIES["CL-P5-B0"].outcomes


def _request():
    return RunRequest("CL-P5-B0", "synthetic-run", "a" * 40, "b" * 16,
                       (("synthetic_fixture", "c" * 64),), RunBudget(5, 10, 1024),
                       date(2024, 7, 31), "synthetic", False)


def _validation(request, **overrides):
    now = datetime(2024, 1, 1, tzinfo=UTC)
    permit = RunPermit(request, now + timedelta(minutes=1), "synthetic_auth",
                       "synthetic_isolation_not_actual", "synthetic_fixture")
    args = {"now": now, "prerequisite_status": {}, "hypothesis": None,
            "gates": {g: True for g in STUDIES[request.study_id].gates}}
    args.update(overrides)
    return validate_run_contract(request, permit, **args)


def test_execution_permit_requires_completed_dependencies_and_cannot_self_expand():
    base = _request()
    assert _validation(base).status == "contract_complete"
    missing = validate_run_contract(
        base, None, now=datetime(2024, 1, 1, tzinfo=UTC), prerequisite_status={},
        gates={g: True for g in STUDIES[base.study_id].gates}, hypothesis=None)
    assert missing.status == "blocked" and "run_permit_missing" in missing.reasons
    h1 = replace(base, study_id="CL-P5-H1", outcomes=True)
    assert _validation(h1, hypothesis="H1",
                       prerequisite_status={"CL-P5-B0": "ready"}).status == "blocked"
    assert _validation(h1, hypothesis="H1",
                       prerequisite_status={"CL-P5-B0": "completed"}).status == "contract_complete"
    for forbidden in (replace(base, network=True), replace(base, holdout=True),
                      replace(base, observation_cutoff=date(2024, 8, 1)),
                      replace(base, scope="measurement")):
        assert _validation(forbidden).status == "blocked"
    now = datetime(2024, 1, 1, tzinfo=UTC)
    permit = RunPermit(base, now, "auth", "isolation", "operator_receipt")
    result = validate_run_contract(
        replace(base, budget=RunBudget(10, 10, 1024)), permit, now=now,
        prerequisite_status={}, gates={g: True for g in STUDIES[base.study_id].gates},
        hypothesis=None)
    assert "request_differs_from_frozen_permit" in result.reasons
    assert "permit_expired" in result.reasons


def test_dry_run_preserves_partial_metrics_budget_failure_and_null_instead_of_support():
    request = _request()
    validation = _validation(request)
    args = {"usage": RunBudget(1, 2, 500), "expected_metrics": {"metric": 0.0},
            "observed_metrics": {"metric": 0.0}, "simulated_scientific_status": "null"}
    assert contract_dry_run(request, validation, **args).status == "metrics_matched"
    assert contract_dry_run(
        request, validation, **{**args, "usage": RunBudget(6, 2, 500)}).status == "budget_exceeded"
    failed = contract_dry_run(
        request, validation, **{**args, "observed_metrics": {"partial": 0.3}},
        execution_error="synthetic_worker_failure")
    assert failed.status == "execution_failed" and failed.observed_metrics == (("partial", 0.3),)
    assert contract_dry_run(
        request, validation, **{**args, "observed_metrics": {}}).status == "metrics_mismatch"
    assert contract_dry_run(
        replace(request, run_id="another-run"), validation, **args).status == "blocked"
    with pytest.raises(ValueError, match="positive"):
        replace(request.budget, cpu_seconds=float("inf")).validate(limit=True)
