import importlib.util
from pathlib import Path

import pytest


def _script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "verify_robust_inference", scripts / "verify_robust_inference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nested_draws_cannot_overrun_the_committed_charge_budget(monkeypatch) -> None:
    script = _script(monkeypatch)
    monkeypatch.setattr(script, "resident_bytes", lambda: 0)
    budget = script.Budget()
    budget.data_replicates = 1000
    budget.bootstrap_draws = script.MAX_CHARGES - 1000 - 400
    assert budget.ceiling(400) is None
    assert budget.ceiling(401) == "replicate_charge_ceiling"
    assert script.planned_charges(script.allocation()) == script.MAX_CHARGES
    assert sum(c["requested"] for c in script.allocation()) < script.MAX_CHARGES


def test_mc_bounds_do_not_turn_missing_draws_into_nonrejections(monkeypatch) -> None:
    script = _script(monkeypatch)
    missing = script.binomial_summary(0, 0, 10, 10)
    assert missing["rate"] is None
    assert missing["CP_95_interval"] is None
    assert missing["worst_case_95_upper"] == 1
    finite = script.binomial_summary(0, 1000, 0, 1000)
    assert finite["worst_case_95_upper"] == pytest.approx(1 - 0.025 ** (1 / 1000))


def test_missing_student_df_cannot_be_labeled_with_normal_reference_metadata(monkeypatch) -> None:
    script = _script(monkeypatch)
    assert all(v is None for v in script.reference_criticals("EWC", None, {}).values())
    assert script.reference_criticals("NW_fixed_b", None, {0.05: 3.043})["0.01"] is None
    assert script.reference_criticals("IM", 6, {})["0.05"] == pytest.approx(2.4469118511449692)
