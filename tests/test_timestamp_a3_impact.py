import importlib.util
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("timestamp_a3_impact", ROOT / "scripts" / "timestamp_a3_impact.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc(text):
    return datetime.fromisoformat(text).astimezone(UTC)


CLOSES = [utc(f"2023-11-{d}T16:00:00-05:00") for d in (22, 24, 27)]


def test_conservative_calendar_moves_only_possible_early_closes():
    m = load()
    moved = m.conservative_closes(CLOSES)
    assert moved[0] == CLOSES[0] and moved[2] == CLOSES[2]
    assert moved[1] == utc("2023-11-24T13:00:00-05:00")


def test_early_close_can_reveal_hidden_lookahead():
    m = load()
    stored, truth = utc("2023-11-24T12:30:00-05:00"), utc("2023-11-24T14:00:00-05:00")
    assert m.direction(stored, truth, CLOSES) == "same_first_close"
    assert m.direction(stored, truth, m.conservative_closes(CLOSES)) == "stored_earlier_lookahead_risk"
    assert m.direction(truth, stored, m.conservative_closes(CLOSES)) == "stored_later_delay_only"
    assert m.direction(utc("2023-11-27T17:00:00-05:00"), truth, CLOSES) == "beyond_registered_calendar"


def test_impact_counts_only_qualified_rows_and_reports_calendar_changes():
    m = load()
    universe = [{"accession": "a", "pair_time": "2023-11-24T17:30:00+00:00",
                 "bulk_time": "2023-11-24T19:00:00+00:00"},
                {"accession": "b", "pair_time": "2023-11-22T15:00:00+00:00",
                 "bulk_time": "2023-11-22T15:00:00+00:00"}]
    table = [{"accession": "a", "qualified_UTC": "2023-11-24T19:00:00+00:00"},
             {"accession": "b", "qualified_UTC": None}]
    result = m.impact(universe, table, CLOSES)
    pair = result["stored_pair"]
    assert pair["nominal_16_00"]["same_first_close"] == 1
    assert pair["conservative_early_close_13_00"]["stored_earlier_lookahead_risk"] == 1
    assert pair["calendar_sensitive_changes"] == {"same_first_close->stored_earlier_lookahead_risk": 1}
    assert result["stored_bulk"]["nominal_16_00"]["stored_equals_qualified"] == 1
