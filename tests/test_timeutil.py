from datetime import UTC, date, datetime, time, timedelta

import pytest

from asof.timeutil import (
    ET,
    close_time_utc,
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


@pytest.mark.parametrize(("value", "reason"), [
    ("20241103013000", "ambiguous"),
    ("20240310023000", "nonexistent"),
    ("2024010101010", "14 ASCII digits"),
])
def test_header_clock_never_silently_chooses_a_fold_or_normalizes_a_gap(value, reason) -> None:
    with pytest.raises(ValueError, match=reason):
        parse_header_acceptance_et(value)


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
    accepted = datetime(2026, 1, 5, 23, tzinfo=UTC)
    assert first_tradable_close(accepted, [date(2026, 1, 5)]) is None


def test_filing_after_an_early_close_waits_for_the_next_session() -> None:
    accepted = parse_header_acceptance_et("20231124140000")  # 2 p.m. on a 1 p.m. close day
    assert first_tradable_close(accepted, [date(2023, 11, 24), date(2023, 11, 27)]) == date(2023, 11, 27)
    before = parse_header_acceptance_et("20231124124500")
    assert first_tradable_close(before, [date(2023, 11, 24), date(2023, 11, 27)]) == date(2023, 11, 24)


@pytest.mark.parametrize(("day", "early"), [
    # Published by NYSE for 2026-2028.
    (date(2026, 11, 27), True), (date(2026, 12, 24), True), (date(2027, 11, 26), True),
    (date(2028, 7, 3), True), (date(2028, 11, 24), True),
    # Friday holidays and ordinary days are not early closes.
    (date(2026, 7, 2), False), (date(2027, 12, 23), False), (date(2026, 11, 25), False),
])
def test_early_closes_match_published_nyse_schedule(day, early) -> None:
    assert close_time_utc(day).astimezone(ET).time() == (time(13) if early else time(16))


def test_dates_outside_the_verified_calendar_are_refused() -> None:
    with pytest.raises(ValueError, match=r"extend it from nyse\.com"):
        close_time_utc(date(2029, 1, 2))


def test_binary_lookup_matches_linear_reference_across_dst_and_gaps() -> None:
    start = date(2023, 1, 1)
    days = [start + timedelta(days=i) for i in range(400)
            if (start + timedelta(days=i)).weekday() < 5 and i % 17]
    for day in [days[0] - timedelta(days=5), *days, days[-1] + timedelta(days=5)]:
        for offset in (-1, 0, 1, 8 * 3600):
            accepted = close_time_utc(day) + timedelta(seconds=offset)
            expected = next((d for d in days if close_time_utc(d) > accepted), None)
            assert first_tradable_close(accepted, days) == expected
    assert first_tradable_close(close_time_utc(days[0]), []) is None
