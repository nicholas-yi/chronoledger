"""Verified, lossless development-price snapshots; raw vendor data stays local."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from httpx import HTTPError

from asof import backtest, ledger, prices
from asof.config import DATA_DIR
from asof.periods import DEV_RETURN_CUTOFF, price_end_allowed

SNAPSHOT_FILES = (
    DATA_DIR / "h0_monthly_prices.parquet",
    DATA_DIR / "h0_daily_returns.parquet",
    DATA_DIR / "h0_price_snapshot.json",
)
REBUILD = "run python scripts/h0_data.py price_snapshot"
logger = logging.getLogger(__name__)


def _snapshot_key(universe: pd.DataFrame) -> dict[str, Any]:
    vendor = prices.YahooPrices()
    files = {t: vendor.cache_path(t, end=DEV_RETURN_CUTOFF) for t in universe["ticker"]}
    sources = [Path(__file__), Path(prices.__file__), Path(backtest.__file__)]
    return {
        "cutoff": DEV_RETURN_CUTOFF.isoformat(),
        "universe": ledger.config_hash({"rows": universe[["cik", "ticker"]].to_dict("records")}),
        "raw_prices": {t: ledger.file_sha256(p) if p.exists() else None for t, p in files.items()},
        "processing_code": {p.name: ledger.file_sha256(p) for p in sources},
        "environment": ledger.lineage()["environment"],
    }


def _read_snapshot(metadata: dict[str, Any], panel_path: Path, daily_path: Path):
    panel = pd.read_parquet(panel_path)
    daily = pd.read_parquet(daily_path)
    if not panel.empty:
        price_end_allowed(max(panel["last_day"]))
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    if not daily.empty:
        price_end_allowed(max(daily["date"]))
    groups = {
        t: g.set_index("date")["return"].rename("adjclose")
        for t, g in daily.groupby("ticker", sort=False)
    }
    expected = {t for t, info in metadata["series"].items() if info["rows"]}
    if set(groups) != expected:
        raise ValueError(f"Incomplete price snapshot; {REBUILD}")
    returns = {}
    for ticker, info in metadata["series"].items():
        if info["rows"]:
            series = groups[ticker]
            if len(series) != info["rows"]:
                raise ValueError(f"Price snapshot row count differs; {REBUILD}")
        else:
            series = pd.Series(
                [], index=pd.Index([], dtype=object, name="date"), dtype=float, name="adjclose")
        series.attrs["excluded_price_returns"] = info["excluded_price_returns"]
        returns[ticker] = series
    return panel, returns


def load_price_snapshot(universe: pd.DataFrame):
    """Refuse absent, stale, corrupt, or post-cutoff snapshots; never silently rebuild."""
    price_end_allowed(DEV_RETURN_CUTOFF)
    panel_path, daily_path, manifest_path = SNAPSHOT_FILES
    if not manifest_path.exists():
        raise FileNotFoundError(f"No processed price snapshot; {REBUILD}")
    metadata = json.loads(manifest_path.read_text())
    if metadata.get("schema_version") != 1 or metadata["inputs"] != _snapshot_key(universe):
        raise ValueError(f"Stale price snapshot (data, universe, code, or runtime changed); {REBUILD}")
    for path in (panel_path, daily_path):
        if not path.exists() or ledger.file_sha256(path) != metadata["outputs"][path.name]:
            raise ValueError(f"Price snapshot missing or corrupt: {path.name}; {REBUILD}")
    panel, returns = _read_snapshot(metadata, panel_path, daily_path)
    excluded = sum(s.attrs["excluded_price_returns"] for s in returns.values())
    if excluded:
        logger.warning("Price snapshot retains %d explicitly excluded unusable daily ratios", excluded)
    return panel, returns


def build_price_snapshot(universe: pd.DataFrame) -> None:
    """Build after acquisition; verify unchanged sources and exact round-trip values before publish."""
    price_end_allowed(DEV_RETURN_CUTOFF)
    key = _snapshot_key(universe)
    vendor = prices.YahooPrices()
    frames, returns = [], {}
    for ticker in universe["ticker"]:
        try:
            daily = vendor.daily(ticker, end=DEV_RETURN_CUTOFF)
        except HTTPError as exc:
            logger.warning("prices: %s failed: %r", ticker, exc)
            continue
        if daily.empty:
            continue
        price_end_allowed(max(daily["date"]))
        returns[ticker] = prices.daily_returns(daily.set_index("date")).dropna()
        frames.append(daily[daily["date"] >= pd.Timestamp("2022-11-01").date()])
    if not frames:
        raise ValueError("No guarded price observations are available for this universe")
    panel = backtest.monthly_panel(pd.concat(frames, ignore_index=True)).merge(
        universe[["cik", "ticker"]], on="ticker")
    parts = [
        r.rename("return").rename_axis("date").reset_index().assign(ticker=t)
        for t, r in returns.items() if not r.empty
    ]
    daily = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame({
        "date": pd.Series(dtype=object), "return": pd.Series(dtype=float),
        "ticker": pd.Series(dtype=str),
    })
    if _snapshot_key(universe) != key:
        raise RuntimeError(f"Price inputs changed during snapshot generation; {REBUILD}")
    panel_path, daily_path, manifest_path = SNAPSHOT_FILES
    temporary = [p.with_suffix(".tmp") for p in SNAPSHOT_FILES]
    for path in SNAPSHOT_FILES:
        path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(temporary[0], index=False)
    daily.to_parquet(temporary[1], index=False)
    metadata = {
        "schema_version": 1, "inputs": key,
        "outputs": {
            panel_path.name: ledger.file_sha256(temporary[0]),
            daily_path.name: ledger.file_sha256(temporary[1]),
        },
        "series": {t: {"rows": len(r), "excluded_price_returns": r.attrs["excluded_price_returns"]}
                   for t, r in returns.items()},
        "generation_lineage": ledger.lineage(),
    }
    serialized = json.dumps(metadata, indent=2)
    restored_panel, restored_returns = _read_snapshot(
        json.loads(serialized), temporary[0], temporary[1])
    if not panel.equals(restored_panel) or any(
        not r.equals(restored_returns[t])
        or r.attrs["excluded_price_returns"] != restored_returns[t].attrs["excluded_price_returns"]
        for t, r in returns.items()
    ):
        raise RuntimeError("Processed price snapshot did not round-trip exactly")
    temporary[2].write_text(serialized)
    temporary[0].replace(panel_path)
    temporary[1].replace(daily_path)
    temporary[2].replace(manifest_path)
    print(f"price snapshot: verified {len(panel)} monthly rows and {len(returns)} daily series",
          file=sys.stderr, flush=True)
