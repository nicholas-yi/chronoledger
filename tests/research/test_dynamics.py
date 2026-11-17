import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from asof.research.arrivals import Arrival, CalendarRate, MarkedHawkes
from asof.research.trajectories import causal_trajectory, signature2

T = datetime(2016, 1, 1, tzinfo=UTC)


def clock(days: float) -> datetime:
    return T + timedelta(days=days)


def process(events: tuple[Arrival, ...] = ()) -> MarkedHawkes:
    return MarkedHawkes((CalendarRate(T, clock(10), 1, clock(-1)),), events, 0.2, 1)


def test_hawkes_calendar_and_excitation_have_independent_closed_form_integrals() -> None:
    h = process((Arrival(T, 1),))
    # Current events cannot excite themselves; history at the conditioning origin can excite survival.
    assert h.intensity(T) == 1
    assert h.intensity(clock(1)) == pytest.approx(1 + 0.2 / math.e)
    integral = 1 + 0.2 * (1 - math.exp(-1))
    assert h.compensator(T, clock(1)) == pytest.approx(integral)
    assert h.no_event_probability(T, clock(1)) == pytest.approx(math.exp(-integral))
    poisson = MarkedHawkes(h.calendar, (Arrival(clock(1), 0), Arrival(clock(3), 0)), 0, 1)
    assert poisson.log_likelihood(T, clock(4)) == -4
    assert poisson.rescaled_gaps(T, clock(4)) == (1, 2)


def test_survival_does_not_condition_on_future_realized_events_or_future_baseline_estimates() -> None:
    old = process((Arrival(T, 1),))
    future = process((*old.events, Arrival(clock(0.5), 1)))
    assert old.no_event_probability(T, clock(2)) == future.no_event_probability(T, clock(2))
    assert old.intensity(clock(0.25)) == future.intensity(clock(0.25))
    assert future.compensator(T, clock(2)) > old.compensator(T, clock(2))
    calendar = (CalendarRate(T, clock(1), 1, clock(-1)),
                CalendarRate(clock(1), clock(3), 2, clock(0.5)))
    h = MarkedHawkes(calendar, (), 0, 1)
    with pytest.raises(ValueError, match="not known"):
        h.no_event_probability(T, clock(2))


def test_missing_calendar_ties_and_invalid_intensities_fail_explicitly() -> None:
    h = MarkedHawkes((CalendarRate(T, clock(1), 0, T),), (Arrival(clock(0.5), 1),), 0, 1)
    with pytest.raises(ValueError, match="zero intensity"):
        h.log_likelihood(T, clock(0.75))
    with pytest.raises(ValueError, match="coverage"):
        h.compensator(T, clock(2))
    with pytest.raises(ValueError, match="tie order"):
        process((Arrival(T, 1), Arrival(T, 0.5)))
    with pytest.raises(ValueError, match="excitation"):
        replace(process(), excitation=1)
    with pytest.raises(ValueError, match="normalized"):
        Arrival(T, -1)
    with pytest.raises(ValueError, match="timezone-aware"):
        Arrival(T.replace(tzinfo=None), 1)


def test_signature_order_shuffle_and_chen_concatenation_match_analytic_paths() -> None:
    first = signature2([[0, 0], [1, 0], [1, -1]])
    reverse = signature2([[0, 0], [0, -1], [1, -1]])
    np.testing.assert_array_equal(first.increment, reverse.increment)
    assert first.area()[0, 1] == -0.5
    assert reverse.area()[0, 1] == 0.5
    np.testing.assert_allclose(first.second + first.second.T,
                               np.outer(first.increment, first.increment))
    concatenated = signature2([[0, 0], [1, 0]]).concatenate(signature2([[0, 0], [0, -1]]))
    np.testing.assert_array_equal(concatenated.features(), first.features())
    translated = signature2([[10, 20], [11, 20], [11, 19]])
    np.testing.assert_array_equal(translated.features(), first.features())


def test_causal_path_keeps_initial_levels_time_and_ignores_future_values() -> None:
    times = (T, clock(1), clock(2))
    short = causal_trajectory(times[:2], [[10, 20], [11, 19]], as_of=clock(1))
    full = causal_trajectory(times, [[10, 20], [11, 19], [None, "future"]], as_of=clock(1))
    np.testing.assert_array_equal(short.signature.features(), full.signature.features())
    np.testing.assert_array_equal(full.initial_state, [10, 20])
    assert full.elapsed_days == 1 and len(full.signature.features()) == 13
    assert len(causal_trajectory(times[:1], [[1, 2, 3, 4]], as_of=T).signature.features()) == 31
    with pytest.raises(ValueError, match="unique"):
        causal_trajectory([T, T], [[1], [2]], as_of=T)
    with pytest.raises(ValueError, match="no eligible"):
        causal_trajectory([T], [[1]], as_of=clock(-1))
    with pytest.raises((TypeError, ValueError), match="finite|numeric"):
        causal_trajectory([T], [[np.nan]], as_of=T)
