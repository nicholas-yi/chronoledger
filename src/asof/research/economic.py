"""A: declared economic facts, public-history novelty and finite-state belief updates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike

from asof.timeutil import aware_utc

from ._validation import FloatArray, distribution, matrix, readonly, scalar, text, vector


@dataclass(frozen=True)
class MetricKey:
    issuer: str
    metric: str
    unit: str
    scope: str
    definition: str

    def __post_init__(self) -> None:
        for name in ("issuer", "metric", "unit", "scope", "definition"):
            text(getattr(self, name), name)


Coverage = Literal["observed", "source_missing", "not_issuer_specific", "unresolved"]


@dataclass(frozen=True)
class Observation:
    key: MetricKey
    period_end: date
    known_at: datetime
    source_id: str
    value: float | None
    coverage: Coverage = "observed"
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, MetricKey):
            raise TypeError("key must be a MetricKey")
        if not isinstance(self.period_end, date) or isinstance(self.period_end, datetime):
            raise TypeError("period_end must be a date")
        known = aware_utc(self.known_at, "known_at")
        object.__setattr__(self, "known_at", known)
        if self.period_end > known.date():
            raise ValueError("period end cannot follow availability")
        text(self.source_id, "source_id")
        if self.coverage == "observed":
            if self.value is None:
                raise ValueError("observed facts require a value, including explicit zero")
            object.__setattr__(self, "value", scalar(self.value, "observed value"))
            if self.reason is not None:
                raise ValueError("observed facts cannot also have an unavailable reason")
        elif self.coverage in ("source_missing", "not_issuer_specific", "unresolved"):
            if self.value is not None or not self.reason:
                raise ValueError("unavailable evidence needs a reason and no numeric value")
            text(self.reason, "reason")
        else:
            raise ValueError("unknown coverage status")


def state_as_of(
    observations: Sequence[Observation], cutoff: datetime,
) -> dict[tuple[MetricKey, date], Observation]:
    """Latest eligible observation per exact metric-period, retaining unavailable states.

    No units/definitions are inferred and no stale value replaces a later unavailable row.
    Simultaneous conflicting sources fail rather than choosing an arbitrary document.
    """
    cutoff = aware_utc(cutoff, "cutoff")
    result: dict[tuple[MetricKey, date], Observation] = {}
    seen_sources: set[tuple[str, MetricKey, date]] = set()
    for obs in sorted(observations, key=lambda o: aware_utc(o.known_at)):
        if aware_utc(obs.known_at) > cutoff:
            continue
        source_key = (obs.source_id, obs.key, obs.period_end)
        if source_key in seen_sources:
            raise ValueError("duplicate source/metric/period observations")
        seen_sources.add(source_key)
        key = (obs.key, obs.period_end)
        old = result.get(key)
        if (old is not None and old.known_at == obs.known_at
                and (old.value, old.coverage, old.reason) != (obs.value, obs.coverage, obs.reason)):
            raise ValueError("simultaneous conflicting economic evidence")
        if old is not None and old.known_at == obs.known_at and old.source_id < obs.source_id:
            continue
        result[key] = obs
    return result


@dataclass(frozen=True)
class Innovation:
    status: Literal["new_observed_value", "already_public", "unavailable"]
    prior_source_ids: tuple[str, ...]
    reason: str | None


def public_innovation(observation: Observation, history: Sequence[Observation]) -> Innovation:
    """Exact-value novelty in supplied prior public history, not market expectations or truth."""
    if observation.coverage != "observed":
        return Innovation("unavailable", (), observation.reason)
    prior = tuple(o for o in history if aware_utc(o.known_at) < aware_utc(observation.known_at))
    prior_state = state_as_of(prior, observation.known_at)
    latest = prior_state.get((observation.key, observation.period_end))
    if latest is not None and latest.coverage != "observed":
        return Innovation("unavailable", (latest.source_id,), "prior_state_unavailable")
    matches = tuple(sorted({o.source_id for o in prior
                            if latest is not None
                            and aware_utc(o.known_at) == aware_utc(latest.known_at)
                            and o.key == observation.key and o.period_end == observation.period_end
                            and o.coverage == "observed" and o.value == observation.value}))
    return Innovation("already_public" if matches else "new_observed_value", matches, None)


def numeric_update(current: Observation, baseline: Observation) -> float:
    """Difference of compatible supplied observations; period endpoints remain explicit."""
    if current.key != baseline.key:
        raise ValueError("issuer, metric, unit, scope and definition must match")
    if (current.coverage != "observed" or baseline.coverage != "observed"
            or current.value is None or baseline.value is None):
        raise ValueError("numeric change is unavailable, not zero")
    if (aware_utc(current.known_at) <= aware_utc(baseline.known_at)
            or current.period_end < baseline.period_end):
        raise ValueError("baseline must precede the update without reversing periods")
    return scalar(scalar(current.value, "current") - scalar(baseline.value, "baseline"),
                  "numeric update")


@dataclass(frozen=True)
class BeliefUpdate:
    predicted: FloatArray
    posterior: FloatArray
    evidence_probability: float | None
    observation: str


def update_belief(
    prior: ArrayLike, transition: ArrayLike, *,
    observation: Literal["observed", "silent", "unavailable", "no_opportunity"],
    disclosure_probability: ArrayLike | None = None,
    emission_probability: ArrayLike | None = None,
) -> BeliefUpdate:
    """Exact finite-state Bayes update under supplied transition/disclosure probabilities.

    Rows of transition are state-to-next-state distributions. Silence is observed only when
    an actual disclosure opportunity was observable. Unavailable sources do not count as silence.
    Probabilities are assumptions, not estimated managerial behavior.
    """
    p = distribution(prior, "prior")
    t = matrix(transition, "transition", (len(p), len(p)))
    if (t < 0).any() or not np.allclose(t.sum(axis=1), 1, atol=1e-12, rtol=1e-12):
        raise ValueError("transition rows must be probability distributions")
    predicted = distribution(t.T @ p, "predicted")
    if observation in ("unavailable", "no_opportunity"):
        if disclosure_probability is not None or emission_probability is not None:
            raise ValueError("unobserved opportunities cannot consume disclosure/emission evidence")
        return BeliefUpdate(readonly(predicted), readonly(predicted), None, observation)
    if observation not in ("observed", "silent"):
        raise ValueError("unknown observation state")
    if disclosure_probability is None:
        raise ValueError("informative observation requires disclosure probabilities")
    d = vector(disclosure_probability, "disclosure_probability", len(p))
    if ((d < 0) | (d > 1)).any():
        raise ValueError("disclosure probabilities must lie in [0,1]")
    likelihood = 1 - d
    if observation == "observed":
        if emission_probability is None:
            raise ValueError("observed category requires emission probabilities")
        emission = vector(emission_probability, "emission_probability", len(p))
        if ((emission < 0) | (emission > 1)).any():
            raise ValueError("emission probabilities must lie in [0,1]")
        likelihood = d * emission
    elif emission_probability is not None:
        raise ValueError("silence cannot consume an emitted category")
    weighted = predicted * likelihood
    evidence = float(weighted.sum())
    if evidence <= 0:
        raise ValueError("observation has zero probability under the supplied model")
    return BeliefUpdate(readonly(predicted), readonly(weighted / evidence), evidence, observation)
