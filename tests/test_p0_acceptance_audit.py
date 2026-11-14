import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd
import pytest


def _script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("p0_acceptance_audit", scripts / "p0_acceptance_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_header_candidate_preserves_raw_field_and_seasonal_offset(monkeypatch) -> None:
    script = _script(monkeypatch)
    for raw, utc in (("20230331163000", "2023-03-31T20:30:00+00:00"),
                     ("20230228163000", "2023-02-28T21:30:00+00:00")):
        parsed = script.header_fields(
            f"&lt;ACCEPTANCE-DATETIME&gt;{raw}\nCENTRAL INDEX KEY: 0000000001")
        assert parsed["header_raw"] == raw
        assert parsed["UTC_if_header_ET"] == utc
        assert parsed["header_CIKs"] == ["0000000001"]


def test_impact_counts_closes_and_latest_signal_not_just_raw_mismatches(monkeypatch) -> None:
    script = _script(monkeypatch)
    frame = pd.DataFrame({
        "cik_pair": [1], "accession": ["synthetic"],
        "knowledge_time_pair": pd.to_datetime(["2023-03-31T16:30:00Z"]),
        "knowledge_time_bulk": pd.to_datetime(["2023-03-31T20:30:00Z"]),
    })
    result = script.timing_impact(frame, [date(2023, 3, 31), date(2023, 4, 3)])
    assert result["first_registered_close_differs"] == 1
    assert result["formation_row_month_instances_differ"] == 1
    assert result["latest_signal_firm_month_choices_differ"] == 1


def test_impact_requires_identity_instead_of_reporting_unmeasured_zero(monkeypatch) -> None:
    script = _script(monkeypatch)
    frame = pd.DataFrame({
        "knowledge_time_pair": pd.to_datetime(["2023-03-31T19:00:00Z"]),
        "knowledge_time_bulk": pd.to_datetime(["2023-03-31T19:30:00Z"]),
    })
    with pytest.raises(KeyError, match="cik_pair"):
        script.timing_impact(frame, [date(2023, 3, 31)])


def test_latest_selection_can_change_without_close_or_eligibility_changes(monkeypatch) -> None:
    script = _script(monkeypatch)
    frame = pd.DataFrame({
        "cik_pair": [1, 1], "accession": ["A", "B"],
        "knowledge_time_pair": pd.to_datetime(["2023-03-31T19:00:00Z", "2023-03-31T19:30:00Z"]),
        "knowledge_time_bulk": pd.to_datetime(["2023-03-31T19:45:00Z", "2023-03-31T19:30:00Z"]),
    })
    result = script.timing_impact(frame, [date(2023, 3, 30), date(2023, 3, 31)])
    assert result["first_registered_close_differs"] == 0
    assert result["formation_eligibility_rows_differ"] == 0
    assert result["latest_signal_firm_month_choices_differ"] == 1


@pytest.mark.parametrize(("before", "at_close", "days"), [
    ("2023-02-28T20:59:59Z", "2023-02-28T21:00:00Z", [date(2023, 2, 28), date(2023, 3, 1)]),
    ("2023-03-31T19:59:59Z", "2023-03-31T20:00:00Z", [date(2023, 3, 31), date(2023, 4, 3)]),
])
def test_exact_close_is_ineligible_in_both_est_and_edt(
    monkeypatch, before: str, at_close: str, days: list[date],
) -> None:
    script = _script(monkeypatch)
    frame = pd.DataFrame({
        "cik_pair": [1], "accession": ["synthetic"],
        "knowledge_time_pair": pd.to_datetime([before]),
        "knowledge_time_bulk": pd.to_datetime([at_close]),
    })
    result = script.timing_impact(frame, days)
    assert result["first_registered_close_differs"] == 1
    assert result["formation_eligibility_rows_differ"] == 1
