"""Shared numerical contracts for the in-memory reference algorithms."""

from __future__ import annotations

from numbers import Real

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not value.strip():
        raise ValueError(f"{name} must be nonempty")
    return value


def scalar(value: float, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} cannot be represented as finite float64") from exc
    if not np.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def array(value: ArrayLike, name: str, ndim: int) -> FloatArray:
    result = np.asarray(value)
    if result.dtype.kind not in "iuf":
        raise TypeError(f"{name} must contain real numeric values, not coercible strings or booleans")
    if result.ndim != ndim or any(d == 0 for d in result.shape):
        raise ValueError(f"{name} must be nonempty with {ndim} dimensions")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite")
    converted = np.array(result, dtype=np.float64, copy=True)
    if not np.isfinite(converted).all():
        raise ValueError(f"{name} cannot be represented as finite float64")
    return converted


def vector(value: ArrayLike, name: str, size: int | None = None) -> FloatArray:
    result = array(value, name, 1)
    if size is not None and len(result) != size:
        raise ValueError(f"{name} has the wrong length")
    return result


def matrix(value: ArrayLike, name: str, shape: tuple[int, int] | None = None) -> FloatArray:
    result = array(value, name, 2)
    if shape is not None and result.shape != shape:
        raise ValueError(f"{name} has the wrong shape")
    return result


def covariance(value: ArrayLike, name: str, size: int, *, definite: bool) -> FloatArray:
    result = matrix(value, name, (size, size))
    if not np.allclose(result, result.T, atol=1e-12, rtol=1e-12):
        raise ValueError(f"{name} must be symmetric")
    result = (result + result.T) / 2
    eigenvalues = np.linalg.eigvalsh(result)
    if (definite and eigenvalues[0] <= 0) or (not definite and eigenvalues[0] < 0):
        kind = "positive definite" if definite else "positive semidefinite"
        raise ValueError(f"{name} must be {kind}")
    return result


def distribution(value: ArrayLike, name: str, size: int | None = None) -> FloatArray:
    result = vector(value, name, size)
    if (result < 0).any() or not np.isclose(result.sum(), 1, atol=1e-12, rtol=1e-12):
        raise ValueError(f"{name} must be a probability distribution")
    return result / result.sum()


def readonly(value: FloatArray) -> FloatArray:
    result = value.copy()
    result.setflags(write=False)
    return result
