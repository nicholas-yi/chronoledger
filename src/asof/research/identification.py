"""H: deterministic support bounds, not sampling confidence or a missing-data imputation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real

import numpy as np
from numpy.typing import ArrayLike

from ._validation import scalar, text, vector


@dataclass(frozen=True)
class OutcomeBound:
    lower: float
    upper: float
    observed: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.observed, bool):
            raise TypeError("observed must be explicit")
        text(self.reason, "support reason")
        for value in (self.lower, self.upper):
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError("support endpoints must be real numbers or explicit infinities")
            if math.isnan(value):
                raise ValueError("NaN is not a support bound")
        if self.lower > self.upper or self.lower == math.inf or self.upper == -math.inf:
            raise ValueError("support interval is empty")
        if self.observed and (self.lower != self.upper or not math.isfinite(self.lower)):
            raise ValueError("observed outcomes require an exact finite value")


@dataclass(frozen=True)
class IdentifiedInterval:
    lower: float
    upper: float
    unobserved: int
    unbounded: bool
    reasons: tuple[str, ...]


def payoff_bounds(weights: ArrayLike, outcomes: Sequence[OutcomeBound]) -> IdentifiedInterval:
    """Sharp bounds for a linear payoff over independent rectangular outcome supports.

    Joint clock/identity/financing constraints are not represented. Infinite limits are
    meaningful non-identification, not numeric failure or a confidence interval.
    """
    w = vector(weights, "weights", len(outcomes))
    low, high = 0.0, 0.0
    for weight, bound in zip(w, outcomes, strict=True):
        if weight == 0:
            continue
        left, right = ((bound.lower, bound.upper) if weight > 0
                       else (bound.upper, bound.lower))
        low_term, high_term = float(weight) * left, float(weight) * right
        if ((math.isfinite(left) and not math.isfinite(low_term))
                or (math.isfinite(right) and not math.isfinite(high_term))):
            raise FloatingPointError("finite payoff support overflowed")
        new_low, new_high = low + low_term, high + high_term
        if ((math.isfinite(low) and math.isfinite(low_term) and not math.isfinite(new_low))
                or (math.isfinite(high) and math.isfinite(high_term) and not math.isfinite(new_high))):
            raise FloatingPointError("finite payoff accumulation overflowed")
        low, high = new_low, new_high
    return IdentifiedInterval(
        low, high, sum(not b.observed for b in outcomes),
        not (math.isfinite(low) and math.isfinite(high)),
        tuple(b.reason for b in outcomes if not b.observed))


def mean_bounds(
    observed: ArrayLike, *, missing_count: int, lower: float, upper: float, reason: str,
) -> IdentifiedInterval:
    """Finite-population mean under explicitly supplied missing-outcome support."""
    raw = np.asarray(observed)
    values = (np.array([], dtype=float) if raw.shape == (0,) and raw.dtype.kind in "iuf"
              else vector(observed, "observed"))
    if isinstance(missing_count, bool) or not isinstance(missing_count, int) or missing_count < 0:
        raise ValueError("missing_count must be a nonnegative integer")
    bound = OutcomeBound(lower, upper, False, reason)
    if any(not lower <= value <= upper for value in values):
        raise ValueError("observed values contradict the declared population support")
    count = len(values) + missing_count
    if count == 0:
        raise ValueError("population cannot be empty")
    known = scalar(float(values.sum()), "observed sum")
    low = (known + missing_count * bound.lower) / count if missing_count else known / count
    high = (known + missing_count * bound.upper) / count if missing_count else known / count
    return IdentifiedInterval(low, high, missing_count,
                              not (math.isfinite(low) and math.isfinite(high)),
                              (reason,) if missing_count else ())
