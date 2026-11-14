"""Data-free prospective registry/readiness, not a job queue or study runner."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


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
    return StudyReadiness(study_id, "blocked" if blockers else "ready", tuple(blockers), spec.outcomes)
