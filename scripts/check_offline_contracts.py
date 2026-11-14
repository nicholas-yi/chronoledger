"""Persist deterministic contract fixtures; no jobs, models, data requests or trial rows."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta

from asof import ledger
from asof.config import PROJECT_ROOT
from asof.costs import component_costs, reconcile_net_return, reconcile_turnover
from asof.measurement import MeasurementCase, score_measurement
from asof.studies import (
    STUDIES,
    RunBudget,
    RunPermit,
    RunRequest,
    contract_dry_run,
    validate_run_contract,
)


def main() -> None:
    output = {
        "label": "SYNTHETIC CONTRACT FIXTURES ONLY; not real measurement, inference or isolation proof",
        "status": "incomplete", "lineage": ledger.lineage(),
        "real_jobs_launched": 0, "trial_rows_appended": 0,
    }
    try:
        now = datetime(2024, 1, 1, tzinfo=UTC)
        request = RunRequest(
            "CL-P5-B0", "synthetic-contract", "a" * 40, "b" * 16,
            (("synthetic-fixture", "c" * 64),), RunBudget(5, 10, 1024),
            date(2024, 7, 31), "synthetic", False)
        permit = RunPermit(request, now + timedelta(minutes=1), "synthetic-authorization",
                           "synthetic-isolation-NOT-verified", "synthetic_fixture")
        gates = {g: True for g in STUDIES[request.study_id].gates}
        validation = validate_run_contract(
            request, permit, now=now, prerequisite_status={}, gates=gates, hypothesis=None)
        args = {"usage": RunBudget(1, 2, 500), "expected_metrics": {"toy_metric": 0.0},
                "observed_metrics": {"toy_metric": 0.0}, "simulated_scientific_status": "null"}
        examples = {
            "null_kept": contract_dry_run(request, validation, **args),
            "missing_output": contract_dry_run(
                request, validation, **{**args, "observed_metrics": {}}),
            "budget_exceeded": contract_dry_run(
                request, validation, **{**args, "usage": RunBudget(6, 2, 500)}),
            "partial_failure": contract_dry_run(
                request, validation, **{**args, "observed_metrics": {"partial": 0.3}},
                execution_error="synthetic_worker_failure"),
            "request_changed": contract_dry_run(
                replace(request, run_id="changed"), validation, **args),
        }
        expected = {"null_kept": "metrics_matched", "missing_output": "metrics_mismatch",
                    "budget_exceeded": "budget_exceeded", "partial_failure": "execution_failed",
                    "request_changed": "blocked"}
        if any(receipt.status != expected[key] for key, receipt in examples.items()):
            raise RuntimeError("synthetic permit/metric fixture disagreement")
        output["fleet"] = {name: asdict(receipt) for name, receipt in examples.items()}
        costs = component_costs(
            capital=10000, currency="USD", turnover=1, turnover_basis="gross_traded",
            half_spread_bps=4, execution_bps={"fees": 1, "impact": 0},
            holding_bps_of_capital={"borrow": 15, "financing": 10, "distributions": 50},
            borrow_available=True, fills_supported=True, gross_return=None)
        pnl = reconcile_net_return(costs, gross_return=-0.005, distributions_in_gross=True)
        basis = reconcile_turnover(
            capital=10000, traded_notional=2000, frozen_turnover=0.2, half_spread_bps=4,
            currency="USD")
        output["costs"] = {"components": asdict(costs), "net_return": asdict(pnl),
                           "turnover_receipt": asdict(basis)}
        cases = [
            MeasurementCase(
                "synthetic-A", "synthetic-issuer-A", "test", now, frozenset({"a"}),
                frozenset({"a"}), ("invented-gold-ref",), ("invented-quote-ref",), True, True),
            MeasurementCase(
                "synthetic-B", "synthetic-issuer-B", "test", now, frozenset({"b"}),
                None, ("invented-gold-ref",), (), True, True, abstention_reason="no_evidence"),
        ]
        score = score_measurement(cases)
        if score.recall != 0.5 or pnl.net_return != -0.008 or basis.status != "basis_mismatch":
            raise RuntimeError("synthetic measurement/cost fixture disagreement")
        output["measurement"] = asdict(score)
        output["status"] = "complete_synthetic_fixture_check"
    except (ValueError, RuntimeError) as exc:
        output["stop_reason"] = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        path = PROJECT_ROOT / "results" / "offline_contract_fixtures.json"
        path.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
        print(output["status"])


if __name__ == "__main__":
    main()
