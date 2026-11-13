"""Time handling: every fact's knowledge time is an aware UTC timestamp.

EDGAR's submissions JSON reports ``acceptanceDateTime`` in true UTC (verified against the
US/Eastern ``ACCEPTANCE-DATETIME`` in filing headers, across EST and EDT). Header values are
US/Eastern local time.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_CLOSE_ET = time(16, 0)


def parse_acceptance_utc(value: str) -> datetime:
    """Parse submissions-JSON ``acceptanceDateTime`` (e.g. '2026-11-09T21:30:40.000Z')."""
    if not value.endswith("Z"):
        raise ValueError(f"expected UTC 'Z' suffix: {value!r}")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_header_acceptance_et(value: str) -> datetime:
    """Parse filing-header ``ACCEPTANCE-DATETIME`` (US/Eastern, 'YYYYMMDDhhmmss') to UTC."""
    local = datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=ET)
    return local.astimezone(timezone.utc)


def close_time_utc(day: date) -> datetime:
    return datetime.combine(day, MARKET_CLOSE_ET, tzinfo=ET).astimezone(timezone.utc)


def first_tradable_close(knowledge_time: datetime, trading_days: list[date]) -> date | None:
    """First day in a sorted trading calendar whose close is strictly after ``knowledge_time``.

    A signal known at ``knowledge_time`` can earn returns only from that close onward. This is
    deliberately conservative: filings accepted at 15:59 ET are traded at that day's close only
    if the close is strictly later, never earlier.
    """
    if knowledge_time.tzinfo is None:
        raise ValueError("knowledge_time must be timezone-aware")
    i = bisect_left(trading_days, knowledge_time.astimezone(ET).date())
    if i < len(trading_days) and close_time_utc(trading_days[i]) <= knowledge_time:
        i += 1
    return trading_days[i] if i < len(trading_days) else None


def utc_day_end(day: date) -> datetime:
    """End of a calendar day in UTC, useful for as-of queries keyed by date."""
    return datetime.combine(day + timedelta(days=1), time(0), tzinfo=timezone.utc)
