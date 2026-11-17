"""C: level-two geometric signatures of explicitly supplied, prefix-causal paths."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise

import numpy as np
from numpy.typing import ArrayLike

from asof.timeutil import aware_utc

from ._validation import FloatArray, matrix, readonly, vector


@dataclass(frozen=True)
class Signature2:
    increment: FloatArray
    second: FloatArray

    def __post_init__(self) -> None:
        first = vector(self.increment, "increment")
        second = matrix(self.second, "second", (len(first), len(first)))
        if not np.allclose(second + second.T, np.outer(first, first), atol=1e-10, rtol=1e-10):
            raise ValueError("level-two coordinates violate the geometric shuffle identity")
        object.__setattr__(self, "increment", readonly(first))
        object.__setattr__(self, "second", readonly(second))

    def concatenate(self, following: Signature2) -> Signature2:
        if self.increment.shape != following.increment.shape:
            raise ValueError("path channel dimensions must match")
        return Signature2(
            self.increment + following.increment,
            self.second + following.second + np.outer(self.increment, following.increment))

    def features(self) -> FloatArray:
        return readonly(np.concatenate(([1.0], self.increment, self.second.ravel())))

    def area(self) -> FloatArray:
        return readonly((self.second - self.second.T) / 2)


def signature2(points: ArrayLike) -> Signature2:
    """Exact level-two signature of a piecewise-linear path; initial level is not encoded."""
    path = matrix(points, "points")
    dimension = path.shape[1]
    if dimension > 64:
        raise ValueError("dense level-two reference implementation is limited to 64 channels")
    first, second = np.zeros(dimension), np.zeros((dimension, dimension))
    for delta in np.diff(path, axis=0):
        second += np.outer(first, delta) + np.outer(delta, delta) / 2
        first += delta
    return Signature2(first, second)


@dataclass(frozen=True)
class CausalTrajectory:
    initial_state: FloatArray
    signature: Signature2
    endpoint: FloatArray
    event_count: int
    elapsed_days: float


def causal_trajectory(
    times: Sequence[datetime], states: ArrayLike, *, as_of: datetime,
) -> CausalTrajectory:
    """Select eligible knots, prepend elapsed UTC days, and never interpolate toward future knots.

    Tied timestamps are rejected rather than converting paragraph order into economic order.
    No scaling or missing-value imputation is learned; caller channels must already be compatible.
    """
    cutoff = aware_utc(as_of, "as_of")
    timestamps = tuple(aware_utc(t, "event time") for t in times)
    if not timestamps or any(a >= b for a, b in pairwise(timestamps)):
        raise ValueError("strictly increasing unique event times are required")
    raw = np.asarray(states, dtype=object)
    if raw.ndim != 2 or raw.shape[0] != len(timestamps):
        raise ValueError("one state row per event time is required")
    count = sum(t <= cutoff for t in timestamps)
    if count == 0:
        raise ValueError("no eligible initial economic state")
    prefix = matrix(raw[:count].tolist(), "eligible states")
    clock = np.array([(t - timestamps[0]).total_seconds() / 86400 for t in timestamps[:count]])
    path = np.column_stack((clock, prefix))
    return CausalTrajectory(
        readonly(prefix[0]), signature2(path), readonly(prefix[-1]), count, float(clock[-1]))
