"""Event studies, signal neutralization, and rank information coefficients.

Abnormal returns use FF5+UMD betas estimated over trading sessions -260..-21 relative to the
event's first tradable close; CARs cover sessions +1..+h. Windows are fixed on the session calendar. All windows must end on or before the
caller's data cutoff, which the caller enforces with the holdout guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

FACTORS = ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "UMD"]


def _session_window(days: list[date], event_day: date, horizon: int,
                    est: tuple[int, int]) -> tuple[int, int, int] | None:
    """Session positions (event, estimation start, estimation end) on the factor calendar."""
    import bisect

    i = bisect.bisect_left(days, event_day)  # the event's session, or the next one
    if i >= len(days) or i + est[0] < 0 or i + horizon >= len(days):
        return None
    return i, i + est[0], i + est[1]


def car(
    returns: pd.Series,
    factors: pd.DataFrame,
    event_day: date,
    horizon: int = 60,
    est: tuple[int, int] = (-260, -21),
    min_est: int = 120,
) -> float:
    """Cumulative abnormal return over trading sessions +1..+horizon after ``event_day``.

    Windows are fixed on the factor (trading-session) calendar, never on the firm's own
    observations: estimation uses the firm's available returns in sessions ``est`` (at least
    ``min_est``), and the CAR is NaN if any return in the event window is missing, rather than
    extending the window past the requested sessions.
    """
    factors = factors.dropna()
    window = _session_window(list(factors.index), event_day, horizon, est)
    if window is None:
        return float("nan")
    i, lo, hi = window
    r = returns.reindex(factors.index)
    estimation = factors.iloc[lo:hi + 1].assign(r=r.iloc[lo:hi + 1]).dropna()
    post = factors.iloc[i + 1:i + 1 + horizon].assign(r=r.iloc[i + 1:i + 1 + horizon])
    if len(estimation) < min_est or post["r"].isna().any():
        return float("nan")
    x = sm.add_constant(estimation[FACTORS])
    beta = sm.OLS(estimation["r"] - estimation["RF"], x).fit().params
    expected = post["RF"] + (sm.add_constant(post[FACTORS], has_constant="add") @ beta)
    return float((post["r"] - expected).sum())


class CarEngine:
    """Fast CARs with ``car``'s fixed session windows: each firm's returns are aligned to the
    factor calendar once, then every event is a slice plus a small least-squares fit.
    """

    def __init__(self, factors: pd.DataFrame) -> None:
        factors = factors.dropna()
        self.factors = factors
        self.days = list(factors.index)
        self.F = factors[FACTORS].to_numpy()
        self.rf = factors["RF"].to_numpy()
        self._cache: dict[str, np.ndarray] = {}

    def _aligned(self, key: str, returns: pd.Series) -> np.ndarray:
        if key not in self._cache:
            self._cache[key] = returns.reindex(self.factors.index).to_numpy(dtype=float)
        return self._cache[key]

    def car(self, key: str, returns: pd.Series, event_day: date, horizon: int = 60,
            est: tuple[int, int] = (-260, -21), min_est: int = 120) -> float:
        window = _session_window(self.days, event_day, horizon, est)
        if window is None:
            return float("nan")
        i, lo, hi = window
        r = self._aligned(key, returns)
        e = lo + np.flatnonzero(~np.isnan(r[lo:hi + 1]))
        p = np.arange(i + 1, i + 1 + horizon)
        if e.size < min_est or np.isnan(r[p]).any():
            return float("nan")
        X = np.column_stack([np.ones(e.size), self.F[e]])
        beta, *_ = np.linalg.lstsq(X, r[e] - self.rf[e], rcond=None)
        expected = self.rf[p] + np.column_stack([np.ones(p.size), self.F[p]]) @ beta
        return float((r[p] - expected).sum())


@dataclass(frozen=True)
class PanelResult:
    coef: float
    t_stat: float
    n_events: int
    n_clusters: int


def event_panel(df: pd.DataFrame, y: str, x: str, cluster: str, controls: list[str] | None = None) -> PanelResult:
    """OLS of y on x (+controls) with standard errors clustered by ``cluster``."""
    cols = [x, *(controls or [])]
    d = df.dropna(subset=[y, *cols, cluster])
    fit = sm.OLS(d[y], sm.add_constant(d[cols])).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d[cluster])[0]})
    return PanelResult(float(fit.params[x]), float(fit.tvalues[x]), len(d), int(d[cluster].nunique()))


def neutralize(df: pd.DataFrame, signal: str, industry: str, controls: list[str]) -> pd.Series:
    """Residual of ``signal`` on industry dummies plus controls (one cross-section)."""
    d = df.dropna(subset=[signal, industry, *controls])
    if len(d) < 10:
        return pd.Series(np.nan, index=df.index)
    dummies = pd.get_dummies(d[industry].astype(str), prefix="ind", drop_first=True, dtype=float)
    x = sm.add_constant(pd.concat([d[controls].astype(float), dummies], axis=1), has_constant="add")
    resid = sm.OLS(d[signal].astype(float), x).fit().resid
    return resid.reindex(df.index)


def rank_ic(signal: pd.Series, forward_return: pd.Series) -> float:
    d = pd.concat([signal, forward_return], axis=1).dropna()
    if len(d) < 10:
        return float("nan")
    return float(stats.spearmanr(d.iloc[:, 0], d.iloc[:, 1]).statistic)
