"""Shared H0 (Lazy Prices) development inputs and formation-time neutralization."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from asof.backtest import Config, clean_shares, values_as_of
from asof.config import DATA_DIR
from asof.events import neutralize
from asof.marketdata import SNAPSHOT_FILES, load_price_snapshot, load_split_events
from asof.periods import DEV_END, DEV_START
from asof.timeutil import close_time_utc

INPUTS = [DATA_DIR / n for n in ("h0_universe.parquet", "h0_signals.parquet", "h0_shares.parquet",
                                 "bulk_entities.parquet", "bulk_filings.parquet",
                                 "h0_market_inputs.json", "h0_splits.parquet")] + list(SNAPSHOT_FILES)


def load_inputs(signals: Path = DATA_DIR / "h0_signals.parquet"):
    uni = pd.read_parquet(DATA_DIR / "h0_universe.parquet")
    sig = pd.read_parquet(signals)
    sig["knowledge_time"] = pd.to_datetime(sig["knowledge_time"], utc=True)
    lo = datetime.combine(DEV_START, datetime.min.time(), tzinfo=UTC)
    hi = datetime.combine(DEV_END, datetime.max.time(), tzinfo=UTC)
    sig = sig[(sig["knowledge_time"] >= lo) & (sig["knowledge_time"] <= hi)].copy()
    sig["change"] = 1.0 - sig["cos_full"]
    shares = pd.read_parquet(DATA_DIR / "h0_shares.parquet")
    shares["knowledge_time"] = pd.to_datetime(shares["knowledge_time"], utc=True)
    splits = load_split_events(uni)
    shares = clean_shares(shares, splits=splits)  # point-in-time removal of share-count typos (F3)
    ent = pd.read_parquet(DATA_DIR / "bulk_entities.parquet")[["cik", "sic"]]
    fil = pd.read_parquet(DATA_DIR / "bulk_filings.parquet")
    ma = fil[(fil["form"] == "8-K") & fil["items"].fillna("").str.contains(r"\b2\.01\b")][["cik", "knowledge_time"]]
    panel, daily_ret = load_price_snapshot(uni)
    return uni, sig, shares, ent, ma, panel, daily_ret, splits


def neutralize_formations(
    snapshots: dict[pd.Period, pd.DataFrame],
    ent: pd.DataFrame,
    ma: pd.DataFrame,
    bp: pd.DataFrame,
    cfg: Config,
) -> dict[pd.Period, pd.DataFrame]:
    """Neutralize formation snapshots: size/events are as-of; SIC is the supplied fixed mapping."""
    if not snapshots:
        return {}
    rows = pd.concat([
        g.assign(as_of=close_time_utc(max(g["last_day"]))) for g in snapshots.values()
    ], ignore_index=True).merge(ent, on="cik", how="left")
    rows["sic2"] = rows["sic"].astype(str).str[:2]
    rows["mcap_musd"] = rows["shares"] * rows["close"] / 1e6
    rows["log_mcap"] = np.log(rows["mcap_musd"].where(rows["mcap_musd"] > 0) * 1e6)
    rows = values_as_of(
        rows, ma.assign(ma_time=ma["knowledge_time"]), ["ma_time"], allow_exact_matches=False)
    rows["ma_flag"] = (rows["ma_time"] >= rows["as_of"] - pd.Timedelta(days=365)).astype(float)
    eligible = ((rows["close"] >= cfg.min_price)
                & (rows["mcap_musd"] >= rows["month"].map(bp[cfg.size_pct])))
    rows["neg_change_n"] = np.nan
    for _, group in rows[eligible].groupby("month"):
        rows.loc[group.index, "neg_change_n"] = -neutralize(
            group, "change", "sic2", ["log_mcap", "ma_flag"])
    return {m: g.drop(columns=["as_of"]) for m, g in rows.groupby("month")}
