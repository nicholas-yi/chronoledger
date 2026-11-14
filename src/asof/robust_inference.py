"""Published robust scalar tests; no data loading, study execution or acceptance claim."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

_NW_TABLE = np.loadtxt(Path(__file__).with_name("nw_fixed_b_kv2005.csv"), delimiter=",")
_NW_TABLE.setflags(write=False)
_WEBB = np.array([-math.sqrt(1.5), -1.0, -math.sqrt(0.5),
                  math.sqrt(0.5), 1.0, math.sqrt(1.5)])


@dataclass(frozen=True)
class RobustTest:
    method: str
    status: Literal["available", "not_estimable"]
    estimate: float | None
    t_stat: float | None
    n_obs: int
    p_value: float | None = None
    standard_error: float | None = None
    df: float | None = None
    minimum_p_value: float = 0.0
    critical_values: tuple[tuple[float, float], ...] = ()
    reasons: tuple[str, ...] = ()
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Significance:
    rejected: bool | None
    reason: str


@dataclass(frozen=True)
class RobustGate:
    endpoint: Literal["monthly", "H4", "event"]
    registered_threshold: float
    status: Literal["supported", "not_supported", "undetermined"]
    reasons: tuple[str, ...]
    expected_direction: int | None = None


def _inputs(y: np.ndarray, x: np.ndarray, coefficient: int) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.asarray(y, dtype=float), np.asarray(x, dtype=float)
    if (y.ndim != 1 or x.ndim != 2 or len(y) != len(x) or not len(y)
            or not 0 <= coefficient < x.shape[1]
            or not np.isfinite(y).all() or not np.isfinite(x).all()):
        raise ValueError("need finite y[n], X[n,p] and an identified coefficient index")
    return y, x


def _unavailable(method: str, n: int, reason: str, **details) -> RobustTest:
    return RobustTest(method, "not_estimable", None, None, n,
                      reasons=(reason,), details=details)


def _fit(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if len(y) <= x.shape[1] or np.linalg.matrix_rank(x) != x.shape[1]:
        return None
    bread = np.linalg.inv(x.T @ x)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    return beta, y - x @ beta, bread


def _zero_residual(y: np.ndarray, residual: np.ndarray) -> bool:
    return bool(np.linalg.norm(residual) <= np.finfo(float).eps * len(y) * np.linalg.norm(y))


def _student_test(
    method: str, estimate: float, variance: float, n: int, df: float, **details,
) -> RobustTest:
    if not math.isfinite(variance) or variance <= 0:
        return _unavailable(method, n, "nonpositive_or_nonfinite_variance", **details)
    se = math.sqrt(variance)
    t = estimate / se
    return RobustTest(method, "available", estimate, t, n,
                      p_value=float(2 * stats.t.sf(abs(t), df)), standard_error=se,
                      df=df, details=details)


def ewc_test(y: np.ndarray, x: np.ndarray, coefficient: int = 0) -> RobustTest:
    """LLWS (2018), eq. (10) and footnote 3: floor nu; unrestricted factor score."""
    y, x = _inputs(y, x, coefficient)
    fit = _fit(y, x)
    if fit is None:
        return _unavailable("EWC", len(y), "rank_or_residual_df")
    beta, residual, bread = fit
    n = len(y)
    if _zero_residual(y, residual):
        return _unavailable("EWC", n, "numerically_zero_residual_variation")
    nu = math.floor(0.4 * n ** (2 / 3))
    if not 1 <= nu < n:
        return _unavailable("EWC", n, "invalid_cosine_count")
    weights = math.sqrt(2) * np.cos(
        np.pi * np.arange(1, nu + 1)[:, None] * (np.arange(n) + 0.5) / n)
    influence = residual * (x @ bread[:, coefficient])
    variance = float(np.mean((weights @ influence) ** 2))
    return _student_test("EWC", float(beta[coefficient]), variance, n, nu,
                         nu=nu, parameters=x.shape[1], rounding="floor")


def bartlett_variance(influence: np.ndarray, bandwidth: int) -> float:
    """LLWS eq. (6), scalar coefficient influence; bandwidth S is maxlag+1."""
    influence = np.asarray(influence, dtype=float)
    if influence.ndim != 1 or not np.isfinite(influence).all() or bandwidth < 1:
        raise ValueError("finite scalar influence and positive bandwidth required")
    variance = float(influence @ influence)
    for lag in range(1, min(bandwidth, len(influence))):
        variance += 2 * (1 - lag / bandwidth) * float(influence[lag:] @ influence[:-lag])
    return variance


def nw_fixed_b_test(y: np.ndarray, x: np.ndarray, coefficient: int = 0) -> RobustTest:
    """LLWS rules (3), (6): ceil S, maxlags=S-1 and Bartlett weights 1-j/S."""
    y, x = _inputs(y, x, coefficient)
    fit = _fit(y, x)
    if fit is None:
        return _unavailable("NW_fixed_b", len(y), "rank_or_residual_df")
    beta, residual, bread = fit
    n = len(y)
    if _zero_residual(y, residual):
        return _unavailable("NW_fixed_b", n, "numerically_zero_residual_variation")
    s = math.ceil(1.3 * math.sqrt(n))
    b = s / n
    if not _NW_TABLE[0, 0] <= b <= _NW_TABLE[-1, 0]:
        return _unavailable("NW_fixed_b", n, "outside_published_bandwidth_grid", S=s, b=b)
    influence = residual * (x @ bread[:, coefficient])
    variance = bartlett_variance(influence, s)
    if not math.isfinite(variance) or variance <= 0:
        return _unavailable("NW_fixed_b", n, "nonpositive_or_nonfinite_variance", S=s, b=b)
    se = math.sqrt(variance)
    return RobustTest(
        "NW_fixed_b", "available", float(beta[coefficient]), float(beta[coefficient]) / se, n,
        standard_error=se,
        critical_values=((0.05, float(np.interp(b, _NW_TABLE[:, 0], _NW_TABLE[:, 2]))),
                         (0.02, float(np.interp(b, _NW_TABLE[:, 0], _NW_TABLE[:, 3])))),
        details={"S": s, "maxlags": s - 1, "b": b,
                 "one_sided_5percent_critical": float(np.interp(b, _NW_TABLE[:, 0], _NW_TABLE[:, 1])),
                 "critical_source": "KV(2005) Cornell WP05-08 Table I, p24; linear b interpolation",
                 "critical_precision": "published three-decimal table; no significance-level extrapolation"})


def _groups(groups: np.ndarray, n: int) -> tuple[np.ndarray, int]:
    groups = np.asarray(groups)
    if groups.ndim != 1 or len(groups) != n:
        raise ValueError("cluster/group labels must have one scalar label per row")
    codes, labels = pd.factorize(groups)
    if (codes < 0).any():
        raise ValueError("missing cluster/group labels are not silently dropped")
    return codes, len(labels)


def im_group_test(
    y: np.ndarray, signal: np.ndarray, nuisance: np.ndarray, groups: np.ndarray,
    *, expected_groups: Sequence, group_axis: str,
) -> RobustTest:
    """IM (2010), eq. (2): unweighted group estimates, Student t(q-1).

    Preserve each group's nuisance column space, absorbing constants/redundancy
    before testing identification. Never drop an infeasible group or its tested signal.
    Independence, Gaussianity and a common parameter are assumptions, not output facts.
    """
    y, signal = np.asarray(y, dtype=float), np.asarray(signal, dtype=float)
    nuisance = np.asarray(nuisance, dtype=float)
    if signal.shape != y.shape or y.ndim != 1 or nuisance.ndim != 2:
        raise ValueError("need y[n], signal[n], nuisance[n,k]")
    full = np.column_stack([signal, nuisance])
    _inputs(y, full, 0)
    _groups(groups, len(y))
    expected = list(expected_groups)
    if len(expected) < 2 or len(set(expected)) != len(expected):
        raise ValueError("register at least two distinct groups")
    if set(pd.unique(groups)) - set(expected):
        raise ValueError("unexpected groups outside the registered group set")
    estimates, records = [], []
    for label in expected:
        mask = np.asarray(groups) == label
        n = int(mask.sum())
        record = {"group": str(label), "n_obs": n, "dropped_nuisance_columns": []}
        z = np.ones((n, 1))
        for j in range(nuisance.shape[1]):
            candidate = np.column_stack([z, nuisance[mask, j]])
            if n and np.linalg.matrix_rank(candidate) > z.shape[1]:
                z = candidate
            else:
                record["dropped_nuisance_columns"].append(j)
        design = np.column_stack([signal[mask], z])
        fit = _fit(y[mask], design)
        if fit is None:
            record.update(status="not_estimable", reason="tested_signal_rank_or_residual_df")
        else:
            value = float(fit[0][0])
            estimates.append(value)
            record.update(status="available", estimate=value, parameters=design.shape[1])
        records.append(record)
    details = {"groups": records, "registered_group_count": len(expected), "group_axis": group_axis,
               "within_one_sided_5percent_group_bound": len(expected) <= 14}
    if len(estimates) != len(expected):
        return _unavailable("IM", len(y), "infeasible_registered_group", **details)
    variance = float(np.var(estimates, ddof=1) / len(estimates))
    return _student_test("IM", float(np.mean(estimates)), variance, len(y),
                         len(estimates) - 1, **details)


def _cluster_component(
    codes: np.ndarray, x: np.ndarray, influence: np.ndarray,
) -> tuple[np.ndarray, float]:
    g = int(codes.max()) + 1
    if g < 2:
        raise ValueError("cluster variance requires at least two clusters in each dimension")
    indicator = (codes[:, None] == np.arange(g)).astype(float)
    factor = g / (g - 1) * (len(x) - 1) / (len(x) - x.shape[1])
    return indicator * influence[:, None], factor


def wild_cluster_restricted(
    y: np.ndarray, x: np.ndarray, groups: np.ndarray, coefficient: int,
    *, seed: int, draws: int = 399, weights: Literal["webb", "rademacher"] = "webb",
    max_enumeration: int = 10000, covariance_groups: np.ndarray | None = None,
    cluster_axis: str, null: float = 0.0,
) -> RobustTest:
    """WCR scalar restriction: MNW (2021), algorithm steps 1-4, CV1 studentization.

    Webb (2014), eq. (4), six weights. Enumerate full support when bounded; otherwise
    use explicit-seed Monte Carlo with inclusive ties and (1+exceedances)/(B+1).
    Constant-weight vectors force an exact two-sided tail floor support**(1-G).
    Nonpositive variances stay invalid; no silent PSD repair or dropped bootstrap draws.
    """
    y, x = _inputs(y, x, coefficient)
    if draws < 1 or max_enumeration < 1 or weights not in {"webb", "rademacher"}:
        raise ValueError("positive draw/enumeration limits and known weight distribution required")
    codes, g = _groups(groups, len(y))
    if g < 2:
        return _unavailable("WCR", len(y), "fewer_than_two_bootstrap_clusters")
    fit = _fit(y, x)
    if fit is None:
        return _unavailable("WCR", len(y), "rank_or_residual_df")
    beta, residual, bread = fit
    if _zero_residual(y, residual):
        return _unavailable("WCR", len(y), "numerically_zero_residual_variation")
    influence = x @ bread[:, coefficient]
    if covariance_groups is None:
        covariance_groups = np.asarray(groups)[:, None]
    covariance_groups = np.asarray(covariance_groups)
    if covariance_groups.ndim == 1:
        covariance_groups = covariance_groups[:, None]
    if covariance_groups.shape[0] != len(y) or covariance_groups.shape[1] not in (1, 2):
        raise ValueError("CV1 covariance labels require one or two clustering dimensions")
    components = []
    dimensions = []
    for j in range(covariance_groups.shape[1]):
        c, h = _groups(covariance_groups[:, j], len(y))
        if h < 2:
            return _unavailable("WCR", len(y), "fewer_than_two_covariance_clusters")
        dimensions.append(c)
        components.append((*_cluster_component(c, x, influence), 1.0))
    if len(dimensions) == 2:
        intersection, _ = pd.factorize(pd.MultiIndex.from_arrays(dimensions))
        components.append((*_cluster_component(intersection, x, influence), -1.0))
    variance = sum(sign * correction * float(np.sum((residual @ weighted) ** 2))
                   for weighted, correction, sign in components)
    if not math.isfinite(variance) or variance <= 0:
        return _unavailable("WCR", len(y), "nonpositive_observed_cluster_variance")
    estimate = float(beta[coefficient] - null)
    observed = estimate / math.sqrt(variance)
    restricted = beta - bread[:, coefficient] * estimate / bread[coefficient, coefficient]
    u_r = y - x @ restricted
    indicator = (codes[:, None] == np.arange(g)).astype(float)
    response = (indicator.T @ (u_r[:, None] * x)) @ bread
    quadratic = np.zeros((g, g))
    for weighted, correction, sign in components:
        projected = indicator.T @ (u_r[:, None] * weighted) - response @ (x.T @ weighted)
        quadratic += sign * correction * (projected @ projected.T)
    support = _WEBB if weights == "webb" else np.array([-1.0, 1.0])
    enumerated = len(support) ** g <= max_enumeration
    w = (np.array(list(product(support, repeat=g))) if enumerated
         else np.random.default_rng(seed).choice(support, (draws, g)))
    variances = np.einsum("bi,ij,bj->b", w, quadratic, w)
    invalid = int((~np.isfinite(variances) | (variances <= 0)).sum())
    minimum = float(len(support) ** (1 - g))
    if not enumerated:
        minimum = max(minimum, 1 / (len(w) + 1))
    details = {"bootstrap_draws": len(w), "enumerated": enumerated,
               "clusters": g, "cluster_axis": cluster_axis, "weights": weights,
               "invalid_bootstrap_draws": invalid, "seed": seed,
               "paired_support_resolution": float(2 / len(support) ** g),
               "identity_tie_floor": float(len(support) ** (1 - g))}
    if invalid:
        return _unavailable("WCR", len(y), "invalid_bootstrap_variance", **details)
    bootstrap_t = (w @ response[:, coefficient]) / np.sqrt(variances)
    exceed = int((abs(bootstrap_t) >= abs(observed) * (1 - 1e-10) - 1e-12).sum())
    raw_p = exceed / len(w) if enumerated else (1 + exceed) / (len(w) + 1)
    details["raw_tail_p"] = raw_p
    return RobustTest("WCR", "available", estimate, observed, len(y),
                      p_value=max(minimum, raw_p), standard_error=math.sqrt(variance),
                      minimum_p_value=minimum, details=details)


def significance(test: RobustTest, alpha: float, direction: int | None = None) -> Significance:
    if not 0 < alpha <= 0.05 or direction not in (None, -1, 1):
        raise ValueError("use a two-sided-equivalent level in (0,.05] and an optional +/-1 direction")
    if test.status != "available" or test.t_stat is None or not math.isfinite(test.t_stat):
        return Significance(None, "not_estimable")
    if test.minimum_p_value > alpha:
        return Significance(None, "unattainable_significance_level")
    if test.method == "NW_fixed_b":
        critical = next((c for a, c in test.critical_values if abs(a - alpha) < 1e-12), None)
        if critical is None:
            return Significance(None, "level_not_in_published_fixed_b_table")
        rejected = abs(test.t_stat) >= critical
    else:
        if test.p_value is None or not math.isfinite(test.p_value) or not 0 <= test.p_value <= 1:
            return Significance(None, "missing_or_invalid_p_value")
        rejected = test.p_value <= alpha
    if direction is not None:
        if test.estimate is None or not math.isfinite(test.estimate):
            return Significance(None, "missing_effect")
        rejected = rejected and direction * test.estimate > 0
    return Significance(bool(rejected), "evaluated_at_requested_level")


def future_robust_gate(
    endpoint: Literal["monthly", "H4", "event"], registered_threshold: float,
    expected_direction: int, test: RobustTest | None, *,
    registered_passed: bool | None = None,
    assumptions_met: bool | None, reliable_at_geometry: bool | None,
    crosscheck: RobustTest | None = None,
) -> RobustGate:
    if endpoint not in ("monthly", "H4", "event") or registered_threshold not in (2.0, 3.0, 3.2):
        raise ValueError("registered endpoint and threshold required")
    if expected_direction not in (-1, 1):
        raise ValueError("expected direction must be registered explicitly")
    if registered_passed is False:
        return RobustGate(endpoint, registered_threshold, "not_supported",
                          ("registered_requirement_failed",), expected_direction)
    required = {"monthly": "EWC", "H4": "IM", "event": "WCR"}[endpoint]
    missing = []
    if registered_passed is not True:
        missing.append("registered_requirements_not_established")
    if assumptions_met is not True or reliable_at_geometry is not True:
        missing.append("assumptions_or_geometry_reliability_not_established")
    if test is None or test.method != required:
        missing.append("matching_robust_procedure_missing")
    elif endpoint == "H4" and (test.details.get("group_axis") != "year"
                               or test.details.get("registered_group_count") != 7):
        missing.append("registered_seven_year_groups_required")
    elif endpoint == "event" and test.details.get("cluster_axis") != "month":
        missing.append("registered_month_bootstrap_clusters_required")
    if endpoint == "event" and (crosscheck is None or crosscheck.method != "IM"
                               or crosscheck.details.get("group_axis") != "month"):
        missing.append("IM_by_month_crosscheck_report_missing")
    if missing:
        return RobustGate(endpoint, registered_threshold, "undetermined", tuple(missing),
                          expected_direction)
    assert test is not None
    level = float(2 * stats.norm.sf(registered_threshold))
    if endpoint == "monthly" and test.df is not None and test.df <= 3 and registered_threshold >= 3:
        return RobustGate(endpoint, registered_threshold, "undetermined",
                          ("very_low_EWC_df_rare_level_not_qualified",), expected_direction)
    checks = [significance(test, level, expected_direction)]
    if any(c.rejected is None for c in checks):
        return RobustGate(endpoint, registered_threshold, "undetermined",
                          tuple(c.reason for c in checks if c.rejected is None), expected_direction)
    status = "supported" if all(c.rejected for c in checks) else "not_supported"
    return RobustGate(endpoint, registered_threshold, status,
                      () if status == "supported" else ("robust_level_or_direction_not_rejected",),
                      expected_direction)
