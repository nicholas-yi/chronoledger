import importlib.util
from pathlib import Path

import pandas as pd


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
    with_future = script.build_panel()
    with_future = with_future[with_future["knowledge_time"].between(*script.DEV)]
    frames[script.PAIRS] = frames[script.PAIRS].iloc[::2].copy()
    frames[script.OUT] = frames[script.OUT][frames[script.OUT]["report_date"] < "2020"]
    without_future = script.build_panel()
    pd.testing.assert_frame_equal(
        with_future.reset_index(drop=True), without_future.reset_index(drop=True))
