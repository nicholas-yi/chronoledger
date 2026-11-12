"""Inference with explicit multiple-testing control.

* ``nw_alpha``: factor-model alpha with Newey-West (HAC) standard errors.
* ``deflated_sharpe_ratio``: Bailey & Lopez de Prado (2014). Tests the best Sharpe ratio against
  the expected maximum Sharpe ratio of N trials, adjusting for skew and kurtosis.
* ``pbo_cscv``: probability of backtest overfitting via combinatorially symmetric
  cross-validation (Bailey, Borwein, Lopez de Prado & Zhu 2017).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True)
class AlphaResult:
    alpha: float
    t_stat: float
    n_obs: int
    betas: dict[str, float]


def nw_alpha(returns: pd.Series, factors: pd.DataFrame, lags: int = 6) -> AlphaResult:
    data = pd.concat([returns.rename("ret"), factors], axis=1, join="inner").dropna()
    x = sm.add_constant(data[factors.columns])
    fit = sm.OLS(data["ret"], x).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return AlphaResult(
        alpha=float(fit.params["const"]),
        t_stat=float(fit.tvalues["const"]),
        n_obs=int(fit.nobs),
        betas={k: float(v) for k, v in fit.params.items() if k != "const"},
    )


def sharpe(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 0 else 0.0


def probabilistic_sharpe_ratio(
    sr: float, n_obs: int, skew: float, kurtosis: float, sr_benchmark: float = 0.0
) -> float:
    """P(true SR > benchmark). ``kurtosis`` is non-excess (normal = 3). SRs are per-period."""
    denom = np.sqrt(1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr**2)
    z = (sr - sr_benchmark) * np.sqrt(n_obs - 1) / denom
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, var_trial_sr: float) -> float:
    if n_trials < 2:
        return 0.0
    a = stats.norm.ppf(1.0 - 1.0 / n_trials)
    b = stats.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(var_trial_sr) * ((1 - EULER_GAMMA) * a + EULER_GAMMA * b))


def deflated_sharpe_ratio(best_returns: np.ndarray, trial_srs: np.ndarray) -> float:
    """DSR of the selected strategy given the per-period Sharpe ratios of all trials."""
    r = np.asarray(best_returns, dtype=float)
    trial_srs = np.asarray(trial_srs, dtype=float)
    sr0 = expected_max_sharpe(len(trial_srs), float(trial_srs.var(ddof=1)))
    return probabilistic_sharpe_ratio(
        sharpe(r), len(r), float(stats.skew(r)), float(stats.kurtosis(r, fisher=False)), sr0
    )


def pbo_cscv(perf: np.ndarray, n_blocks: int = 16) -> float:
    """Probability of backtest overfitting.

    ``perf`` is a (T periods x N configurations) matrix of returns. For every split of the S
    blocks into equal in-sample/out-of-sample halves, take the in-sample best configuration
    and record its out-of-sample relative rank. PBO is the share of splits in which it ranks
    at or below the out-of-sample median.
    """
    perf = np.asarray(perf, dtype=float)
    t, n = perf.shape
    if n < 2 or n_blocks % 2 or t < n_blocks:
        raise ValueError("need >=2 configurations, even n_blocks, and T >= n_blocks")
    blocks = np.array_split(np.arange(t), n_blocks)
    below = 0
    total = 0
    for is_blocks in combinations(range(n_blocks), n_blocks // 2):
        is_idx = np.concatenate([blocks[i] for i in is_blocks])
        oos_idx = np.concatenate([blocks[i] for i in range(n_blocks) if i not in is_blocks])
        is_sr = _col_sharpe(perf[is_idx])
        oos_sr = _col_sharpe(perf[oos_idx])
        best = int(np.argmax(is_sr))
        rank = stats.rankdata(oos_sr)[best]  # 1..n
        w = rank / (n + 1)
        below += w <= 0.5
        total += 1
    return below / total


def _col_sharpe(m: np.ndarray) -> np.ndarray:
    sd = m.std(axis=0, ddof=1)
    return np.divide(m.mean(axis=0), sd, out=np.zeros(m.shape[1]), where=sd > 0)
