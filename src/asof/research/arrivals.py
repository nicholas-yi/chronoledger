"""B: supplied-calendar marked exponential Hawkes calculations, with no parameter fitting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise

from asof.timeutil import aware_utc

from ._validation import scalar

DAY = 86400.0


@dataclass(frozen=True)
class CalendarRate:
    start: datetime
    end: datetime
    per_day: float
    frozen_at: datetime

    def __post_init__(self) -> None:
        start, end = aware_utc(self.start), aware_utc(self.end)
        frozen = aware_utc(self.frozen_at)
        if start >= end or frozen > start:
            raise ValueError("calendar interval must be ordered and frozen before its start")
        for name, value in (("start", start), ("end", end), ("frozen_at", frozen)):
            object.__setattr__(self, name, value)
        if scalar(self.per_day, "per_day") < 0:
            raise ValueError("calendar rate must be nonnegative")


@dataclass(frozen=True)
class Arrival:
    at: datetime
    mark: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "at", aware_utc(self.at, "arrival"))
        if not 0 <= scalar(self.mark, "mark") <= 1:
            raise ValueError("excitation marks must be normalized nonnegative sizes in [0,1]")


@dataclass(frozen=True)
class MarkedHawkes:
    calendar: tuple[CalendarRate, ...]
    events: tuple[Arrival, ...]
    excitation: float
    decay_per_day: float

    def __post_init__(self) -> None:
        if not isinstance(self.calendar, tuple) or not self.calendar:
            raise ValueError("an explicit immutable nonempty calendar is required")
        if not isinstance(self.events, tuple):
            raise TypeError("events must be an immutable tuple")
        if any(a.end > b.start for a, b in pairwise(self.calendar)):
            raise ValueError("calendar must be ordered without overlaps")
        if any(a.at >= b.at for a, b in pairwise(self.events)):
            raise ValueError("events must be strictly ordered with no inferred tie order")
        if not 0 <= scalar(self.excitation, "excitation") < 1:
            raise ValueError("excitation must be in [0,1); marks are bounded by one")
        if scalar(self.decay_per_day, "decay_per_day") <= 0:
            raise ValueError("decay_per_day must be positive")

    def _base_integral(
        self, start: datetime, end: datetime, *, frozen_by: datetime | None = None,
    ) -> float:
        start, end = aware_utc(start), aware_utc(end)
        if start > end:
            raise ValueError("interval must be ordered")
        cursor, total = start, 0.0
        for segment in self.calendar:
            left, right = max(start, segment.start), min(end, segment.end)
            if right <= left:
                continue
            if left != cursor:
                raise ValueError("calendar has missing interval coverage")
            if frozen_by is not None and segment.frozen_at > frozen_by:
                raise ValueError("future calendar rate was not known at the forecast origin")
            total += segment.per_day * (right - left).total_seconds() / DAY
            cursor = right
        if cursor != end:
            raise ValueError("calendar has missing interval coverage")
        if not math.isfinite(total):
            raise FloatingPointError("nonfinite integrated calendar rate")
        return total

    def intensity(self, at: datetime) -> float:
        """Predictable intensity immediately before an event; its own mark is excluded."""
        at = aware_utc(at)
        rates = [s.per_day for s in self.calendar if s.start <= at < s.end]
        if len(rates) != 1:
            raise ValueError("calendar rate is unavailable at the requested instant")
        result = rates[0] + sum(
            self.excitation * self.decay_per_day * e.mark
            * math.exp(-self.decay_per_day * (at - e.at).total_seconds() / DAY)
            for e in self.events if e.at < at)
        if not math.isfinite(result):
            raise FloatingPointError("nonfinite conditional intensity")
        return result

    def _excitation_integral(
        self, start: datetime, end: datetime, history: tuple[Arrival, ...],
    ) -> float:
        beta = self.decay_per_day
        return sum(
            self.excitation * e.mark * (
                math.exp(-beta * (max(start, e.at) - e.at).total_seconds() / DAY)
                - math.exp(-beta * (end - e.at).total_seconds() / DAY))
            for e in history if e.at < end)

    def compensator(self, start: datetime, end: datetime) -> float:
        """Integrated realized-history intensity, including earlier events within the interval."""
        start, end = aware_utc(start), aware_utc(end)
        return self._base_integral(start, end) + self._excitation_integral(start, end, self.events)

    def no_event_probability(self, start: datetime, end: datetime) -> float:
        """Conditional survival: no future realized events or unreleased baseline estimates."""
        start, end = aware_utc(start), aware_utc(end)
        history = tuple(e for e in self.events if e.at <= start)
        integral = self._base_integral(start, end, frozen_by=start)
        integral += self._excitation_integral(start, end, history)
        return math.exp(-integral)

    def log_likelihood(self, start: datetime, end: datetime) -> float:
        """Conditional point-process log likelihood for events in (start,end], in day units."""
        start, end = aware_utc(start), aware_utc(end)
        integral = self.compensator(start, end)
        rates = [self.intensity(e.at) for e in self.events if start < e.at <= end]
        if any(rate <= 0 for rate in rates):
            raise ValueError("observed event has zero intensity under the supplied model")
        return sum(math.log(rate) for rate in rates) - integral

    def rescaled_gaps(self, start: datetime, end: datetime) -> tuple[float, ...]:
        """Compensator increments; Exp(1) interpretation needs a correct complete event model."""
        start, end = aware_utc(start), aware_utc(end)
        self._base_integral(start, end)
        times = (start, *(e.at for e in self.events if start < e.at <= end))
        return tuple(self.compensator(a, b) for a, b in pairwise(times))
