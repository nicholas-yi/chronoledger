"""Daily prices (free source) with as-traded reconstruction and coverage auditing.

Yahoo's chart API returns ``close`` adjusted for *all* splits, including future ones, and
``adjclose`` adjusted for splits and dividends. Using either as a price *level* (for a $5 filter or
market cap) leaks future corporate actions. ``as_traded_close`` undoes splits that occurred after
each date. Returns use ``adjclose`` ratios, which is standard and leak-free for total returns.

Raw vendor data is cached under data/ for personal research only and is never redistributed.
"""

from __future__ import annotations

import gzip
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from asof.config import RAW_DIR

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def _yahoo_symbol(ticker: str) -> str:
    return ticker.replace(".", "-").upper()


class YahooPrices:
    def __init__(self, cache_dir: Path | None = None, min_interval: float = 0.5) -> None:
        self.cache_dir = cache_dir or RAW_DIR / "yahoo"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._last = 0.0
        self._http = httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=60.0)

    def raw(self, ticker: str, *, end: date | None = None, holdout_opened: bool = False,
            refresh: bool = False) -> dict | None:
        """Fetch daily history; with ``end``, price rows after ``end`` are stripped before caching.

        Yahoo adjusts *all* prices for every split up to today. To reverse that adjustment
        (as-traded reconstruction) we need split *events* after ``end`` as well. So the request
        spans the full history, every quote after ``end`` is discarded in memory, and only the
        split events (date and ratio) are kept. No post-``end`` price or dividend reaches disk.
        """
        from asof.periods import price_end_allowed

        symbol = _yahoo_symbol(ticker)
        if end is not None:
            price_end_allowed(end, holdout_opened)
            path = self.cache_dir / f"{symbol}_to{end:%Y%m%d}_v2.json.gz"
        else:
            path = self.cache_dir / f"{symbol}.json.gz"
        period2 = int(datetime.now(timezone.utc).timestamp())
        if path.exists() and not refresh:
            payload = json.loads(gzip.decompress(path.read_bytes()))
            return payload or None
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        params = {
            "period1": "0",
            "period2": str(period2),
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
        resp = self._http.get(YAHOO_CHART.format(symbol=symbol), params=params)
        payload: dict = {}
        if resp.status_code == 200:
            result = resp.json().get("chart", {}).get("result")
            payload = result[0] if result else {}
        elif resp.status_code not in (400, 404):  # 400/404: no data for this symbol and range
            resp.raise_for_status()
        if end is not None and payload:
            payload = _strip_after(payload, end)
        path.write_bytes(gzip.compress(json.dumps(payload).encode()))
        return payload or None

    def daily(self, ticker: str, *, end: date | None = None, holdout_opened: bool = False) -> pd.DataFrame:
        payload = self.raw(ticker, end=end, holdout_opened=holdout_opened)
        if not payload or "timestamp" not in payload:
            return pd.DataFrame()
        quote = payload["indicators"]["quote"][0]
        adj = payload["indicators"].get("adjclose", [{}])[0].get("adjclose")
        tz = payload.get("meta", {}).get("exchangeTimezoneName", "America/New_York")
        dates = pd.to_datetime(payload["timestamp"], unit="s", utc=True).tz_convert(tz).date
        df = pd.DataFrame(
            {
                "date": dates,
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "close_split_adj": quote.get("close"),
                "adjclose": adj,
                "volume": quote.get("volume"),
            }
        ).dropna(subset=["close_split_adj", "adjclose"])
        splits = splits_from_payload(payload)
        df["close"] = as_traded_close(df["date"].tolist(), df["close_split_adj"].to_numpy(), splits)
        factor = df["close"] / df["close_split_adj"]
        for col in ("open", "high", "low"):
            df[col] = df[col] * factor
        df["ticker"] = ticker.upper()
        if end is not None:
            df = df[df["date"] <= end]
        return df.drop_duplicates("date", keep="last").reset_index(drop=True)


def _strip_after(payload: dict, end: date) -> dict:
    """Drop every quote and dividend after ``end``; keep all split events (dates and ratios)."""
    tz = payload.get("meta", {}).get("exchangeTimezoneName", "America/New_York")
    ts = payload.get("timestamp") or []
    days = pd.to_datetime(ts, unit="s", utc=True).tz_convert(tz).date if ts else []
    keep = [i for i, d in enumerate(days) if d <= end]
    out = {k: v for k, v in payload.items() if k not in ("timestamp", "indicators", "events")}
    out["timestamp"] = [ts[i] for i in keep]
    ind = payload.get("indicators", {})
    out["indicators"] = {
        name: [{k: [s[i] for i in keep] for k, s in block.items()} for block in blocks]
        for name, blocks in ind.items()
    }
    events = payload.get("events", {})
    out["events"] = {"splits": events.get("splits", {})}
    cutoff = int(datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc).timestamp())
    out["events"]["dividends"] = {k: v for k, v in events.get("dividends", {}).items() if v.get("date", 0) <= cutoff}
    out["stripped_after"] = end.isoformat()
    return out


def splits_from_payload(payload: dict) -> list[tuple[date, float]]:
    """(ex-date, ratio) where ratio = numerator/denominator, e.g. 4.0 for a 4-for-1 split."""
    events = payload.get("events", {}).get("splits", {}) or {}
    tz = payload.get("meta", {}).get("exchangeTimezoneName", "America/New_York")
    out = []
    for ev in events.values():
        num, den = ev.get("numerator"), ev.get("denominator")
        if not num or not den:
            continue
        day = pd.Timestamp(ev["date"], unit="s", tz="UTC").tz_convert(tz).date()
        out.append((day, float(num) / float(den)))
    return sorted(out)


def as_traded_close(
    dates: list[date], split_adjusted_close: np.ndarray, splits: list[tuple[date, float]]
) -> np.ndarray:
    """Undo split adjustments: multiply by the product of ratios of splits after each date.

    A split with ex-date d applies to prices strictly before d.
    """
    factors = np.ones(len(dates))
    for ex_date, ratio in splits:
        mask = np.array([d < ex_date for d in dates])
        factors[mask] *= ratio
    return np.asarray(split_adjusted_close, dtype=float) * factors


def daily_returns(df: pd.DataFrame) -> pd.Series:
    """Total returns from dividend- and split-adjusted closes."""
    return df["adjclose"].pct_change()
