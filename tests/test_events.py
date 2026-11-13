from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from asof.events import FACTORS, car, event_panel, neutralize, rank_ic


def _factors(n=600, seed=0):
    rng = np.random.default_rng(seed)
    days = [date(2022, 1, 3) + timedelta(days=i) for i in range(n)]
    f = pd.DataFrame(rng.normal(0, 0.01, (n, len(FACTORS))), index=days, columns=FACTORS)
    f["RF"] = 0.0001
    return f


def test_car_recovers_planted_abnormal_return() -> None:
    f = _factors()
    rng = np.random.default_rng(1)
    r = f["RF"] + 1.2 * f["Mkt_RF"] + 0.5 * f["SMB"] + rng.normal(0, 0.002, len(f))
    event = f.index[400]
    r.iloc[401:421] += 0.002  # +4% over 20 days
    assert car(r, f, event, horizon=20) == pytest.approx(0.04, abs=0.01)
    assert abs(car(r, f, f.index[560], horizon=20)) < 0.01  # no planted effect there


def test_car_nan_when_window_incomplete() -> None:
    f = _factors()
    r = f["RF"] + f["Mkt_RF"]
    assert np.isnan(car(r, f, f.index[50], horizon=20))   # not enough estimation history
    assert np.isnan(car(r, f, f.index[-5], horizon=20))   # event window runs past data


def test_event_panel_detects_planted_effect() -> None:
    rng = np.random.default_rng(2)
    n = 2000
    df = pd.DataFrame({"x": rng.normal(size=n), "month": rng.integers(0, 40, n)})
    df["y"] = -0.01 * df["x"] + rng.normal(0, 0.05, n)
    res = event_panel(df, "y", "x", "month")
    assert res.coef == pytest.approx(-0.01, abs=0.004)
    assert res.t_stat < -3 and res.n_clusters == 40


def test_neutralize_removes_industry_and_size() -> None:
    rng = np.random.default_rng(3)
    n = 500
    df = pd.DataFrame({"ind": rng.integers(0, 5, n), "size": rng.normal(size=n)})
    df["sig"] = df["ind"] * 0.3 + 0.5 * df["size"] + rng.normal(0, 0.1, n)
    res = neutralize(df, "sig", "ind", ["size"])
    assert abs(np.corrcoef(res, df["size"])[0, 1]) < 1e-6
    assert res.groupby(df["ind"]).mean().abs().max() < 1e-6


def test_rank_ic() -> None:
    s = pd.Series(range(50), dtype=float)
    assert rank_ic(s, s * 2) == pytest.approx(1.0)
    assert rank_ic(s, -s) == pytest.approx(-1.0)
