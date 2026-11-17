"""Aware-UTC time handling; timestamp syntax is not source-clock certification.

The P0 audit found inconsistent acceptance instants in cached SEC JSON sources despite Z
suffixes. Parse the declared representation here; adjudicate accuracy against filing-level
header/index evidence and source provenance before treating it as knowledge time.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_CLOSE_ET = time(16, 0)


def aware_utc(value: datetime, name: str = "time") -> datetime:
    """Validate an aware datetime and normalize its declared instant, not its authority."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def parse_acceptance_utc(value: str) -> datetime:
    """Parse a Z-labeled representation; this does not certify the underlying acceptance instant."""
    if not value.endswith("Z"):
        raise ValueError(f"expected UTC 'Z' suffix: {value!r}")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def et_wall_instants(wall: datetime) -> tuple[datetime, ...]:
    """Valid UTC instants for a naive NY civil clock: zero in a gap, two in a fold."""
    if wall.tzinfo is not None:
        raise ValueError("Eastern wall clock must be naive")
    instants = set()
    for fold in (0, 1):
        candidate = wall.replace(tzinfo=ET, fold=fold).astimezone(UTC)
        if candidate.astimezone(ET).replace(tzinfo=None) == wall:
            instants.add(candidate)
    return tuple(sorted(instants))


def parse_header_acceptance_et(value: str) -> datetime:
    """Interpret a header as Eastern only if its civil clock is uniquely valid.

    This conversion does not independently certify the source field's clock.
    """
    if len(value) != 14 or not value.isascii() or not value.isdigit():
        raise ValueError("header acceptance requires exactly 14 ASCII digits")
    candidates = et_wall_instants(datetime.strptime(value, "%Y%m%d%H%M%S"))
    if len(candidates) != 1:
        issue = "ambiguous" if candidates else "nonexistent"
        raise ValueError(f"{issue} Eastern header clock")
    return candidates[0]


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
