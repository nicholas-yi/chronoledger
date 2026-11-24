from datetime import UTC, datetime

import pytest

from asof.chrono import vintage_for


def at(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=UTC)


def test_uses_previous_year_end_vintage() -> None:
    assert vintage_for(at(2023, 2, 15)) == "manelalab/chrono-bert-v1-20221231"


def test_new_years_day_uses_previous_year() -> None:
    assert vintage_for(at(2024, 1, 1, 0)) == "manelalab/chrono-bert-v1-20231231"


def test_dec_31_filing_cannot_use_same_day_vintage() -> None:
    assert vintage_for(at(2023, 12, 31, 23)) == "manelalab/chrono-bert-v1-20221231"


def test_after_last_vintage_uses_latest() -> None:
    assert vintage_for(at(2026, 6, 1)) == "manelalab/chrono-bert-v1-20241231"


def test_before_first_vintage_rejected() -> None:
    with pytest.raises(ValueError):
        vintage_for(at(1999, 6, 1))


def test_naive_rejected() -> None:
    with pytest.raises(ValueError):
        vintage_for(datetime(2023, 1, 1))
