from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from asof.research.economic import (
    MetricKey,
    Observation,
    numeric_update,
    public_innovation,
    state_as_of,
    update_belief,
)
from asof.research.pricing import campbell_news, physical_probabilities, pricing_moments

T = datetime(2016, 2, 1, tzinfo=UTC)
KEY = MetricKey("INVENTED", "contract_backlog", "USD", "consolidated", "definition-v1")


def observation(value: float | None, day: int, **kwargs) -> Observation:
    return Observation(KEY, date(2015, 12, 31), T + timedelta(days=day),
                       f"invented-source-{day}", value, **kwargs)


def test_asof_state_distinguishes_prior_public_value_revisions_and_unavailability() -> None:
    first, revision, reversion = observation(10, 0), observation(20, 1), observation(10, 2)
    repeat = replace(first, known_at=T + timedelta(hours=1), source_id="invented-annual-repeat")
    assert public_innovation(repeat, [first]).status == "already_public"
    assert public_innovation(reversion, [first, revision]).status == "new_observed_value"
    assert state_as_of([first, revision], T)[(KEY, first.period_end)] == first
    missing = observation(None, 3, coverage="source_missing", reason="invented unreadable source")
    state = state_as_of([first, revision, missing], missing.known_at)
    assert state[(KEY, first.period_end)].value is None
    assert public_innovation(observation(20, 4), [revision, missing]).status == "unavailable"
    assert numeric_update(revision, first) == 10
    with pytest.raises(ValueError, match="unavailable"):
        numeric_update(missing, first)


def test_economic_identity_and_simultaneous_conflicts_are_not_silently_matched() -> None:
    first = observation(10, 0)
    with pytest.raises(ValueError, match="definition"):
        numeric_update(replace(observation(20, 1), key=replace(KEY, definition="v2")), first)
    with pytest.raises(ValueError, match="conflicting"):
        state_as_of([first, replace(first, source_id="other", value=9)], T)
    with pytest.raises(ValueError, match="duplicate"):
        state_as_of([first, first], T)
    same = replace(first, source_id="another-source")
    assert state_as_of([first, same], T) == state_as_of([same, first], T)
    with pytest.raises(ValueError, match="require a value"):
        observation(None, 0)
    with pytest.raises(ValueError, match="no numeric value"):
        observation(0, 0, coverage="not_issuer_specific", reason="industry metric")
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(first, known_at=T.replace(tzinfo=None))
    with pytest.raises(ValueError, match="period"):
        replace(first, period_end=date(2017, 1, 1))


def test_informative_silence_is_a_bayesian_update_but_missing_source_is_not_silence() -> None:
    transition = np.eye(2)
    silent = update_belief([0.5, 0.5], transition, observation="silent",
                          disclosure_probability=[0.2, 0.8])
    np.testing.assert_allclose(silent.posterior, [0.8, 0.2])
    assert silent.evidence_probability == pytest.approx(0.5)
    observed = update_belief(
        [0.5, 0.5], transition, observation="observed",
        disclosure_probability=[0.2, 0.8], emission_probability=[0.1, 0.9])
    np.testing.assert_allclose(observed.posterior, [1 / 37, 36 / 37])
    for reason in ("unavailable", "no_opportunity"):
        result = update_belief([0.5, 0.5], transition, observation=reason)
        np.testing.assert_allclose(result.posterior, [0.5, 0.5])
        assert result.evidence_probability is None
    with pytest.raises(ValueError, match="zero probability"):
        update_belief([0.5, 0.5], transition, observation="silent",
                      disclosure_probability=[1, 1])
    with pytest.raises(ValueError, match="cannot consume"):
        update_belief([0.5, 0.5], transition, observation="unavailable",
                      disclosure_probability=[0.2, 0.8])
    with pytest.raises(ValueError, match="transition rows"):
        update_belief([0.5, 0.5], [[1, 1], [0, 1]], observation="unavailable")


def test_var_news_matches_the_scalar_geometric_series_and_measures_are_not_equal() -> None:
    news = campbell_news([[0.8]], [0.1], [1], rho=0.9)
    assert news.discount_rate_news == pytest.approx(0.1 * 0.72 / (1 - 0.72))
    assert news.cash_flow_news - news.discount_rate_news == pytest.approx(news.unexpected_return)
    np.testing.assert_allclose(physical_probabilities([0.5, 0.5], [2, 1]), [1 / 3, 2 / 3])
    np.testing.assert_allclose(physical_probabilities([0.5, 0.5], [1e-309, 1e-309]), [0.5, 0.5])
    np.testing.assert_allclose(physical_probabilities([0, 1], [1e-309, 1e-309]), [0, 1])
    np.testing.assert_allclose(pricing_moments([[1], [-1]], [1, 1]), [0])
    with pytest.raises(ValueError, match="does not converge"):
        campbell_news([[2]], [1], [1], rho=0.9)
    with pytest.raises(ValueError, match="strictly positive"):
        physical_probabilities([0.5, 0.5], [0, 1])
    with pytest.raises(ValueError, match="finite"):
        pricing_moments([[1], [np.nan]], [1, 1])
