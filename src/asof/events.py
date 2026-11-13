"""Event studies, signal neutralization, and rank information coefficients.

Abnormal returns use FF5+UMD betas estimated over trading days -260..-21 relative to the event's
first tradable close; CARs start the day after that close. All windows must end on or before the
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


def car(
    returns: pd.Series,
    factors: pd.DataFrame,
    event_day: date,
    horizon: int = 60,
    est: tuple[int, int] = (-260, -21),
    min_est: int = 120,
) -> float:
    """Cumulative abnormal return over trading days +1..+horizon after ``event_day``.

    ``returns`` is a daily simple-return series indexed by date (one firm); ``factors`` holds daily
    factors and RF. Returns NaN if the estimation or event window is incomplete.
    """
    data = pd.concat([returns.rename("r"), factors], axis=1, join="inner").dropna()
    days = list(data.index)
    if event_day not in data.index:
        later = [d for d in days if d >= event_day]
        if not later:
            return float("nan")
        event_day = later[0]
    i = days.index(event_day)
    lo, hi = i + est[0], i + est[1]
    if lo < 0 or i + horizon >= len(days):
        return float("nan")
    window = data.iloc[lo:hi + 1]
    if len(window) < min_est:
        return float("nan")
    x = sm.add_constant(window[FACTORS])
    beta = sm.OLS(window["r"] - window["RF"], x).fit().params
    post = data.iloc[i + 1:i + 1 + horizon]
    expected = post["RF"] + (sm.add_constant(post[FACTORS], has_constant="add") @ beta)
    return float((post["r"] - expected).sum())


class CarEngine:
    """Fast CARs: each firm's returns are aligned to the factor calendar once, then every event is
    a slice plus a small least-squares fit. Numerically identical to ``car``."""

    def __init__(self, factors: pd.DataFrame) -> None:
        self.factors = factors
        self.days = list(factors.index)
        self.pos = {d: i for i, d in enumerate(self.days)}
        self.F = factors[FACTORS].to_numpy()
        self.rf = factors["RF"].to_numpy()
        self._cache: dict[str, np.ndarray] = {}

    def _aligned(self, key: str, returns: pd.Series) -> np.ndarray:
        if key not in self._cache:
            self._cache[key] = returns.reindex(self.factors.index).to_numpy(dtype=float)
        return self._cache[key]

    def car(self, key: str, returns: pd.Series, event_day: date, horizon: int = 60,
            est: tuple[int, int] = (-260, -21), min_est: int = 120) -> float:
        import bisect

        r = self._aligned(key, returns)
        idx = np.flatnonzero(~np.isnan(r))  # calendar positions of this firm's valid days
        dpos = bisect.bisect_left(self.days, event_day)  # first calendar day >= event_day
        j = int(np.searchsorted(idx, dpos))  # first valid firm day on/after the event
        if j >= idx.size:
            return float("nan")
        lo, hi = j + est[0], j + est[1]
        if lo < 0 or j + horizon >= idx.size:
            return float("nan")
        e = idx[lo:hi + 1]
        if e.size < min_est:
            return float("nan")
        X = np.column_stack([np.ones(e.size), self.F[e]])
        beta, *_ = np.linalg.lstsq(X, r[e] - self.rf[e], rcond=None)
        p = idx[j + 1:j + 1 + horizon]
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
