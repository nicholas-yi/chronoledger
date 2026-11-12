from datetime import date, datetime, timezone

import pytest

from asof.timeutil import (
    first_tradable_close,
    parse_acceptance_utc,
    parse_header_acceptance_et,
)


@pytest.mark.parametrize(
    ("json_value", "header_value"),
    [
        # Observed Apple filings: EST (UTC-5) and EDT (UTC-4) cases.
        ("2026-11-09T21:30:40.000Z", "20261109163040"),
        ("2026-07-31T10:01:02.000Z", "20260731060102"),
        ("2026-04-20T21:29:51.000Z", "20260420172951"),
    ],
)
def test_json_utc_matches_header_eastern(json_value: str, header_value: str) -> None:
    assert parse_acceptance_utc(json_value) == parse_header_acceptance_et(header_value)


def test_rejects_naive_or_non_utc_strings() -> None:
    with pytest.raises(ValueError):
        parse_acceptance_utc("2026-11-09T21:30:40")


def test_premarket_filing_trades_same_day_close() -> None:
    accepted = parse_header_acceptance_et("20260731060102")
    days = [date(2026, 7, 30), date(2026, 7, 31), date(2026, 8, 3)]
    assert first_tradable_close(accepted, days) == date(2026, 7, 31)


def test_after_close_filing_trades_next_close() -> None:
    accepted = parse_header_acceptance_et("20261109163040")
    days = [date(2026, 11, 9), date(2026, 11, 10)]
    assert first_tradable_close(accepted, days) == date(2026, 11, 10)


def test_filing_exactly_at_close_waits_for_next_close() -> None:
    accepted = parse_header_acceptance_et("20261109160000")
    days = [date(2026, 11, 9), date(2026, 11, 10)]
    assert first_tradable_close(accepted, days) == date(2026, 11, 10)


def test_naive_knowledge_time_rejected() -> None:
    with pytest.raises(ValueError):
        first_tradable_close(datetime(2026, 1, 1), [date(2026, 1, 2)])


def test_no_future_trading_day_returns_none() -> None:
    accepted = datetime(2026, 1, 5, 23, tzinfo=timezone.utc)
    assert first_tradable_close(accepted, [date(2026, 1, 5)]) is None
