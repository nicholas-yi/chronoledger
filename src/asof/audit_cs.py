"""Conditional finite-population confidence sets, not timestamp/source certification."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import hypergeom

MAX_POPULATION = 100_000
LOG_MARGIN = 1e-7


@dataclass(frozen=True)
class AuditConfidenceSet:
    population: int
    drawn: int
    observed_errors: int
    unread: int
    delta: float
    intervals: tuple[tuple[int, int], ...]

    def contains(self, total: int) -> bool:
        return any(low <= total <= high for low, high in self.intervals)

    def summary(self) -> dict:
        low, high = self.intervals[0][0], self.intervals[-1][1]
        return {
            "status": "conditional_confidence_set",
            "method": "uniform_total_prior_hypergeometric_PPR_with_unread_union",
            "population": self.population, "drawn": self.drawn,
            "observed_errors": self.observed_errors, "unread_sampled": self.unread,
            "unsampled": self.population - self.drawn, "delta": self.delta,
            "total_error_intervals_inclusive": self.intervals,
            "lower_rate": low / self.population, "upper_rate": high / self.population,
            "working_prior": "uniform on integer totals 0..population; fixed before observation",
            "path_intersection_applied": False,
            "boundary_policy": f"retain equality and an outward {LOG_MARGIN:g} log margin",
            "assumptions": [
                "fixed population, binary labels and eligibility",
                "uniform without-replacement random prefix, including unread sampled members",
                "population, delta, label definition and method fixed before observation",
                "priority/nonrandom strata not pooled into the random prefix",
            ],
            "sampling_verified": False, "scientific_acceptance": False,
            "qualifies_UTC": False,
        }


def audit_confidence_set(
    population: int, drawn: int, observed_errors: int, unread: int = 0, delta: float = 0.05,
) -> AuditConfidenceSet:
    """Return an unintersected time-uniform count set under the stated sampling model.

    With a uniform prior on total errors K, the marginal probability of s errors
    in m draws is 1/(m+1). The PPR accepts K when HG(s; N,K,m) > delta/(m+1).
    Unread labels are marginalized by a union, not by a missing-at-random assumption.
    """
    for name, value in (("population", population), ("drawn", drawn),
                        ("observed_errors", observed_errors), ("unread", unread)):
        if type(value) is not int:
            raise ValueError(f"{name} must be an integer, not a boolean or coerced count")
    if not 1 <= population <= MAX_POPULATION:
        raise ValueError(f"population must be between 1 and {MAX_POPULATION}")
    if not 0 <= drawn <= population or not 0 <= unread <= drawn:
        raise ValueError("require 0 <= unread <= drawn <= population")
    if not 0 <= observed_errors <= drawn - unread:
        raise ValueError("observed_errors cannot exceed the number of readable sampled members")
    if (isinstance(delta, bool) or not isinstance(delta, (int, float))
            or not math.isfinite(delta) or not 0 < delta < 1):
        raise ValueError("delta must be a finite number strictly between zero and one")

    totals = np.arange(population + 1, dtype=np.int64)
    # Maximize over admissible unread completions at the clamped hypergeometric mode.
    mode = ((drawn + 1) * (totals + 1)) // (population + 2)
    successes = np.clip(mode, observed_errors, observed_errors + unread)
    log_probability = hypergeom.logpmf(successes, population, totals, drawn)
    if np.any(np.isnan(log_probability) | np.isposinf(log_probability)):
        raise ArithmeticError("hypergeometric backend returned an invalid log probability")
    accepted = log_probability >= math.log(delta) - math.log(drawn + 1) - LOG_MARGIN
    edges = np.diff(np.concatenate(([False], accepted, [False])).astype(np.int8))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1
    intervals = tuple((int(low), int(high)) for low, high in zip(starts, ends, strict=True))
    if not intervals:
        raise ArithmeticError("empty set for a full-support uniform prior; inspect numerics/inputs")
    return AuditConfidenceSet(population, drawn, observed_errors, unread, float(delta), intervals)
