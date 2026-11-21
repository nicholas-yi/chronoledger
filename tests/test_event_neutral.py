from datetime import timedelta

import numpy as np
import pandas as pd

from asof.event_neutral import trailing_residuals


def events(seed=0, n=1200):
    rng = np.random.default_rng(seed)
    times = pd.Timestamp("2022-01-03T15:00Z") + pd.to_timedelta(rng.uniform(0, 700, n), unit="D")
    frame = pd.DataFrame({
        "knowledge_time": times, "sic2": rng.choice(["10", "20", "28", "35", "73", "99"], n,
                                                    p=[.3, .3, .2, .1, .095, .005]),
        "log_mcap": rng.normal(20, 2, n), "ma_flag": rng.integers(0, 2, n).astype(float)})
    frame["change"] = 0.01 * frame["log_mcap"] + 0.05 * (frame["sic2"] == "28") + rng.normal(0, .1, n)
    return frame.sort_values("knowledge_time", ignore_index=True)


def test_future_and_same_day_filings_cannot_change_a_residual():
    base = events()
    before = trailing_residuals(base, "change", min_reference=100)
    cut = pd.Timestamp("2023-03-01T05:00Z")
    changed = base.copy()
    later = changed["knowledge_time"] >= cut - timedelta(hours=10)
    changed.loc[later, "change"] += 100.0
    changed.loc[later, "log_mcap"] -= 50.0
    after = trailing_residuals(changed, "change", min_reference=100)
    earlier = base["knowledge_time"] < cut - timedelta(days=1)
    assert earlier.sum() > 100 and before[earlier].notna().sum() > 50
    pd.testing.assert_series_equal(before[earlier], after[earlier])


def test_thin_reference_and_unseen_industries_are_unresolved_not_guessed():
    base = events()
    base["sic2"] = base["sic2"].replace("99", "10")
    base.loc[base.index[-1], "sic2"] = "55"
    residuals = trailing_residuals(base, "change", min_reference=100)
    assert residuals[base["knowledge_time"] < pd.Timestamp("2022-02-01T00:00Z")].isna().all()
    assert np.isnan(residuals.iloc[-1])
    assert residuals.iloc[-2:-1].notna().all() or base["knowledge_time"].iloc[-2].date() == \
        base["knowledge_time"].iloc[-1].date()
    assert np.isfinite(residuals.dropna()).all()


def test_residuals_remove_the_controlled_components():
    base = events(n=3000)
    residuals = trailing_residuals(base, "change", window=timedelta(days=365), min_reference=300)
    late = residuals.notna() & (base["knowledge_time"] > pd.Timestamp("2023-01-01T00:00Z"))
    assert abs(np.corrcoef(residuals[late], base.loc[late, "log_mcap"])[0, 1]) < 0.1
    assert abs(residuals[late & (base["sic2"] == "28")].mean()) < 0.03
