"""Exact interval reconciliation for declared compatible facts, not an XBRL processor.

Inspired by Calculations 1.1: no taxonomy parsing, arcrole resolution, OIM validation,
cross-period inference or financial truth certification. No I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext
from typing import Literal

PRECISION = 1024


def _decimal(value: Decimal | str, name: str) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise TypeError(f"{name} requires an exact decimal string or Decimal, not a float")
    result = Decimal(value)
    if (not result.is_finite() or len(result.as_tuple().digits) > 128
            or abs(result.as_tuple().exponent) > 100):
        raise ValueError(f"{name} must be finite with at most 128 digits and exponent in [-100,100]")
    return result


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


@dataclass(frozen=True)
class AccountingContext:
    entity: str
    unit: str
    period_end: date
    period_start: date | None = None
    dimensions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _text(self.entity, "entity")
        _text(self.unit, "unit")
        for value in (self.period_start, self.period_end):
            if value is not None and (not isinstance(value, date) or isinstance(value, datetime)):
                raise TypeError("periods require explicit dates, not timestamps")
        if self.period_end is None or (
                self.period_start is not None and self.period_start > self.period_end):
            raise ValueError("valid instant or ordered duration period required")
        if (not isinstance(self.dimensions, tuple)
                or any(not isinstance(item, tuple) or len(item) != 2 for item in self.dimensions)):
            raise TypeError("dimensions must be immutable axis/member pairs")
        for axis, member in self.dimensions:
            _text(axis, "dimension axis")
            _text(member, "dimension member")
        if len({axis for axis, _ in self.dimensions}) != len(self.dimensions):
            raise ValueError("duplicate dimension axis")
        object.__setattr__(self, "dimensions", tuple(sorted(self.dimensions)))


@dataclass(frozen=True)
class Interval:
    lower: Decimal
    upper: Decimal
    lower_closed: bool = True
    upper_closed: bool = True

    def __post_init__(self) -> None:
        if (not isinstance(self.lower, Decimal) or not isinstance(self.upper, Decimal)
                or not self.lower.is_finite() or not self.upper.is_finite()):
            raise TypeError("interval endpoints must be finite Decimals")
        if not isinstance(self.lower_closed, bool) or not isinstance(self.upper_closed, bool):
            raise TypeError("endpoint inclusion must be boolean")
        if self.lower > self.upper or (self.lower == self.upper
                                       and not (self.lower_closed and self.upper_closed)):
            raise ValueError("empty interval")

    def intersection(self, other: Interval) -> Interval | None:
        lower, upper = max(self.lower, other.lower), min(self.upper, other.upper)
        lc = (self.lower_closed if lower == self.lower else True) and (
            other.lower_closed if lower == other.lower else True)
        uc = (self.upper_closed if upper == self.upper else True) and (
            other.upper_closed if upper == other.upper else True)
        if lower > upper or (lower == upper and not (lc and uc)):
            return None
        return Interval(lower, upper, lc, uc)


@dataclass(frozen=True)
class ReportedFact:
    concept: str
    context: AccountingContext
    value: Decimal | str | None
    source_id: str
    decimals: int | None = None
    scale: int = 0
    rounding: Literal["nearest", "truncate"] = "nearest"

    def __post_init__(self) -> None:
        _text(self.concept, "concept")
        _text(self.source_id, "source_id")
        if not isinstance(self.context, AccountingContext):
            raise TypeError("typed accounting context required")
        if self.decimals is not None and (
                isinstance(self.decimals, bool) or not isinstance(self.decimals, int)
                or not -18 <= self.decimals <= 18):
            raise ValueError("decimals must be None (exact) or an integer in [-18,18]")
        if isinstance(self.scale, bool) or not isinstance(self.scale, int) or not -18 <= self.scale <= 18:
            raise ValueError("scale must be an integer in [-18,18]")
        if self.rounding not in ("nearest", "truncate"):
            raise ValueError("rounding must be nearest or truncate")
        if self.value is not None:
            object.__setattr__(self, "value", _decimal(self.value, "reported value"))

    def interval(self) -> Interval | None:
        """None is nil/missing. Decimals describes displayed precision; scale converts to base units."""
        if self.value is None:
            return None
        value = _decimal(self.value, "reported value")
        with localcontext() as ctx:
            ctx.prec = PRECISION
            multiplier = Decimal(10) ** self.scale
            canonical = value * multiplier
            if self.decimals is None:
                return Interval(canonical, canonical)
            quantum = Decimal(10) ** -self.decimals
            if value % quantum != 0:
                raise ValueError("reported value has digits beyond declared precision")
            width = quantum * multiplier
            if self.rounding == "nearest":
                # Conservative closed ties: no specific tie-breaking rule is asserted.
                return Interval(canonical - width / 2, canonical + width / 2)
            if canonical > 0:
                return Interval(canonical, canonical + width, True, False)
            if canonical < 0:
                return Interval(canonical - width, canonical, False, True)
            return Interval(-width, width, False, False)


@dataclass(frozen=True)
class Reconciliation:
    status: Literal["consistent", "inconsistent", "unavailable"]
    reasons: tuple[str, ...]
    total_interval: Interval | None = None
    calculated_interval: Interval | None = None
    duplicate_concepts: tuple[str, ...] = ()


def reconcile(
    facts: Sequence[ReportedFact], *, context: AccountingContext, total: str,
    contributions: Sequence[tuple[str, Decimal | str]],
) -> Reconciliation:
    """Check existence of compatible values satisfying one supplied weighted sum.

    This validates a declared relationship only, never discovers or proves it. A mismatch
    is not fraud and compatibility is not truth. Incomplete/mixed contexts stay unavailable.
    """
    if not isinstance(context, AccountingContext):
        raise TypeError("typed target context required")
    _text(total, "total concept")
    if not contributions or len(contributions) > 256:
        raise ValueError("one through 256 contribution terms required")
    terms = tuple((name, _decimal(weight, "contribution weight")) for name, weight in contributions)
    for name, weight in terms:
        _text(name, "contribution concept")
        if weight == 0:
            raise ValueError("zero contribution is not a required accounting term")
    names = (total, *(name for name, _ in terms))
    if len(set(names)) != len(names):
        raise ValueError("total/contribution concepts must be unique")
    if any(not isinstance(fact, ReportedFact) for fact in facts):
        raise TypeError("facts must be ReportedFact records")
    selected = {name: [f for f in facts if f.concept == name and f.context == context]
                for name in names}
    missing = tuple(f"missing_compatible_fact:{name}" for name, rows in selected.items() if not rows)
    if missing:
        return Reconciliation("unavailable", missing)
    duplicates = tuple(name for name, rows in selected.items() if len(rows) > 1)
    intervals: dict[str, Interval] = {}
    for name, rows in selected.items():
        if len({f.source_id for f in rows}) != len(rows):
            raise ValueError("duplicate source record would repeat the same accounting evidence")
        merged: Interval | None = None
        for fact in rows:
            interval = fact.interval()
            if interval is None:
                return Reconciliation("unavailable", (f"nil_fact:{name}",),
                                      duplicate_concepts=duplicates)
            if merged is None:
                merged = interval
            else:
                merged = merged.intersection(interval)
                if merged is None:
                    return Reconciliation("inconsistent", (f"conflicting_duplicates:{name}",),
                                          duplicate_concepts=duplicates)
        if merged is None:
            raise RuntimeError("nonempty compatible evidence did not produce an interval")
        intervals[name] = merged
    lower = upper = Decimal(0)
    lc = uc = True
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for name, weight in terms:
            interval = intervals[name]
            if weight > 0:
                lower += weight * interval.lower
                upper += weight * interval.upper
                lc, uc = lc and interval.lower_closed, uc and interval.upper_closed
            else:
                lower += weight * interval.upper
                upper += weight * interval.lower
                lc, uc = lc and interval.upper_closed, uc and interval.lower_closed
    calculated = Interval(lower, upper, lc, uc)
    compatible = intervals[total].intersection(calculated) is not None
    return Reconciliation("consistent" if compatible else "inconsistent",
                          ("overlapping_intervals" if compatible else "disjoint_intervals",),
                          intervals[total], calculated, duplicates)
