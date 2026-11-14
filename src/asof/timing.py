"""Opt-in synthetic scheduled-window planning, separate from historical research runners."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from typing import Literal

from asof.periods import price_end_allowed

PlanStatus = Literal["complete", "missing", "unavailable", "censored"]


@dataclass(frozen=True)
class ReturnSlot:
    offset: int
    start: datetime | None
    end: datetime | None
    status: PlanStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReturnWindowPlan:
    information_ready: datetime
    observation_cutoff: datetime
    anchor: datetime | None
    order_deadline: datetime | None
    anchor_reasons: tuple[str, ...]
    estimation: tuple[ReturnSlot, ...]
    outcome: tuple[ReturnSlot, ...]
    status: PlanStatus

    @property
    def estimation_support(self) -> int:
        return sum(slot.status == "complete" for slot in self.estimation)

    @property
    def outcome_support(self) -> int:
        return sum(slot.status == "complete" for slot in self.outcome)


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def plan_return_window(
    session_closes: Sequence[datetime],
    information_ready: datetime,
    *,
    observation_cutoff: datetime,
    firm_closes: Collection[datetime],
    factor_closes: Collection[datetime],
    horizon: int,
    estimation_offsets: tuple[int, int],
    order_deadlines: Mapping[datetime, datetime] | None = None,
) -> ReturnWindowPlan:
    """Plan hypothetical entry at the first eligible supplied close, with no I/O or fitting.

    Firm timestamps assert available closing observations. A return ending at a session needs
    both adjacent firm closes and that session's complete factor/RF row. Neither prices nor
    returns are consumed or computed. Offsets are scheduled slots relative to entry; estimation
    offsets must be negative and outcome offsets are +1..+horizon.

    All instants are compared and returned in UTC. Supplied deadlines apply strictly where
    present; absent deadlines remain unknown. No plan, even complete with a deadline, establishes
    order, fill or borrow feasibility. Missing support never changes the anchor or slot bounds.
    """
    ready = _utc(information_ready, "information_ready")
    cutoff = _utc(observation_cutoff, "observation_cutoff")
    price_end_allowed(cutoff.date())
    closes = tuple(_utc(t, "session close") for t in session_closes)
    if any(a >= b for a, b in pairwise(closes)):
        raise ValueError("session_closes must be strictly increasing and unique in UTC")
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    if (len(estimation_offsets) != 2
            or any(isinstance(v, bool) or not isinstance(v, int) for v in estimation_offsets)
            or not estimation_offsets[0] <= estimation_offsets[1] < 0):
        raise ValueError("estimation_offsets must be two ordered negative integer offsets")
    calendar = set(closes)
    deadlines = {}
    for session, deadline in (order_deadlines or {}).items():
        session, deadline = _utc(session, "deadline session"), _utc(deadline, "order deadline")
        if session not in calendar or deadline > session:
            raise ValueError("each order deadline must belong to a supplied session and not exceed its close")
        deadlines[session] = deadline

    def observations(values: Collection[datetime], name: str) -> set[datetime]:
        result = {_utc(t, name) for t in values}
        if not result <= calendar:
            raise ValueError(f"{name} contains timestamps outside session_closes")
        if any(t > cutoff for t in result):
            raise ValueError(f"{name} must not contain observations after observation_cutoff")
        return result

    firm = observations(firm_closes, "firm_closes")
    factors = observations(factor_closes, "factor_closes")
    anchor_index = next((
        i for i, close in enumerate(closes)
        if ready < close and (close not in deadlines or ready < deadlines[close])
    ), None)
    anchor = None if anchor_index is None else closes[anchor_index]
    if anchor is None:
        anchor_reasons = ("no_eligible_close",)
    elif anchor > cutoff:
        anchor_reasons = ("anchor_after_observation_cutoff",)
    elif anchor not in firm:
        anchor_reasons = ("missing_anchor_close",)
    else:
        anchor_reasons = ()

    def slot(offset: int) -> ReturnSlot:
        if anchor_index is None:
            return ReturnSlot(offset, None, None, "unavailable", ("no_eligible_close",))
        first, last = anchor_index + offset - 1, anchor_index + offset
        start = closes[first] if 0 <= first < len(closes) else None
        end = closes[last] if 0 <= last < len(closes) else None
        reasons = []
        if start is None:
            reasons.append("start_outside_schedule")
        if end is None:
            reasons.append("end_outside_schedule")
        if (start is not None and start > cutoff) or (end is not None and end > cutoff):
            return ReturnSlot(offset, start, end, "censored",
                              (*reasons, "after_observation_cutoff"))
        if start is None or end is None:
            return ReturnSlot(offset, start, end, "unavailable", tuple(reasons))
        if start not in firm:
            reasons.append("missing_firm_start")
        if end not in firm:
            reasons.append("missing_firm_end")
        if end not in factors:
            reasons.append("missing_factor_row")
        return ReturnSlot(offset, start, end, "missing" if reasons else "complete", tuple(reasons))

    estimation = tuple(slot(i) for i in range(estimation_offsets[0], estimation_offsets[1] + 1))
    outcome = tuple(slot(i) for i in range(1, horizon + 1))
    statuses = {s.status for s in (*estimation, *outcome)}
    status: PlanStatus
    if "censored" in statuses or anchor_reasons == ("anchor_after_observation_cutoff",):
        status = "censored"
    elif "unavailable" in statuses or anchor is None:
        status = "unavailable"
    elif "missing" in statuses or anchor_reasons:
        status = "missing"
    else:
        status = "complete"
    return ReturnWindowPlan(ready, cutoff, anchor, deadlines.get(anchor) if anchor else None,
                            anchor_reasons, estimation, outcome, status)
