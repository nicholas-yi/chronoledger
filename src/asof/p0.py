"""Hypothetical acceptance-clock sensitivity, never timestamp correction or authority."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Literal

from asof.timeutil import ET, et_wall_instants


@dataclass(frozen=True)
class ClockBranch:
    interpretation: Literal["stored_UTC", "late_correction", "ET_wall_correction"]
    instant: datetime


@dataclass(frozen=True)
class ClockCandidates:
    branches: tuple[ClockBranch, ...]
    issues: tuple[str, ...]

    @property
    def instants(self) -> tuple[datetime, ...]:
        return tuple(sorted({b.instant for b in self.branches}))


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("acceptance candidates require timezone-aware datetimes")
    return value.astimezone(UTC)


def acceptance_candidates(stored: datetime) -> ClockCandidates:
    """Apply R1's CORRECT/LATE/EARLY hypotheses, not probabilities or verified labels.

    LATE solves t = stored + NY_offset(t); EARLY reinterprets the displayed UTC
    wall clock as New York local time. Named-zone round trips retain both valid
    fall-back folds and reject nonexistent local clocks without normalizing them.
    """
    stored = _aware(stored)
    branches = [ClockBranch("stored_UTC", stored)]
    offsets = {(stored + timedelta(days=d)).astimezone(ET).utcoffset() for d in (-1, 0, 1)}
    for offset in sorted(offsets):
        assert offset is not None
        candidate = stored + offset
        if candidate.astimezone(ET).utcoffset() == offset:
            branches.append(ClockBranch("late_correction", candidate))
    wall = stored.replace(tzinfo=None)
    local_candidates = et_wall_instants(wall)
    branches.extend(ClockBranch("ET_wall_correction", t) for t in sorted(local_candidates))
    issues = (() if len(local_candidates) == 1 else
              ("ambiguous_ET_wall_clock",) if local_candidates else ("nonexistent_ET_wall_clock",))
    return ClockCandidates(tuple(branches), issues)


def first_close_options(
    instants: Sequence[datetime], session_closes: Sequence[datetime],
) -> tuple[datetime | None, ...]:
    """Strictly later supplied closes; do not infer a venue/calendar or extend its tail."""
    closes = tuple(_aware(t) for t in session_closes)
    if any(a >= b for a, b in pairwise(closes)):
        raise ValueError("session closes must be strictly ordered and unique")
    times = tuple(_aware(t) for t in instants)
    if not times:
        raise ValueError("empty acceptance candidate set")
    indices = {bisect_right(closes, t) for t in times}
    return tuple(closes[i] if i < len(closes) else None for i in sorted(indices))


def latest_signal_options(
    records: Sequence[tuple[str, Sequence[datetime]]], formation_close: datetime,
    *, max_age_days: int, signal_window: tuple[datetime, datetime] | None = None,
) -> tuple[str | None, ...]:
    """Exact possible latest records under independent candidate choices.

    Preserve supplied input order on equal timestamps, matching a stable sort
    followed by group tail(1). A possible winner must dominate every necessarily
    eligible peer's earliest feasible time. Never choose one clock as authority.
    """
    close = _aware(formation_close)
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days < 1:
        raise ValueError("positive integer maximum signal age required")
    if len({a for a, _ in records}) != len(records):
        raise ValueError("one record per accession is required")
    lower = close - timedelta(days=max_age_days)
    upper = close
    if signal_window is not None:
        start, end = (_aware(t) for t in signal_window)
        if start >= end:
            raise ValueError("signal window requires ordered half-open bounds")
        lower, upper = max(lower, start), min(upper, end)
    choices = []
    forced = []
    for order, (accession, candidates) in enumerate(records):
        if not accession:
            raise ValueError("nonempty accession identity required")
        times = tuple(_aware(t) for t in candidates)
        if not times:
            raise ValueError("empty acceptance candidate set")
        eligible = [t for t in times if lower <= t < upper]
        if eligible:
            choices.append((accession, (max(eligible), order)))
            if len(eligible) == len(times):
                forced.append((min(eligible), order))
    winners = []
    for accession, largest in choices:
        other_minima = [t for t in forced if t[1] != largest[1]]
        if not other_minima or largest >= max(other_minima):
            winners.append(accession)
    return tuple(winners) if forced else (*winners, None)


def window_membership_options(
    focal: Sequence[datetime], other: Sequence[datetime],
    *, window: Literal["prior_120d", "future_365d"],
) -> tuple[bool, ...]:
    """R1 fixture contracts: [focal-120d,focal) or (focal,focal+365d].

    Both clocks may vary jointly. These are metadata membership decisions, not
    observed positive/negative H6 labels or a new interpretation of frozen tests.
    """
    if window not in ("prior_120d", "future_365d"):
        raise ValueError("unknown temporal membership window")
    a, b = tuple(_aware(t) for t in focal), tuple(_aware(t) for t in other)
    if not a or not b:
        raise ValueError("both acceptance candidate sets must be nonempty")
    lower, upper = ((-timedelta(days=120), timedelta(0)) if window == "prior_120d"
                    else (timedelta(0), timedelta(days=365)))

    def contains(delta: timedelta) -> bool:
        return (lower <= delta < upper if window == "prior_120d" else lower < delta <= upper)

    minimum, maximum = min(b) - max(a), max(b) - min(a)
    if ((window == "prior_120d" and (maximum < lower or minimum >= upper))
            or (window == "future_365d" and (maximum <= lower or minimum > upper))):
        return (False,)
    if contains(minimum) and contains(maximum):
        return (True,)
    return tuple(sorted({contains(t_other - t_focal) for t_focal in a for t_other in b}))
