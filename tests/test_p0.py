from datetime import UTC, date, datetime, timedelta
from itertools import product

import pytest

from asof.p0 import (
    acceptance_candidates,
    first_close_options,
    latest_signal_options,
    window_membership_options,
)
from asof.timeutil import close_time_utc


def dt(value):
    return datetime.fromisoformat(value)


@pytest.mark.parametrize(("stored", "expected"), [
    ("2024-01-09T15:00:00Z", ["2024-01-09T10:00:00Z", "2024-01-09T15:00:00Z", "2024-01-09T20:00:00Z"]),
    ("2024-06-12T20:00:00Z", ["2024-06-12T16:00:00Z", "2024-06-12T20:00:00Z", "2024-06-13T00:00:00Z"]),
    ("2006-03-20T20:00:00Z", ["2006-03-20T15:00:00Z", "2006-03-20T20:00:00Z", "2006-03-21T01:00:00Z"]),
])
def test_candidates_use_seasonal_and_historical_rules_without_picking_authority(stored, expected):
    result = acceptance_candidates(dt(stored))
    assert result.instants == tuple(map(dt, expected))
    assert result.issues == ()


def test_fall_folds_remain_distinct_and_spring_gap_is_not_shifted():
    fall = acceptance_candidates(dt("2024-11-03T01:30:00Z"))
    assert fall.instants == tuple(map(dt, [
        "2024-11-02T21:30:00Z", "2024-11-03T01:30:00Z",
        "2024-11-03T05:30:00Z", "2024-11-03T06:30:00Z",
    ]))
    assert fall.issues == ("ambiguous_ET_wall_clock",)
    spring = acceptance_candidates(dt("2024-03-10T02:30:00Z"))
    assert spring.instants == tuple(map(dt, ["2024-03-09T21:30:00Z", "2024-03-10T02:30:00Z"]))
    assert spring.issues == ("nonexistent_ET_wall_clock",)


def test_clock_self_consistency_when_shift_crosses_dst_transition():
    stored = dt("2024-03-10T07:30:00Z")
    result = acceptance_candidates(stored)
    late = [b.instant for b in result.branches if b.interpretation == "late_correction"]
    assert late == [dt("2024-03-10T02:30:00Z")]  # corrected instant is still EST


def test_strict_close_month_end_and_finite_tail():
    closes = [close_time_utc(d) for d in (date(2024, 5, 31), date(2024, 6, 3))]
    candidates = acceptance_candidates(dt("2024-05-31T19:00:00Z")).instants
    assert first_close_options(candidates, closes) == tuple(closes)
    assert first_close_options([closes[0] - timedelta(seconds=1)], closes) == (closes[0],)
    assert first_close_options([closes[0]], closes) == (closes[1],)
    assert first_close_options([closes[1]], closes) == (None,)


def test_latest_order_can_change_even_when_eligibility_and_close_do_not():
    close = dt("2024-06-28T20:00:00Z")
    a = acceptance_candidates(dt("2024-06-12T15:00:00Z")).instants
    b = [dt("2024-06-12T16:00:00Z")]
    assert latest_signal_options([("A", a), ("B", b)], close, max_age_days=365) == ("A", "B")
    assert latest_signal_options([("A", b), ("B", b)], close, max_age_days=365) == ("B",)


def test_latest_365day_lower_bound_and_no_signal_are_not_zero():
    close = dt("2024-06-28T20:00:00Z")
    choices = [close - timedelta(days=365, seconds=1), close - timedelta(days=365), close]
    assert latest_signal_options([("A", choices)], close, max_age_days=365) == ("A", None)
    assert latest_signal_options([], close, max_age_days=365) == (None,)


def test_development_filter_and_latest_formation_are_joint_not_posthoc():
    close = dt("2024-07-31T20:00:00Z")
    a = [dt("2024-06-30T22:00:00Z"), dt("2024-07-01T02:00:00Z")]
    window = (dt("2023-01-01T00:00:00Z"), dt("2024-07-01T00:00:00Z"))
    assert latest_signal_options([("A", a)], close, max_age_days=365,
                                 signal_window=window) == ("A", None)


def test_latest_analytic_options_match_joint_enumeration():
    close = dt("2024-06-28T20:00:00Z")
    records = [
        ("A", [close - timedelta(days=1), close]),
        ("B", [close - timedelta(hours=2), close - timedelta(days=366)]),
        ("C", [close - timedelta(hours=4), close - timedelta(hours=1)]),
    ]
    expected = set()
    for times in product(*(t for _, t in records)):
        eligible = [(t, i, records[i][0]) for i, t in enumerate(times)
                    if close - timedelta(days=365) <= t < close]
        expected.add(max(eligible)[2] if eligible else None)
    assert set(latest_signal_options(records, close, max_age_days=365)) == expected


def test_prior120_and_future365_exact_operators_and_joint_clocks():
    focal = dt("2024-06-01T16:00:00Z")
    prior = acceptance_candidates(dt("2024-02-02T16:00:00Z")).instants
    assert window_membership_options([focal], prior, window="prior_120d") == (False, True)
    old = dt("2023-06-01T16:00:00Z")
    endpoint = acceptance_candidates(dt("2024-05-31T16:00:00Z")).instants
    assert window_membership_options([old], endpoint, window="future_365d") == (False, True)
    assert window_membership_options([old], [old], window="future_365d") == (False,)
    assert window_membership_options([old], [old + timedelta(days=365)], window="future_365d") == (True,)
    assert window_membership_options([old, old + timedelta(hours=1)],
                                     [old + timedelta(days=365, minutes=30)],
                                     window="future_365d") == (False, True)


def test_invalid_input_does_not_create_success_shaped_candidates():
    with pytest.raises(ValueError, match="timezone-aware"):
        acceptance_candidates(datetime(2024, 1, 1))
    with pytest.raises(ValueError, match="empty"):
        first_close_options([], [])
    with pytest.raises(ValueError, match="one record"):
        latest_signal_options([("A", [datetime.now(UTC)]), ("A", [datetime.now(UTC)])],
                              datetime.now(UTC), max_age_days=365)
