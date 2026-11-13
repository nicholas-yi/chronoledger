from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from asof.backtest import Config, abdi_ranaldo_spread, form_portfolios, latest_as_of, long_short, monthly_panel


def test_abdi_ranaldo_recovers_known_spread() -> None:
    rng = np.random.default_rng(0)
    n, s = 5000, 0.02
    mid = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    close = mid * np.exp(rng.choice([-1, 1], n) * s / 2)
    high = mid * np.exp(np.abs(rng.normal(0, 0.01, n)) + s / 2)
    low = mid * np.exp(-np.abs(rng.normal(0, 0.01, n)) - s / 2)
    est = abdi_ranaldo_spread(pd.DataFrame({"close": close, "high": high, "low": low}))
    assert est == pytest.approx(s, rel=0.35)


def test_zero_spread_is_nonnegative() -> None:
    p = np.linspace(100, 110, 30)
    assert abdi_ranaldo_spread(pd.DataFrame({"close": p, "high": p, "low": p})) == 0.0


def test_monthly_returns_do_not_bridge_gaps() -> None:
    days = [date(2023, 1, 31), date(2023, 2, 28), date(2023, 4, 28)]
    d = pd.DataFrame({"ticker": "X", "date": days, "close": [10, 11, 12], "adjclose": [10, 11, 12],
                      "high": [10, 11, 12], "low": [10, 11, 12]})
    p = monthly_panel(d)
    assert p["ret_next"].iloc[0] == pytest.approx(0.1)
    assert np.isnan(p["ret_next"].iloc[1])  # March missing -> no Feb->Apr return


def test_latest_as_of_ignores_future_facts() -> None:
    f = pd.DataFrame({"cik": [1, 1], "val": [100, 200],
                      "knowledge_time": [datetime(2023, 1, 5, tzinfo=timezone.utc),
                                         datetime(2023, 3, 5, tzinfo=timezone.utc)]})
    got = latest_as_of(f, "cik", datetime(2023, 2, 1, tzinfo=timezone.utc), ["val"])
    assert got["val"].tolist() == [100]


def _panel(n=50):
    return pd.DataFrame({"ticker": [f"T{i}" for i in range(n)], "cik": range(n),
                         "last_day": [date(2023, 3, 31)] * n, "close": [20.0] * n,
                         "ret_next": np.linspace(-0.05, 0.05, n), "spread": [0.01] * n})


def test_signals_after_formation_close_are_excluded() -> None:
    panel = _panel()
    late = datetime(2023, 3, 31, 21, 0, tzinfo=timezone.utc)  # 17:00 ET, after the close
    early = datetime(2023, 3, 1, tzinfo=timezone.utc)
    sig = pd.DataFrame({"cik": list(range(50)), "cos_full": np.linspace(0, 1, 50),
                        "knowledge_time": [early] * 49 + [late]})
    shares = pd.DataFrame({"cik": range(50), "val": [1e8] * 50, "knowledge_time": [early] * 50})
    port = form_portfolios(pd.Period("2023-03", "M"), sig, shares, panel, 700.0, Config())
    assert 49 not in set(port["cik"])
    assert len(port) == 49


def test_long_short_signs_and_costs() -> None:
    panel = _panel()
    t = datetime(2023, 3, 1, tzinfo=timezone.utc)
    sig = pd.DataFrame({"cik": range(50), "cos_full": np.linspace(0, 1, 50), "knowledge_time": [t] * 50})
    shares = pd.DataFrame({"cik": range(50), "val": [1e8] * 50, "knowledge_time": [t] * 50})
    port = form_portfolios(pd.Period("2023-03", "M"), sig, shares, panel, 700.0, Config())
    r = long_short(port, None, Config())
    # Similarity and next return rise together here, so long-high earns a positive spread.
    assert r["ls_gross"] > 0
    assert r["ls_net"] < r["ls_gross"]


def test_clean_shares_drops_typo_and_accepts_confirmed_split() -> None:
    from asof.backtest import clean_shares

    t = [datetime(2023, m, 1, tzinfo=timezone.utc) for m in (1, 4, 7, 10, 12)]
    df = pd.DataFrame({"cik": 1, "val": [90e6, 90e9, 90e6, 4.5e6, 4.6e6], "knowledge_time": t})
    out = clean_shares(df)
    # 1,000x typo is never accepted; a 20:1 reverse split takes effect only once confirmed.
    assert out["val"].tolist() == [90e6, 90e6, 4.6e6]
    assert out["knowledge_time"].tolist() == [t[0], t[2], t[4]]


def test_returns_below_minus_100pct_are_dropped() -> None:
    days = [date(2023, 1, 31), date(2023, 2, 28)]
    d = pd.DataFrame({"ticker": "X", "date": days, "close": [10, 11], "adjclose": [10.0, -4.0],
                      "high": [10, 11], "low": [10, 11]})
    assert np.isnan(monthly_panel(d)["ret_next"].iloc[0])


def test_strip_after_keeps_future_splits_only() -> None:
    from asof.prices import _strip_after

    ts = [1688140800, 1690819200, 1693497600]  # 2023-06-30, 2023-07-31, 2023-08-31 (UTC)
    payload = {"meta": {"exchangeTimezoneName": "UTC"}, "timestamp": ts,
               "indicators": {"quote": [{"close": [1, 2, 3]}], "adjclose": [{"adjclose": [1, 2, 3]}]},
               "events": {"splits": {"x": {"date": 1693497600, "numerator": 1, "denominator": 10}},
                          "dividends": {"y": {"date": 1693497600, "amount": 0.1}}}}
    out = _strip_after(payload, date(2023, 7, 31))
    assert out["timestamp"] == ts[:2]
    assert out["indicators"]["quote"][0]["close"] == [1, 2]
    assert "x" in out["events"]["splits"] and out["events"]["dividends"] == {}
