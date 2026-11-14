import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from asof.backtest import Config, formation_snapshots, latest_as_of
from asof.events import neutralize


def _script():
    spec = importlib.util.spec_from_file_location(
        "h0_script", Path(__file__).resolve().parents[1] / "scripts" / "h0_backtest.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


def test_batched_neutralization_matches_monthly_reference_with_sparse_controls() -> None:
    script = _script()
    rng = np.random.default_rng(42)
    sig = pd.DataFrame({
        "cik": list(range(60)) * 2, "change": rng.normal(size=120),
        "knowledge_time": [pd.Timestamp("2023-03-15", tz="UTC")] * 60
                          + [pd.Timestamp("2023-04-15", tz="UTC")] * 60,
    })
    ent = pd.DataFrame({"cik": range(60), "sic": [str(1000 + i % 4 * 100) for i in range(60)]})
    shares = pd.DataFrame({
        "cik": list(range(59)) * 2, "val": rng.uniform(1e6, 1e8, 118),
        "knowledge_time": [pd.Timestamp("2023-01-01", tz="UTC")] * 59
                          + [pd.Timestamp("2023-04-01", tz="UTC")] * 59,
    })
    panel = pd.DataFrame({
        "cik": list(range(58)) * 2, "close": rng.uniform(10, 100, 116),
        "month": [pd.Period("2023-02", "M")] * 58 + [pd.Period("2023-03", "M")] * 58,
    })
    ma = pd.DataFrame({"cik": [1, 2, 3, 4], "knowledge_time": pd.to_datetime([
        "2022-03-15", "2023-03-15", "2023-04-15", "2023-04-01",
    ], utc=True)})
    expected = sig.merge(ent, on="cik", how="left")
    expected["sic2"] = expected["sic"].astype(str).str[:2]
    expected["month"] = expected["knowledge_time"].dt.tz_localize(None).dt.to_period("M")
    expected["change_n"] = np.nan
    for month, group in expected.groupby("month"):
        as_of = group["knowledge_time"].max()
        known = latest_as_of(shares, "cik", as_of, ["val"])
        px = panel[panel["month"] == month - 1][["cik", "close"]]
        controls = group.merge(known, on="cik", how="left").merge(px, on="cik", how="left")
        controls.index = group.index
        controls["log_mcap"] = np.log(controls["val"] * controls["close"])
        recent = ma[(ma["knowledge_time"] < as_of)
                    & (ma["knowledge_time"] >= as_of - pd.Timedelta(days=365))]
        controls["ma_flag"] = controls["cik"].isin(set(recent["cik"])).astype(float)
        expected.loc[group.index, "change_n"] = neutralize(
            controls, "change", "sic2", ["log_mcap", "ma_flag"])
    actual = script.add_neutral(sig, shares, ent, ma, panel)
    pd.testing.assert_frame_equal(actual, expected, atol=1e-12, rtol=1e-12)
    no_ma = script.add_neutral(sig, shares, ent, ma.iloc[:0], panel)
    assert no_ma["change_n"].notna().sum() == 116


def test_formation_neutralization_ignores_post_close_events_and_future_returns() -> None:
    script = _script()
    rng = np.random.default_rng(7)
    month = pd.Period("2023-03", "M")
    t = pd.Timestamp("2023-03-01", tz="UTC")
    late = pd.Timestamp("2023-03-31 21:00:00", tz="UTC")
    sig = pd.DataFrame({"cik": range(60), "change": rng.uniform(0, 1, 60), "knowledge_time": t})
    shares = pd.DataFrame({"cik": range(60), "val": rng.uniform(1e8, 2e8, 60), "knowledge_time": t})
    panel = pd.DataFrame({
        "cik": range(60), "ticker": [f"S{i}" for i in range(60)], "month": month,
        "last_day": pd.Timestamp("2023-03-31").date(), "close": rng.uniform(20, 100, 60),
        "ret_next": rng.normal(0, 0.05, 60), "spread": 0.01,
    })
    ent = pd.DataFrame({"cik": range(60), "sic": [str(1000 + i % 4 * 1000) for i in range(60)]})
    ma = pd.DataFrame({"cik": [1, 3], "knowledge_time": pd.to_datetime(
        ["2023-03-02", "2023-03-03"], utc=True)})
    bp = pd.DataFrame({"p20": [700.0]}, index=pd.PeriodIndex([month]))
    snapshots = formation_snapshots(sig, shares, panel)
    expected = script.neutralize_formations(snapshots, ent, ma, bp, Config())[month]
    sig = pd.concat([sig, pd.DataFrame({"cik": [0], "change": [1000.0], "knowledge_time": [late]})])
    shares = pd.concat([shares, pd.DataFrame({"cik": [0], "val": [1e15], "knowledge_time": [late]})])
    ma = pd.concat([ma, pd.DataFrame({"cik": [0], "knowledge_time": [late]})])
    panel.loc[0, "ret_next"] = np.nan
    snapshots = formation_snapshots(sig, shares, panel)
    actual = script.neutralize_formations(snapshots, ent, ma, bp, Config())[month]
    columns = ["cik", "shares", "neg_change_n", "ma_flag"]
    pd.testing.assert_frame_equal(actual[columns], expected[columns], rtol=1e-12, atol=1e-12)


def test_monthly_series_persistence_does_not_change_summary(monkeypatch) -> None:
    script = _script()
    months = pd.period_range("2023-01", "2024-06", freq="M")
    panel = pd.DataFrame({"month": months})
    bp = pd.DataFrame({"p20": 0.0}, index=months)
    factors = pd.DataFrame(np.random.default_rng(2).normal(0, 0.01, (20, 6)),
                           index=pd.period_range("2023-01", periods=20, freq="M"),
                           columns=script.FACTORS)

    def portfolios(month, *args, **kwargs):
        rng = np.random.default_rng(month.ordinal)
        return pd.DataFrame({
            "ticker": [f"S{i}" for i in range(50)], "q": np.repeat(np.arange(1, 6), 10),
            "w": 0.1, "ret_next": rng.normal(0, 0.02, 50),
            "cos_full": rng.normal(size=50), "spread": 0.001,
        })

    monkeypatch.setattr(script, "form_portfolios", portfolios)
    cfg = Config()
    plain = script.monthly_test(cfg, None, None, panel, bp, factors)
    series = []
    persisted = script.monthly_test(cfg, None, None, panel, bp, factors, series_out=series)
    assert persisted == plain
    assert len(series) == persisted["months"] == 18
    assert [r["return_month"] for r in series] == [str(m + 1) for m in months]
    assert np.mean([r["ls_net"] for r in series]) == persisted["mean_net"]
    assert set(series[0]) == {"return_month", "ls_net", "ls_gross"}
