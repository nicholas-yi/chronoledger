from datetime import date

import numpy as np
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
    assert DEV_RETURN_CUTOFF == date(2024, 7, 31)
