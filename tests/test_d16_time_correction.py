import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("d16", SCRIPTS / "d16_h0_time_correction.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(sensitive: bool) -> dict:
    closes = ["2023-05-09T20:00:00+00:00"] + (["2023-05-10T20:00:00+00:00"] if sensitive else [])
    return {"first_close_choices": closes, "candidate_times": ["2023-05-09T17:00:00+00:00"],
            "sensitivity_reasons": []}


def signals(*accessions):
    return pd.DataFrame({"accession": list(accessions),
                         "knowledge_time": pd.to_datetime(["2023-05-09T17:07:09Z"] * len(accessions), utc=True)})


def test_qualified_times_replace_stored_and_insensitive_rows_keep_theirs():
    m = load()
    out = m.corrected_times(signals("a", "b"), {"a": "2023-05-09T21:07:09+00:00"},
                            {"a": row(True), "b": row(False)})
    assert out.iloc[0] == pd.Timestamp("2023-05-09T21:07:09Z")
    assert out.iloc[1] == pd.Timestamp("2023-05-09T17:07:09Z")
    assert str(out.dtype) == str(signals("a")["knowledge_time"].dtype)


def test_refuses_unaudited_sensitive_rows_and_afternoons_of_early_closes():
    m = load()
    with pytest.raises(ValueError, match="assignment-sensitive"):
        m.corrected_times(signals("a"), {}, {"a": row(True)})
    with pytest.raises(ValueError, match="early close"):
        m.corrected_times(signals("a"), {"a": "2023-11-24T19:00:00+00:00"}, {"a": row(True)})
    assert m.corrected_times(signals("a"), {"a": "2022-12-23T20:19:00+00:00"}, {"a": row(True)}).notna().all()
