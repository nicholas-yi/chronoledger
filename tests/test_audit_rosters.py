import importlib.util
from pathlib import Path

import pandas as pd


def _script():
    spec = importlib.util.spec_from_file_location(
        "audit_rosters", Path(__file__).resolve().parents[1] / "scripts" / "prepare_audit_rosters.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_metadata_selection_is_deterministic_unique_and_ignores_outcomes() -> None:
    script = _script()
    frame = pd.DataFrame({
        "cik": list(range(20)) * 2, "accession": [f"A{i}" for i in range(40)],
        "knowledge_time": pd.Timestamp("2023-03-01", tz="UTC"),
        "category": ["10-K"] * 20 + ["10-Q"] * 20, "return": range(40), "cos_full": range(40),
    })
    first, shortfalls = script.sample_metadata(frame, {"10-K": 8, "10-Q": 8}, stream=0)
    altered = frame.sample(frac=1, random_state=3).assign(return_value=100, cos_full=-100)
    second, _ = script.sample_metadata(altered, {"10-K": 8, "10-Q": 8}, stream=0)
    pd.testing.assert_frame_equal(first, second)
    assert first["cik"].is_unique and len(first) == 16
    assert not any(shortfalls.values())
    assert "cos_full" not in first and "return" not in first


def test_infeasible_stratum_is_recorded_not_filled_by_other_cases() -> None:
    script = _script()
    frame = pd.DataFrame({
        "cik": [1], "accession": ["A"], "knowledge_time": [pd.Timestamp("2023-03-01", tz="UTC")],
        "category": ["continuing"],
    })
    chosen, shortfalls = script.sample_metadata(frame, {"continuing": 4, "ticker_reuse": 4}, stream=2)
    assert len(chosen) == 1
    assert shortfalls == {"continuing": 3, "ticker_reuse": 4}
