import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from asof.backtest import Config, formation_snapshots
from asof.h0 import neutralize_formations


def _script():
    spec = importlib.util.spec_from_file_location(
        "h0_script", Path(__file__).resolve().parents[1] / "scripts" / "h0_backtest.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


def test_formation_neutralization_ignores_post_close_events_and_future_returns() -> None:
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
    expected = neutralize_formations(snapshots, ent, ma, bp, Config())[month]
    sig = pd.concat([sig, pd.DataFrame({"cik": [0], "change": [1000.0], "knowledge_time": [late]})])
    shares = pd.concat([shares, pd.DataFrame({"cik": [0], "val": [1e15], "knowledge_time": [late]})])
    ma = pd.concat([ma, pd.DataFrame({"cik": [0], "knowledge_time": [late]})])
    panel.loc[0, "ret_next"] = np.nan
    snapshots = formation_snapshots(sig, shares, panel)
    actual = neutralize_formations(snapshots, ent, ma, bp, Config())[month]
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
