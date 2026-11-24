from datetime import date

import pandas as pd
import pytest

from asof import marketdata


@pytest.fixture
def snapshot_case(tmp_path, monkeypatch):
    paths = (tmp_path / "panel.parquet", tmp_path / "daily.parquet", tmp_path / "manifest.json")
    monkeypatch.setattr(marketdata, "SNAPSHOT_FILES", paths)
    state = {"source": 1}
    monkeypatch.setattr(marketdata, "_snapshot_key", lambda universe: dict(state))
    calls = []

    class Vendor:
        def daily(self, ticker, *, end):
            calls.append(ticker)
            days = [date(2023, 1, 30), date(2023, 1, 31), date(2023, 2, 1),
                    date(2023, 2, 2), date(2023, 2, 3)]
            close = [20.0, 21.0, 22.0, 23.0, 24.0]
            if ticker == "EMPTY":
                days, close = days[:1], close[:1]
            return pd.DataFrame({
                "ticker": ticker, "date": days, "close": close, "adjclose": close,
                "high": [x + 0.1 for x in close], "low": [x - 0.1 for x in close],
            })

        def raw(self, ticker, *, end):
            # One split inside the window and one after the cutoff, which must be dropped.
            return {"meta": {"exchangeTimezoneName": "UTC"}, "events": {"splits": {
                "a": {"date": 1675209600, "numerator": 2, "denominator": 1},
                "b": {"date": 1767225600, "numerator": 3, "denominator": 1}}}}

    monkeypatch.setattr(marketdata.prices, "YahooPrices", Vendor)
    universe = pd.DataFrame({"cik": [1, 2], "ticker": ["SYN", "EMPTY"]})
    return universe, paths, state, calls


def test_price_snapshot_roundtrips_and_loads_without_recomputing(snapshot_case) -> None:
    universe, _paths, _state, calls = snapshot_case
    with pytest.raises(FileNotFoundError, match="price_snapshot"):
        marketdata.load_price_snapshot(universe)
    marketdata.build_price_snapshot(universe)
    before = len(calls)
    panel, returns = marketdata.load_price_snapshot(universe)
    assert len(calls) == before
    assert panel["ticker"].nunique() == 2
    assert set(returns) == {"SYN", "EMPTY"}
    assert returns["EMPTY"].empty
    assert returns["SYN"].index.tolist() == [
        date(2023, 1, 31), date(2023, 2, 1), date(2023, 2, 2), date(2023, 2, 3)]
    assert returns["SYN"].tolist() == pytest.approx([21 / 20 - 1, 22 / 21 - 1, 23 / 22 - 1, 24 / 23 - 1])
    splits = marketdata.load_split_events(universe)
    assert splits[splits["ticker"] == "SYN"][["cik", "ex_date", "ratio"]].values.tolist() == [
        [1, date(2023, 2, 1), 2.0]]


def test_price_snapshot_refuses_changed_sources_and_corrupt_outputs(snapshot_case) -> None:
    universe, paths, state, _calls = snapshot_case
    marketdata.build_price_snapshot(universe)
    state["source"] = 2
    with pytest.raises(ValueError, match="Stale price snapshot"):
        marketdata.load_price_snapshot(universe)
    state["source"] = 1
    paths[1].write_bytes(paths[1].read_bytes() + b"corrupt")
    with pytest.raises(ValueError, match="corrupt"):
        marketdata.load_price_snapshot(universe)


def test_price_snapshot_does_not_publish_when_sources_change_during_generation(
    snapshot_case, monkeypatch,
) -> None:
    universe, paths, state, _calls = snapshot_case
    marketdata.build_price_snapshot(universe)
    previous = paths[2].read_bytes()
    original = marketdata.prices.YahooPrices.daily

    def changing(self, ticker, *, end):
        state["source"] = 2
        return original(self, ticker, end=end)

    monkeypatch.setattr(marketdata.prices.YahooPrices, "daily", changing)
    with pytest.raises(RuntimeError, match="changed during snapshot"):
        marketdata.build_price_snapshot(universe)
    assert paths[2].read_bytes() == previous


def test_price_snapshot_refuses_post_cutoff_rows_before_writing(snapshot_case, monkeypatch) -> None:
    from asof.periods import HoldoutAccessError

    universe, paths, _state, _calls = snapshot_case
    original = marketdata.prices.YahooPrices.daily

    def future(self, ticker, *, end):
        frame = original(self, ticker, end=end)
        frame.loc[0, "date"] = date(2024, 8, 1)
        return frame

    monkeypatch.setattr(marketdata.prices.YahooPrices, "daily", future)
    with pytest.raises(HoldoutAccessError):
        marketdata.build_price_snapshot(universe)
    assert not list(paths[0].parent.iterdir())
