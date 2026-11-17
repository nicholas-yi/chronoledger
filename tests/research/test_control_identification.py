import math

import numpy as np
import pytest

from asof.research.control import robust_decay_plan
from asof.research.identification import OutcomeBound, mean_bounds, payoff_bounds


def plan(mean, persistence, cost, horizon, radius, *, previous=None, ambiguity=None):
    n = len(mean)
    return robust_decay_plan(
        mean, persistence, np.eye(n), cost, np.zeros(n) if previous is None else previous,
        horizon=horizon, risk_aversion=1, discount=1,
        mean_ambiguity=np.eye(n * horizon) if ambiguity is None else ambiguity,
        ambiguity_radius=radius)


def test_finite_horizon_turnover_solution_matches_independent_two_variable_equations() -> None:
    result = plan([1], [[0.5]], [[1]], 2, 0)
    # Minimize .5*(w0^2+w1^2+w0^2+(w1-w0)^2)-w0-.5*w1.
    expected = np.linalg.solve([[3, -1], [-1, 2]], [1, 0.5])
    np.testing.assert_allclose(result.positions[:, 0], expected)
    frictionless = plan([1], [[0.5]], [[0]], 2, 0)
    np.testing.assert_allclose(frictionless.positions[:, 0], [1, 0.5])
    assert result.stationarity_error < 1e-10


def test_joint_ellipsoid_matches_group_soft_threshold_and_scalar_threshold() -> None:
    result = plan([1], [[0.5]], [[0]], 2, 0.4)
    mu = np.array([1.0, 0.5])
    expected = mu * (1 - 0.4 / np.linalg.norm(mu))
    np.testing.assert_allclose(result.positions[:, 0], expected, atol=1e-10)
    assert result.uncertainty_penalty == pytest.approx(0.4 * np.linalg.norm(expected))
    assert result.worst_case_utility == pytest.approx(
        expected @ mu - 0.5 * expected @ expected - 0.4 * np.linalg.norm(expected))
    zero = plan([1], [[0.5]], [[0]], 2, 2)
    np.testing.assert_array_equal(zero.positions, np.zeros((2, 1)))
    scalar = plan([0.5], [[1]], [[2]], 1, 0.1, previous=[0.2])
    assert scalar.positions[0, 0] == pytest.approx((0.5 + 2 * 0.2 - 0.1) / 3)


def test_correlated_ambiguity_plan_satisfies_an_independent_objective_gradient() -> None:
    means = np.array([0.6, -0.3])
    v = np.array([[0.5, 0.1], [0.1, 0.4]])
    result = plan(means, np.eye(2), np.diag([0.2, 0.4]), 1, 0.2, ambiguity=v)
    w = result.positions[0]
    gradient = w - means + np.diag([0.2, 0.4]) @ w + 0.2 * v @ w / np.sqrt(w @ v @ w)
    np.testing.assert_allclose(gradient, np.zeros(2), atol=1e-9)
    assert result.stationarity_error < 1e-9


@pytest.mark.parametrize("override", [
    {"horizon": 0}, {"risk_aversion": 0}, {"ambiguity_radius": -1},
    {"mean_ambiguity": [[0]]}, {"covariance_matrix": [[-1]]},
    {"turnover_cost": [[-1]]}, {"persistence": [[1.1]]},
    {"initial_mean": [math.nan]},
])
def test_invalid_control_inputs_do_not_produce_a_position(override) -> None:
    args = {
        "initial_mean": [1], "persistence": [[0.5]], "covariance_matrix": [[1]],
        "turnover_cost": [[0]], "previous_position": [0], "horizon": 1,
        "risk_aversion": 1, "discount": 1, "mean_ambiguity": [[1]], "ambiguity_radius": 0.1,
    }
    args.update(override)
    with pytest.raises((ValueError, TypeError)):
        robust_decay_plan(**args)


def test_missing_short_return_has_unbounded_loss_without_an_invented_upper_cap() -> None:
    missing = OutcomeBound(-1, math.inf, False, "only simple-long limited liability assumed")
    known = OutcomeBound(0.1, 0.1, True, "invented observed outcome")
    long = payoff_bounds([1], [missing])
    assert long.lower == -1 and long.upper == math.inf and long.unbounded
    spread = payoff_bounds([1, -1], [known, missing])
    assert spread.lower == -math.inf and spread.upper == pytest.approx(1.1)
    assert spread.unobserved == 1
    no_exposure = payoff_bounds([0], [missing])
    assert no_exposure.lower == no_exposure.upper == 0
    assert no_exposure.unobserved == 1


def test_finite_population_bounds_include_entirely_missing_and_unknown_denominators() -> None:
    result = mean_bounds([0.1, 0.2], missing_count=2, lower=-1, upper=1, reason="invented support")
    assert (result.lower, result.upper) == pytest.approx((-0.425, 0.575))
    unknown = mean_bounds([], missing_count=3, lower=-1, upper=math.inf, reason="unbounded")
    assert unknown.lower == -1 and unknown.upper == math.inf and unknown.unobserved == 3
    with pytest.raises(ValueError, match="population cannot be empty"):
        mean_bounds([], missing_count=0, lower=-1, upper=1, reason="support")
    with pytest.raises(ValueError, match="contradict"):
        mean_bounds([2], missing_count=1, lower=-1, upper=1, reason="unsupported cap")
    with pytest.raises(ValueError, match="NaN"):
        OutcomeBound(math.nan, 1, False, "not a bound")
