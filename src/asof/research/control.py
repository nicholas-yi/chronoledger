"""G: convex open-loop planning with decay, quadratic costs and ellipsoidal mean ambiguity."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.linalg import solve
from scipy.optimize import brentq

from ._validation import FloatArray, covariance, matrix, readonly, scalar, vector


@dataclass(frozen=True)
class ControlPlan:
    positions: FloatArray
    expected_means: FloatArray
    nominal_utility: float
    uncertainty_penalty: float
    worst_case_utility: float
    stationarity_error: float


def _robust_quadratic(
    hessian: FloatArray, linear: FloatArray, ambiguity: FloatArray, radius: float,
) -> tuple[FloatArray, float]:
    """Solve 1/2*w'Hw-b'w+rho*sqrt(w'Vw), with H,V positive definite."""
    if radius == 0:
        weights = solve(hessian, linear, assume_a="pos")
    else:
        dual_norm = float(np.sqrt(linear @ solve(ambiguity, linear, assume_a="pos")))
        if dual_norm <= radius:
            return np.zeros_like(linear), max(0.0, dual_norm - radius)

        # t=eta/(1+eta) avoids an unbounded root search near the zero-position threshold.
        def transformed(t: float) -> tuple[FloatArray, float]:
            v = solve((1 - t) * hessian + t * ambiguity, linear, assume_a="pos")
            return v, t * float(np.sqrt(v @ ambiguity @ v)) - radius

        root = brentq(lambda t: transformed(t)[1], 0, 1, xtol=1e-14)
        v, _ = transformed(root)
        weights = (1 - root) * v
    norm = float(np.sqrt(weights @ ambiguity @ weights))
    gradient = hessian @ weights - linear
    if radius and norm:
        gradient += radius * (ambiguity @ weights) / norm
    error = float(np.linalg.norm(gradient, ord=np.inf))
    if not np.isfinite(weights).all() or error > 1e-8 * max(1.0, float(np.linalg.norm(linear))):
        raise FloatingPointError("robust quadratic solver failed its stationarity check")
    return weights, error


def robust_decay_plan(
    initial_mean: ArrayLike, persistence: ArrayLike, covariance_matrix: ArrayLike,
    turnover_cost: ArrayLike, previous_position: ArrayLike, *,
    horizon: int, risk_aversion: float, discount: float,
    mean_ambiguity: ArrayLike, ambiguity_radius: float,
) -> ControlPlan:
    """Exact unconstrained reference solution, not an executable or calibrated portfolio.

    Forecast means are persistence**k * initial_mean, known at the planning origin.
    mean_ambiguity is SPD covariance/geometry of stacked mean errors, NOT return covariance.
    One joint ellipsoid spans the horizon; it is not per-period rectangular ambiguity.
    There are no leverage, financing, borrow, position or execution-feasibility constraints.
    """
    mean = vector(initial_mean, "initial_mean")
    n = len(mean)
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 256:
        raise ValueError("horizon must be an integer in [1,256]")
    if n * horizon > 256:
        raise ValueError("dense reference plan is limited to 256 total position coordinates")
    dynamics = matrix(persistence, "persistence", (n, n))
    if np.max(np.abs(np.linalg.eigvals(dynamics))) > 1:
        raise ValueError("persistence spectral radius must not exceed one")
    sigma = covariance(covariance_matrix, "return covariance", n, definite=True)
    cost = covariance(turnover_cost, "turnover cost", n, definite=False)
    previous = vector(previous_position, "previous_position", n)
    gamma, beta = scalar(risk_aversion, "risk_aversion"), scalar(discount, "discount")
    radius = scalar(ambiguity_radius, "ambiguity_radius")
    if gamma <= 0 or not 0 < beta <= 1 or radius < 0:
        raise ValueError("risk aversion>0, discount in (0,1] and radius>=0 are required")
    dimension = n * horizon
    uncertainty = covariance(mean_ambiguity, "mean_ambiguity", dimension, definite=True)
    means = [mean]
    for _ in range(1, horizon):
        means.append(dynamics @ means[-1])
    expected = np.stack(means)
    if not np.isfinite(expected).all():
        raise FloatingPointError("nonfinite expected mean path")
    scales = np.repeat(beta ** np.arange(horizon), n)
    if (scales == 0).any():
        raise FloatingPointError("discount weights underflow at the requested horizon")
    hessian = np.zeros((dimension, dimension))
    linear = (expected * (beta ** np.arange(horizon))[:, None]).ravel()
    linear[:n] += cost @ previous
    for t in range(horizon):
        here = slice(t * n, (t + 1) * n)
        hessian[here, here] += beta**t * (gamma * sigma + cost)
        if t:
            before = slice((t - 1) * n, t * n)
            hessian[before, before] += beta**t * cost
            hessian[here, before] -= beta**t * cost
            hessian[before, here] -= beta**t * cost
    weighted_ambiguity = uncertainty * np.outer(scales, scales)
    flat, error = _robust_quadratic(hessian, linear, weighted_ambiguity, radius)
    positions = flat.reshape(horizon, n)
    nominal = 0.0
    old = previous
    for t, (weights, forecast) in enumerate(zip(positions, expected, strict=True)):
        delta = weights - old
        nominal += beta**t * float(
            weights @ forecast - gamma / 2 * weights @ sigma @ weights
            - 0.5 * delta @ cost @ delta)
        old = weights
    penalty = radius * float(np.sqrt(flat @ weighted_ambiguity @ flat))
    return ControlPlan(readonly(positions), readonly(expected), nominal, penalty,
                       nominal - penalty, error)
