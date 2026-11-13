from dataclasses import replace
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from asof.backtest import (
    Config,
    abdi_ranaldo_spread,
    form_portfolios,
    formation_snapshots,
    latest_as_of,
    long_short,
    monthly_panel,
    values_as_of,
)


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


@pytest.mark.parametrize("exact", [False, True])
@pytest.mark.parametrize("query_unit", ["us", "ns"])
def test_batch_asof_matches_reference_and_preserves_query_order(exact, query_unit) -> None:
    t = pd.Timestamp("2023-03-01", tz="UTC")
    facts = pd.DataFrame({"cik": [1, 2, 1], "val": [10, 20, 30],
                         "knowledge_time": [t, t, t + pd.Timedelta(days=1)]})
    queries = pd.DataFrame({"cik": [1, 2, 1, 3], "as_of": [
        t + pd.Timedelta(days=2), t, t - pd.Timedelta(days=1), t,
    ]}, index=[8, 2, 9, 1])
    facts["knowledge_time"] = facts["knowledge_time"].dt.as_unit("us")
    queries["as_of"] = queries["as_of"].dt.as_unit(query_unit)
    result = values_as_of(queries, facts, ["val"], allow_exact_matches=exact)
    expected = []
    for r in queries.itertuples():
        cutoff = r.as_of if exact else r.as_of - pd.Timedelta(nanoseconds=1)
        known = latest_as_of(facts, "cik", cutoff, ["val"]).set_index("cik")["val"]
        expected.append(known.get(r.cik, np.nan))
    pd.testing.assert_series_equal(
        result["val"], pd.Series(expected, index=queries.index, name="val"))
    assert values_as_of(queries, facts.iloc[:0], ["val"])["val"].isna().all()


@pytest.mark.parametrize("signal", ["cos_full", "neg_change_n"])
@pytest.mark.parametrize("weighting", ["value", "equal"])
def test_snapshots_match_portfolios_with_ties_missing_and_boundary_data(signal, weighting) -> None:
    panel = pd.concat([
        _panel(60).assign(month=pd.Period("2023-03", "M")),
        _panel(60).assign(month=pd.Period("2023-04", "M"), last_day=date(2023, 4, 28)),
    ], ignore_index=True)
    t = pd.Timestamp("2023-03-01", tz="UTC")
    close = pd.Timestamp("2023-03-31 20:00:00", tz="UTC")
    sig = pd.DataFrame({"cik": range(60), "cos_full": np.arange(60) % 10 / 10,
                        "knowledge_time": t})
    sig.loc[3, "knowledge_time"] = close - pd.Timedelta(days=365)
    sig.loc[4, "knowledge_time"] = close - pd.Timedelta(days=365, microseconds=1)
    extra = pd.DataFrame({"cik": [0, 1, 2], "cos_full": [999, 0.01, np.nan],
                          "knowledge_time": [close, close - pd.Timedelta(seconds=1), t + pd.Timedelta(days=1)]})
    sig = pd.concat([sig, extra], ignore_index=True)
    sig["neg_change_n"] = sig["cos_full"] - 0.5
    sig["month"] = sig["knowledge_time"].dt.tz_localize(None).dt.to_period("M")
    shares = pd.DataFrame({"cik": range(59), "val": np.arange(59) * 1e6 + 1e8,
                           "knowledge_time": t})
    shares = pd.concat([shares, pd.DataFrame({
        "cik": [0, 1], "val": [2e8, 1e15],
        "knowledge_time": [close, close + pd.Timedelta(seconds=1)],
    })], ignore_index=True)
    cfg = replace(Config(), signal=signal, weighting=weighting)
    snapshots = formation_snapshots(sig, shares, panel, cfg.max_signal_age_days)
    for month, pm in panel.groupby("month"):
        reference = form_portfolios(month, sig, shares, pm, 700.0, cfg)
        fast = form_portfolios(month, sig, shares, pm, 700.0, cfg, snapshot=snapshots[month])
        pd.testing.assert_frame_equal(
            fast.reset_index(drop=True), reference.reset_index(drop=True), check_dtype=False)


def test_turnover_alignment_matches_concat_reference_with_exits_and_missing_spreads() -> None:
    prev = pd.DataFrame({"ticker": ["A", "B", "C", "D"], "q": [1, 1, 5, 5],
                         "w": [0.4, 0.6, 0.7, 0.3], "ret_next": [-0.1, 0.2, 0.3, -0.1],
                         "spread": [0.03, np.nan, 0.04, 0.06]})
    port = pd.DataFrame({"ticker": ["A", "E", "C", "F"], "q": [1, 1, 5, 5],
                         "w": [0.2, 0.8, 0.5, 0.5], "ret_next": [0.1, 0.2, 0.3, 0.4],
                         "spread": [0.01, 0.02, np.nan, 0.05]})
    got = long_short(port, prev, Config())
    for leg, q in (("long", 5), ("short", 1)):
        cur = port[port["q"] == q].set_index("ticker")
        old = prev[prev["q"] == q].set_index("ticker")
        drift = old["w"] * (1 + old["ret_next"])
        drift /= drift.sum()
        both = pd.concat([cur["w"].rename("new"), drift.rename("old")], axis=1).fillna(0)
        spread = pd.concat([cur["spread"], old["spread"]]).groupby(level=0).last()
        expected = ((both["new"] - both["old"]).abs() * spread.reindex(both.index).fillna(0) / 2).sum()
        assert got[f"{leg}_cost"] == pytest.approx(expected, abs=1e-14)


