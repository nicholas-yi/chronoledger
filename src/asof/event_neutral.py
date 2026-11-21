"""Event-time neutralization: each filing's residual uses only filings known before its day.

For an event accepted on Eastern calendar day ``d``, the reference set is every filing
accepted in ``[start(d) - window, start(d))``, where ``start(d)`` is 00:00 ET. The model
regresses the signal on log market cap, a prior-year M&A flag and SIC2 dummies in that set,
and the event's residual is its own signal minus the fitted value. Nothing accepted on or
after the event's day, including same-day filings, can influence it.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd

from asof.timeutil import ET

CONTROLS = ("log_mcap", "ma_flag")


def day_start_utc(knowledge_time: pd.Series) -> pd.Series:
    local = knowledge_time.dt.tz_convert(ET)
    return pd.Series([pd.Timestamp(datetime.combine(d, time(0), tzinfo=ET)).tz_convert("UTC")
                      for d in local.dt.date], index=knowledge_time.index)


def _design(frame: pd.DataFrame, levels: list[str]) -> np.ndarray:
    dummies = np.column_stack([(frame["sic_group"] == level).to_numpy(float) for level in levels[1:]]) \
        if len(levels) > 1 else np.empty((len(frame), 0))
    return np.column_stack([np.ones(len(frame)), frame[list(CONTROLS)].to_numpy(float), dummies])


def _group(codes: pd.Series, kept: set[str]) -> pd.Series:
    codes = codes.astype(str)
    return codes.where(codes.isin(kept), "other")


def trailing_residuals(events: pd.DataFrame, signal: str, *, window: timedelta = timedelta(days=365),
                       min_reference: int = 200, min_level: int = 5) -> pd.Series:
    """Out-of-sample residuals; NaN when the reference set or the event's industry is too thin.

    ``events`` needs ``knowledge_time`` (tz-aware), ``signal``, ``sic2`` and the CONTROLS.
    SIC2 codes with fewer than ``min_level`` reference filings share one "other" level, which
    is itself kept only when it reaches ``min_level``.
    """
    complete = events.dropna(subset=[signal, "sic2", *CONTROLS])
    starts = day_start_utc(complete["knowledge_time"])
    times = complete["knowledge_time"]
    out = pd.Series(np.nan, index=events.index)
    for start in sorted(starts.unique()):
        targets = complete[starts == start]
        reference = complete[(times >= start - window) & (times < start)]
        if len(reference) < min_reference:
            continue
        counts = reference["sic2"].astype(str).value_counts()
        kept = set(counts[counts >= min_level].index)
        reference = reference.assign(sic_group=_group(reference["sic2"], kept))
        level_counts = reference["sic_group"].value_counts()
        levels = sorted(level_counts[level_counts >= min_level].index)
        reference = reference[reference["sic_group"].isin(levels)]
        targets = targets.assign(sic_group=_group(targets["sic2"], kept))
        targets = targets[targets["sic_group"].isin(levels)]
        if targets.empty:
            continue
        beta, *_ = np.linalg.lstsq(_design(reference, levels), reference[signal].to_numpy(float), rcond=None)
        out.loc[targets.index] = targets[signal].to_numpy(float) - _design(targets, levels) @ beta
    return out
