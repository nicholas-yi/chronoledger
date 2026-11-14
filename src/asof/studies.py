"""Data-free prospective registry/readiness, not a job queue or study runner."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from asof.periods import DEV_RETURN_CUTOFF


@dataclass(frozen=True)
class StudySpec:
    prerequisites: tuple[str, ...]
    gates: tuple[str, ...]
    outcomes: bool


COMMON = ("source_rights", "point_in_time_contract", "inference_contract",
          "measurement_evidence", "prospective_registration", "resource_authorized", "run_authorized")
OUTCOME = (*COMMON, "qualified_sources", "economic_contract")
STUDIES = {
    "CL-P5-B0": StudySpec((), (*COMMON, "no_returns_scope"), False),
    "CL-P5-H1": StudySpec(("CL-P5-B0",), OUTCOME, True),
    "CL-P5-X1": StudySpec(("CL-P5-H1",), (*OUTCOME, "incremental_margin_fixed"), True),
    "CL-P5-G1": StudySpec(("CL-P5-X1",), (*OUTCOME, "gold_dated_links", "two_ended_identity"), True),
    "CL-P5-U1": StudySpec(("CL-P5-G1",), (*OUTCOME, "independent_calibration", "baseline_evidence"), True),
}


@dataclass(frozen=True)
class StudyReadiness:
    study_id: str
    status: Literal["ready", "blocked"]
    blockers: tuple[str, ...]
    outcomes: bool


def study_readiness(
    study_id: str, *, prerequisite_status: Mapping[str, Literal["ready", "blocked", "completed"] | None],
    gates: Mapping[str, bool | None], hypothesis: str | None,
    requested_outcomes: bool | None = None,
) -> StudyReadiness:
    """Validate supplied readiness assertions, never infer authority from a design card."""
    if study_id not in STUDIES:
        raise ValueError("unknown study ID; H1n is not an alias for formal H1")
    spec = STUDIES[study_id]
    blockers = [f"prerequisite:{p}" for p in spec.prerequisites
                if prerequisite_status.get(p) not in {"ready", "completed"}]
    blockers += [f"gate:{g}" for g in spec.gates if gates.get(g) is not True]
    if study_id == "CL-P5-H1" and hypothesis != "H1":
        blockers.append("formal_H1_identity_required")
    if requested_outcomes is not None and requested_outcomes != spec.outcomes:
        blockers.append("scope_mismatch")
    if study_id == "CL-P5-X1" and hypothesis in {"H1", "H1n"}:
        blockers.append("distinct_study_required")
    return StudyReadiness(study_id, "blocked" if blockers else "ready", tuple(blockers), spec.outcomes)


@dataclass(frozen=True)
class RunBudget:
    cpu_seconds: float
    wall_seconds: float
    resident_bytes: int

    def validate(self, *, limit: bool) -> None:
        if (any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
                or v < 0 or (limit and v == 0)
                for v in (self.cpu_seconds, self.wall_seconds, self.resident_bytes))
                or not isinstance(self.resident_bytes, int)):
            raise ValueError("finite positive limits or nonnegative measured usage required")


@dataclass(frozen=True)
class RunRequest:
    study_id: str
    run_id: str
    source_revision: str
    config_digest: str
    input_fingerprints: tuple[tuple[str, str], ...]
    budget: RunBudget
    observation_cutoff: date
    scope: Literal["synthetic", "measurement", "development"]
    outcomes: bool
    network: bool = False
    holdout: bool = False


@dataclass(frozen=True)
class RunPermit:
    request: RunRequest
    expires_at: datetime
    authorization_ref: str
    isolation_ref: str
    evidence_kind: Literal["synthetic_fixture", "operator_receipt"]


@dataclass(frozen=True)
class RunContractValidation:
    status: Literal["contract_complete", "blocked"]
    reasons: tuple[str, ...]
    request: RunRequest


def validate_run_contract(
    request: RunRequest, permit: RunPermit | None, *,
    now: datetime, prerequisite_status: Mapping[str, str | None],
    gates: Mapping[str, bool | None], hypothesis: str | None,
) -> RunContractValidation:
    """Validate declared receipts only, never issue authority or launch a process.

    Unlike design readiness, an execution contract requires completed prerequisites.
    Receipt strings are not authenticated permissions or proof of a sandbox; a real
    supervisor must verify them and enforce the tool/filesystem/network boundaries.
    """
    request.budget.validate(limit=True)
    if (not request.run_id.strip() or re.fullmatch(r"[a-f0-9]{40}", request.source_revision) is None
            or re.fullmatch(r"[a-f0-9]{16}", request.config_digest) is None
            or request.scope not in ("synthetic", "measurement", "development")
            or not isinstance(request.input_fingerprints, tuple)
            or any(not isinstance(item, tuple) or len(item) != 2
                   for item in request.input_fingerprints)
            or any(not isinstance(value, bool) for value in (
                request.outcomes, request.network, request.holdout))
            or not isinstance(request.observation_cutoff, date)
            or isinstance(request.observation_cutoff, datetime)
            or len({name for name, _ in request.input_fingerprints}) != len(request.input_fingerprints)
            or any(not name.strip() or re.fullmatch(r"[a-f0-9]{64}", digest) is None
                   for name, digest in request.input_fingerprints)):
        raise ValueError("run identity, frozen hashes, scope and unique input identities required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("permit comparison time must be timezone-aware")
    spec = STUDIES.get(request.study_id)
    if spec is None:
        raise ValueError("unknown registered study; H1n cannot alias H1")
    readiness = study_readiness(
        request.study_id,
        prerequisite_status={p: "completed" if prerequisite_status.get(p) == "completed"
                             else "blocked" for p in spec.prerequisites},
        gates=gates, hypothesis=hypothesis, requested_outcomes=request.outcomes)
    reasons = list(readiness.blockers)
    if request.network or request.holdout or request.observation_cutoff > DEV_RETURN_CUTOFF:
        reasons.append("forbidden_access_or_cutoff")
    if request.scope == "measurement" and request.outcomes:
        reasons.append("measurement_scope_cannot_consume_outcomes")
    if permit is None:
        reasons.append("run_permit_missing")
    else:
        if permit.expires_at.tzinfo is None or permit.expires_at.utcoffset() is None:
            raise ValueError("permit expiry must be timezone-aware")
        if permit.request != request:
            reasons.append("request_differs_from_frozen_permit")
        if now.astimezone(UTC) >= permit.expires_at.astimezone(UTC):
            reasons.append("permit_expired")
        if not permit.authorization_ref.strip() or not permit.isolation_ref.strip():
            reasons.append("authorization_or_isolation_receipt_missing")
        if permit.evidence_kind not in ("synthetic_fixture", "operator_receipt"):
            reasons.append("unknown_permit_evidence_kind")
        if request.scope != "synthetic" and permit.evidence_kind != "operator_receipt":
            reasons.append("synthetic_receipt_cannot_authorize_real_work")
        if request.scope != "synthetic" and not request.input_fingerprints:
            reasons.append("real_work_requires_input_snapshot_fingerprints")
    return RunContractValidation("blocked" if reasons else "contract_complete", tuple(reasons), request)


@dataclass(frozen=True)
class ContractDryRun:
    label: str
    run_id: str
    status: Literal["blocked", "budget_exceeded", "execution_failed", "metrics_mismatch", "metrics_matched"]
    reasons: tuple[str, ...]
    observed_metrics: tuple[tuple[str, float], ...]
    simulated_scientific_status: Literal["not_evaluated", "null"]


def contract_dry_run(
    request: RunRequest, validation: RunContractValidation, *, usage: RunBudget,
    expected_metrics: Mapping[str, float], observed_metrics: Mapping[str, float],
    execution_error: str | None = None,
    simulated_scientific_status: Literal["not_evaluated", "null"] = "not_evaluated",
) -> ContractDryRun:
    """Compare supplied synthetic telemetry; no callback, command, worker or filesystem access."""
    if request.scope != "synthetic":
        raise ValueError("dry run accepts synthetic requests only")
    if simulated_scientific_status not in ("not_evaluated", "null"):
        raise ValueError("a dry run cannot declare scientific support")
    request.budget.validate(limit=True)
    usage.validate(limit=False)
    if any(not math.isfinite(v) for v in (*expected_metrics.values(), *observed_metrics.values())):
        raise ValueError("synthetic metrics must be finite; missing output is not zero")
    preserved = tuple(sorted(observed_metrics.items()))
    reasons = []
    if validation.request != request:
        status = "blocked"
        reasons.append("validation_request_mismatch")
    elif validation.status != "contract_complete":
        status = "blocked"
        reasons.extend(validation.reasons)
    elif (usage.cpu_seconds > request.budget.cpu_seconds
          or usage.wall_seconds > request.budget.wall_seconds
          or usage.resident_bytes > request.budget.resident_bytes):
        status = "budget_exceeded"
        reasons.append("observed_usage_exceeds_frozen_limit")
    elif execution_error is not None:
        status = "execution_failed"
        reasons.append(execution_error)
    elif not expected_metrics or dict(expected_metrics) != dict(observed_metrics):
        status = "metrics_mismatch"
        reasons.append("missing_or_different_scoped_metric")
    else:
        status = "metrics_matched"
    return ContractDryRun("SYNTHETIC RECEIPT CHECK; no run permission or actual worker execution",
                          request.run_id, status, tuple(reasons), preserved,
                          simulated_scientific_status)