def test_share_ties_use_latest_reported_date_not_duplicate_confirmation() -> None:
    from asof.backtest import clean_shares

    shares = pd.DataFrame({
        "cik": 1,
        "knowledge_time": pd.to_datetime([
            "2023-01-01", "2023-01-01", "2023-04-01", "2023-04-01", "2023-05-01",
        ], utc=True),
        "end": ["2022-12-31", "2022-11-30", "2023-03-01", "2023-03-31", "2023-04-30"],
        "accn": ["first", "first", "typo", "typo", "later"],
        "val": [90e6, 80e6, 90e9, 91e9, 90e6],
    })
    cleaned = clean_shares(shares)
    assert cleaned["val"].tolist() == [90e6, 90e6]
    assert cleaned["knowledge_time"].tolist() == list(pd.to_datetime(
        ["2023-01-01", "2023-05-01"], utc=True))


def test_formation_membership_and_weights_do_not_depend_on_future_return_availability() -> None:
    panel = _panel()
    t = pd.Timestamp("2023-03-01", tz="UTC")
    sig = pd.DataFrame({"cik": range(50), "cos_full": np.linspace(0, 1, 50),
                        "knowledge_time": t})
    shares = pd.DataFrame({"cik": range(50), "val": 1e8, "knowledge_time": t})
    month = pd.Period("2023-03", "M")
    complete = form_portfolios(month, sig, shares, panel, 700.0, Config())
    panel.loc[0, "ret_next"] = np.nan
    missing = form_portfolios(month, sig, shares, panel, 700.0, Config())
    pd.testing.assert_frame_equal(
        missing[["cik", "q", "w"]].reset_index(drop=True),
        complete[["cik", "q", "w"]].reset_index(drop=True))


@pytest.mark.parametrize("assumption", [0.0, -0.3, -1.0])
def test_missing_returns_use_declared_sensitivity_and_report_counts(assumption) -> None:
    port = pd.DataFrame({"ticker": ["A", "B"], "q": [1, 5], "w": [1.0, 1.0],
                         "ret_next": [np.nan, 0.1], "spread": [0.0, 0.0]})
    result = long_short(port, port, replace(Config(), missing_return=assumption))
    assert result["ls_net"] == pytest.approx(0.1 - assumption)
    assert result["short_missing"] == 1
    assert result["long_missing"] == 0


def test_monthly_panel_matches_window_reference_with_invalid_quotes_and_gaps() -> None:
    rng = np.random.default_rng(12)
    days = pd.bdate_range("2023-01-02", "2023-03-31")
    daily = pd.DataFrame({
        "ticker": np.repeat(["A", "B"], len(days)), "date": list(days.date) * 2,
        "close": rng.uniform(10, 20, 2 * len(days)),
        "high": rng.uniform(20, 25, 2 * len(days)),
        "low": rng.uniform(5, 10, 2 * len(days)),
    })
    daily["adjclose"] = daily["close"]
    daily = daily[~((daily["ticker"] == "B") & (pd.to_datetime(daily["date"]).dt.month == 2))]
    daily.loc[3, "high"] = np.nan
    daily.loc[7, "low"] = 0.0
    daily.loc[11, "close"] = 0.0
    daily.loc[len(days) - 1, "close"] = np.nan
    daily = daily.sample(frac=1, random_state=4)
    ordered = daily.sort_values(["ticker", "date"]).assign(
        month=lambda d: pd.PeriodIndex(pd.to_datetime(d["date"]), freq="M"))
    rows = []
    with np.errstate(divide="ignore", invalid="ignore"):
        for (ticker, month), group in ordered.groupby(["ticker", "month"]):
            rows.append({"ticker": ticker, "month": month, "last_day": group["date"].iloc[-1],
                         "close": group["close"].iloc[-1], "adjclose": group["adjclose"].iloc[-1],
                         "spread": abdi_ranaldo_spread(group)})
        expected = pd.DataFrame(rows)
        expected["ret_next"] = expected.groupby("ticker")["adjclose"].shift(-1) / expected["adjclose"] - 1
        following = expected.groupby("ticker")["month"].shift(-1)
        expected.loc[(following != expected["month"] + 1) | (expected["ret_next"] <= -1), "ret_next"] = np.nan
        actual = monthly_panel(daily)
    pd.testing.assert_frame_equal(actual, expected, rtol=1e-12, atol=1e-12)


def test_monthly_panel_batches_many_small_windows() -> None:
    from time import perf_counter

    daily = pd.DataFrame({
        "ticker": np.repeat(np.arange(5000).astype(str), 4),
        "date": list(pd.bdate_range("2023-03-01", periods=4).date) * 5000,
        "close": 20.0, "adjclose": 20.0, "high": 20.1, "low": 19.9,
    })
    start = perf_counter()
    panel = monthly_panel(daily)
    assert perf_counter() - start < 2.0
    assert len(panel) == 5000
