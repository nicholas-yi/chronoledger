from datetime import date

import numpy as np
import pandas as pd
import pytest

from asof.prices import as_traded_close


def test_split_is_undone_only_before_ex_date() -> None:
    dates = [date(2020, 8, 27), date(2020, 8, 28), date(2020, 8, 31), date(2020, 9, 1)]
    # Apple 4-for-1 split, ex-date 2020-08-31; vendor shows split-adjusted closes.
    adjusted = np.array([125.0, 124.8, 129.0, 134.2])
    traded = as_traded_close(dates, adjusted, [(date(2020, 8, 31), 4.0)])
    assert traded.tolist() == pytest.approx([500.0, 499.2, 129.0, 134.2])


def test_multiple_splits_compound() -> None:
    dates = [date(2010, 1, 4), date(2015, 1, 5), date(2021, 1, 4)]
    adjusted = np.array([1.0, 1.0, 1.0])
    splits = [(date(2014, 6, 9), 7.0), (date(2020, 8, 31), 4.0)]
    assert as_traded_close(dates, adjusted, splits).tolist() == [28.0, 4.0, 1.0]


def test_reverse_split() -> None:
    dates = [date(2019, 1, 2), date(2019, 6, 3)]
    adjusted = np.array([10.0, 10.0])
    assert as_traded_close(dates, adjusted, [(date(2019, 3, 1), 0.1)]).tolist() == [1.0, 10.0]


def test_no_splits_is_identity() -> None:
    dates = [date(2019, 1, 2)]
    assert as_traded_close(dates, np.array([42.0]), []).tolist() == [42.0]


def test_price_requests_past_dev_cutoff_are_refused(tmp_path) -> None:
    from asof.periods import DEV_RETURN_CUTOFF, HoldoutAccessError
    from asof.prices import YahooPrices

    y = YahooPrices(cache_dir=tmp_path)
    with pytest.raises(HoldoutAccessError):
        y.raw("AAPL", end=date(2024, 8, 1))
    with pytest.raises(HoldoutAccessError):
        y.daily("AAPL", end=date(2026, 1, 1))
    assert date(2024, 7, 31) == DEV_RETURN_CUTOFF


def test_guarded_payload_does_not_cache_current_price_metadata() -> None:
    from asof.prices import _strip_after

    payload = {"meta": {"exchangeTimezoneName": "UTC", "regularMarketPrice": 9999,
                        "fiftyTwoWeekHigh": 12345}, "timestamp": [],
               "indicators": {}, "events": {}}
    out = _strip_after(payload, date(2024, 7, 31))
    assert out["meta"] == {"exchangeTimezoneName": "UTC"}


def test_listing_after_cutoff_with_future_split_is_an_empty_history(tmp_path, monkeypatch) -> None:
    from asof.periods import DEV_RETURN_CUTOFF
    from asof.prices import YahooPrices

    y = YahooPrices(cache_dir=tmp_path)
    payload = {"meta": {"exchangeTimezoneName": "UTC"}, "timestamp": [],
               "indicators": {"quote": [{"open": [], "high": [], "low": [], "close": [], "volume": []}],
                              "adjclose": [{"adjclose": []}]},
               "events": {"splits": {"s": {"date": 1751328000, "numerator": 2, "denominator": 1}}}}
    monkeypatch.setattr(y, "raw", lambda *args, **kwargs: payload)
    assert y.daily("SYNTHETIC", end=DEV_RETURN_CUTOFF).empty


def test_daily_returns_reject_unusable_ratios_and_log_exclusions(caplog) -> None:
    from asof.prices import daily_returns

    frame = pd.DataFrame({
        "adjclose": [10.0, 11.0, 0.0, 10.0, -10.0, 10.0, np.nan, 11.0, 12.0],
        "ticker": "SYNTHETIC",
    })
    result = daily_returns(frame)
    assert result.dropna().tolist() == pytest.approx([0.1, 12 / 11 - 1])
    assert result.dropna().attrs["excluded_price_returns"] == 4
    assert "SYNTHETIC: excluded 4 unusable price returns" in caplog.text
