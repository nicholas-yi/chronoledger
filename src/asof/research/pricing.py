"""E: explicit asset-pricing identities, not identification from language or option data."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.special import logsumexp

from ._validation import (
    FloatArray,
    distribution,
    matrix,
    readonly,
    scalar,
    vector,
)


@dataclass(frozen=True)
class ReturnNews:
    unexpected_return: float
    cash_flow_news: float
    discount_rate_news: float


def campbell_news(
    transition: ArrayLike, innovation: ArrayLike, return_selector: ArrayLike, *, rho: float,
) -> ReturnNews:
    """Log-linear VAR news under supplied parameters; no VAR is fitted.

    DR = e' rho*A (I-rho*A)^(-1) epsilon; CF = e'epsilon + DR.
    Requires a convergent discounted forecast sum and the present-value model's conditions.
    """
    shock = vector(innovation, "innovation")
    a = matrix(transition, "transition", (len(shock), len(shock)))
    selector = vector(return_selector, "return_selector", len(shock))
    rho = scalar(rho, "rho")
    if not 0 < rho < 1:
        raise ValueError("rho must lie strictly between zero and one")
    if np.max(np.abs(np.linalg.eigvals(rho * a))) >= 1:
        raise ValueError("discounted VAR forecast sum does not converge")
    future = np.linalg.solve(np.eye(len(shock)) - rho * a, shock)
    discount = float(selector @ (rho * a @ future))
    unexpected = float(selector @ shock)
    cash_flow = unexpected + discount
    if not np.isfinite([discount, unexpected, cash_flow]).all():
        raise FloatingPointError("nonfinite VAR news")
    return ReturnNews(unexpected, cash_flow, discount)


def physical_probabilities(risk_neutral: ArrayLike, state_pricing_kernel: ArrayLike) -> FloatArray:
    """Invert q proportional to p*m for a supplied strictly positive finite-state kernel."""
    q = distribution(risk_neutral, "risk_neutral")
    kernel = vector(state_pricing_kernel, "state_pricing_kernel", len(q))
    if (kernel <= 0).any():
        raise ValueError("pricing kernel must be strictly positive")
    log_q = np.full(len(q), -np.inf)
    np.log(q, where=q > 0, out=log_q)
    log_weights = log_q - np.log(kernel)
    return readonly(np.exp(log_weights - logsumexp(log_weights)))


def pricing_moments(excess_payoffs: ArrayLike, sdf: ArrayLike) -> FloatArray:
    """Sample E[m*excess payoff] moments; no standard errors or no-arbitrage certificate."""
    payoffs = matrix(excess_payoffs, "excess_payoffs")
    kernel = vector(sdf, "sdf", len(payoffs))
    if (kernel <= 0).any():
        raise ValueError("SDF must be strictly positive")
    with np.errstate(over="raise", invalid="raise"):
        moments = (kernel[:, None] * payoffs).mean(axis=0)
    return readonly(moments)
