import importlib.util
from pathlib import Path

import pandas as pd
import pytest


def test_h4_development_winsorization_ignores_future_outcomes(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "h4_script", Path(__file__).resolve().parents[1] / "scripts" / "h4_fundamentals.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    pairs, outcomes = [], []
    for cik in range(30):
        for year in (2015, 2022):
            accession = f"{cik}-{year}"
            pairs.append({"cik": cik, "accession": accession, "report_date": f"{year}-12-31",
                          "knowledge_time": pd.Timestamp(f"{year + 1}-03-01", tz="UTC"),
                          "cos_full": 0.9})
            for offset in (-1, 0, 1):
                ni = 10 + cik * offset if year == 2015 else (offset + 2) * 1e9
                outcomes.append({"cik": cik, "accession": f"{cik}-{year + offset}",
                                 "report_date": f"{year + offset}-12-31", "ni": ni,
                                 "assets": 100.0, "revenue": 100 + offset, "gw_impair": 0.0})
    frames = {
        script.PAIRS: pd.DataFrame(pairs),
        script.OUT: pd.DataFrame(outcomes),
        script.ENT: pd.DataFrame({"cik": range(30), "sic": "3500"}),
    }
    monkeypatch.setattr(script.pd, "read_parquet", lambda path: frames[path].copy())
    with_future = script.panel_from_frames(frames[script.PAIRS], frames[script.OUT], frames[script.ENT])
    with_future = with_future[with_future["knowledge_time"].between(*script.DEV)]
    frames[script.PAIRS] = frames[script.PAIRS].iloc[::2].copy()
    frames[script.OUT] = frames[script.OUT][frames[script.OUT]["report_date"] < "2020"]
    without_future = script.panel_from_frames(frames[script.PAIRS], frames[script.OUT], frames[script.ENT])
    pd.testing.assert_frame_equal(
        with_future.reset_index(drop=True), without_future.reset_index(drop=True))


@pytest.mark.parametrize(
    ("current_ni", "next_ni", "expected"),
    [(None, 2.0, None), (2.0, None, None), (2.0, 1.0, 1.0), (2.0, 2.0, 0.0), (4.0, 0.0, 1.0)],
)
def test_h4_decline_requires_both_observed_income_values(
    monkeypatch, current_ni, next_ni, expected,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "h4_missing_income", Path(__file__).resolve().parents[1] / "scripts" / "h4_fundamentals.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    frames = {
        script.PAIRS: pd.DataFrame({
            "cik": [1], "accession": ["current"], "report_date": ["2015-12-31"],
            "knowledge_time": [pd.Timestamp("2016-03-01", tz="UTC")], "cos_full": [0.9],
        }),
        script.OUT: pd.DataFrame({
            "cik": [1, 1], "accession": ["current", "next"],
            "report_date": ["2015-12-31", "2016-12-31"], "ni": [current_ni, next_ni],
            "assets": [100.0, 100.0], "revenue": [100.0, 110.0], "gw_impair": [0.0, 0.0],
        }),
        script.ENT: pd.DataFrame({"cik": [1], "sic": ["3500"]}),
    }
    monkeypatch.setattr(script.pd, "read_parquet", lambda path: frames[path].copy())
    panel = script.panel_from_frames(frames[script.PAIRS], frames[script.OUT], frames[script.ENT])
    decline = panel["decline"].iloc[0]
    if expected is None:
        assert pd.isna(decline)
    else:
        assert decline == expected
    if current_ni == 4.0 and next_ni == 0.0:
        assert panel["d_roa"].iloc[0] == pytest.approx(-0.04)


