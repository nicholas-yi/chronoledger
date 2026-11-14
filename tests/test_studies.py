import pytest

from asof.studies import STUDIES, study_readiness


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
