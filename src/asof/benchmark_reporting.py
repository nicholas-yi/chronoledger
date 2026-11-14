"""Descriptive question-level accuracy intervals, not a trading inference procedure."""

from __future__ import annotations

import math


def wilson95(successes: int, n: int) -> tuple[float, float] | None:
    """Two-sided 95% Wilson score interval; question dependence is not corrected here."""
    if (isinstance(successes, bool) or isinstance(n, bool) or not isinstance(successes, int)
            or not isinstance(n, int) or not 0 <= successes <= n):
        raise ValueError("integer successes and denominator with 0<=successes<=n required")
    if n == 0:
        return None
    z = 1.959963984540054
    p = successes / n
    factor = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / factor
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / factor
    return max(0.0, centre - radius), min(1.0, centre + radius)
