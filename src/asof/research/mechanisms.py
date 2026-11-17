"""F: fixed-feature ridge influence and descriptive mechanism-twin reconstruction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from ._validation import FloatArray, matrix, readonly, scalar, vector


def kernel_weights(
    reference_features: ArrayLike, query: ArrayLike, *, penalty: float,
) -> FloatArray:
    """a=(Phi Phi'+penalty I)^(-1)Phi phi(query); a'y is the fixed-map ridge forecast.

    This performs matrix algebra only. No feature map is learned, no data is fetched and
    weights are not assumed positive, normalized, causal or independent observations.
    """
    phi = matrix(reference_features, "reference_features")
    x = vector(query, "query", phi.shape[1])
    penalty = scalar(penalty, "penalty")
    if penalty <= 0:
        raise ValueError("penalty must be strictly positive")
    result = np.linalg.solve(phi @ phi.T + penalty * np.eye(len(phi)), phi @ x)
    if not np.isfinite(result).all():
        raise FloatingPointError("nonfinite ridge influence")
    return readonly(result)


@dataclass(frozen=True)
class TwinProjection:
    intercept: float
    coefficients: FloatArray
    reconstructed: FloatArray
    residual: FloatArray
    residual_rms: float
    explained_fraction: float | None


def project_on_twins(scores: ArrayLike, twins: ArrayLike) -> TwinProjection:
    """Descriptive in-sample least-squares reconstruction with an intercept, not OOS evidence."""
    y = vector(scores, "scores")
    x = matrix(twins, "twins")
    if len(x) != len(y):
        raise ValueError("one twin row per score is required")
    design = np.column_stack((np.ones(len(y)), x))
    if len(y) <= design.shape[1]:
        raise ValueError("need residual degrees of freedom beyond the supplied twins")
    coefficients, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank != design.shape[1]:
        raise ValueError("mechanism twins are rank deficient")
    reconstructed = design @ coefficients
    residual = y - reconstructed
    total = float(np.sum((y - y.mean()) ** 2))
    explained = 1 - float(residual @ residual) / total if total > 0 else None
    return TwinProjection(
        float(coefficients[0]), readonly(coefficients[1:]), readonly(reconstructed),
        readonly(residual), float(np.sqrt(np.mean(residual**2))), explained)
