"""Point-in-time social-media sentiment (exploratory H7 scaffolding; no data is fetched here).

Three parts, each usable without the others:

- ``XArchiveClient``: X API v2 full-archive search, pay-per-use. It refuses to start unless the
  owner sets ``ASOF_X_BEARER_TOKEN`` and a positive ``ASOF_X_BUDGET_USD``, charges every post read
  against that cap *before* requesting more, and keeps an append-only request log. X's developer
  terms require deleting stored posts deleted on X, so only post IDs, creation times and scores
  are kept; text is scored in memory and discarded.
- ``score_posts``: any ``text -> float in [-1, 1]`` scorer. ``vader_scorer`` uses the VADER
  lexicon (Hutto & Gilbert 2014, MIT), which predates every post it would score.
- ``signals_at_closes``: firm-day signals that use only posts created at least ``buffer``
  before each close, so a signal is always known before the close it trades at.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

PRICE_PER_POST_USD = 0.005
SEARCH_ALL = "https://api.x.com/2/tweets/search/all"
EARLIEST = datetime(2006, 3, 21, tzinfo=UTC)


class BudgetExceeded(RuntimeError):
    pass


def cashtag_query(ticker: str) -> str:
    if not ticker.replace(".", "").replace("-", "").isalnum() or len(ticker) > 10:
        raise ValueError("ticker must be a plain symbol")
    return f"${ticker.upper()} lang:en -is:retweet"


def estimate_cost(posts: int) -> float:
    return round(posts * PRICE_PER_POST_USD, 2)


@dataclass
class XArchiveClient:
    log_path: Path
    transport: httpx.BaseTransport | None = None
    min_interval: float = 1.0
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    spent_usd: float = 0.0
    _last: float | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        token, budget = os.environ.get("ASOF_X_BEARER_TOKEN"), os.environ.get("ASOF_X_BUDGET_USD")
        if not token or not budget:
            raise PermissionError("set ASOF_X_BEARER_TOKEN and ASOF_X_BUDGET_USD; no X request is made otherwise")
        self.budget_usd = float(budget)
        if not self.budget_usd > 0:
            raise PermissionError("ASOF_X_BUDGET_USD must be positive")
        self.client = httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30,
                                   transport=self.transport, follow_redirects=False)

    def _log(self, row: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({**row, "UTC": datetime.now(UTC).isoformat()}) + "\n")

    def search(self, query: str, start: datetime, end: datetime, max_posts: int) -> Iterator[dict]:
        """Yield posts newest-first; never requests a page that could exceed the budget."""
        if not EARLIEST <= start < end or start.tzinfo is None:
            raise ValueError("aware start < end after X's first post required")
        token, read = None, 0
        while read < max_posts:
            page = min(100, max_posts - read)
            if self.spent_usd + page * PRICE_PER_POST_USD > self.budget_usd + 1e-9:
                raise BudgetExceeded(f"next page would exceed the ${self.budget_usd} cap")
            if self._last is not None:
                self.sleep(max(0.0, self.min_interval - (self.clock() - self._last)))
            self._last = self.clock()
            params = {"query": query, "start_time": start.isoformat().replace("+00:00", "Z"),
                      "end_time": end.isoformat().replace("+00:00", "Z"), "max_results": max(10, page),
                      "tweet.fields": "created_at,lang"}
            if token:
                params["next_token"] = token
            response = self.client.get(SEARCH_ALL, params=params)
            data = response.json() if response.content else {}
            posts = data.get("data", [])
            self.spent_usd += len(posts) * PRICE_PER_POST_USD
            self._log({"query": query, "status": response.status_code, "posts": len(posts),
                       "spent_usd": round(self.spent_usd, 4)})
            if response.status_code != 200:
                raise RuntimeError(f"X API HTTP {response.status_code}; stopping without retry")
            for post in posts:
                read += 1
                yield {"id": post["id"], "created_at": post["created_at"], "text": post.get("text", "")}
            token = data.get("meta", {}).get("next_token")
            if not token:
                return


def score_posts(posts: Iterable[dict], scorer: Callable[[str], float], ticker: str) -> pd.DataFrame:
    """Score in memory; keep only ID, creation time, ticker and score (text is discarded)."""
    rows = []
    for post in posts:
        score = float(scorer(post["text"]))
        if not -1.0 <= score <= 1.0:
            raise ValueError("scorer must return a value in [-1, 1]")
        rows.append({"id": post["id"], "ticker": ticker,
                     "created_at": pd.Timestamp(post["created_at"]).tz_convert("UTC"), "score": score})
    return pd.DataFrame(rows, columns=["id", "ticker", "created_at", "score"])


def vader_scorer() -> Callable[[str], float]:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    analyzer = SentimentIntensityAnalyzer()
    return lambda text: analyzer.polarity_scores(text)["compound"]


def signals_at_closes(scores: pd.DataFrame, closes: pd.DatetimeIndex, *, window: timedelta = timedelta(hours=24),
                      buffer: timedelta = timedelta(minutes=15), min_posts: int = 5) -> pd.DataFrame:
    """Mean score and count per ticker for posts in [close - window, close - buffer)."""
    if closes.tz is None:
        raise ValueError("closes must be timezone-aware")
    out = []
    for ticker, group in scores.groupby("ticker"):
        times = group["created_at"].to_numpy(dtype="datetime64[ns]")
        order = np.argsort(times)
        times, values = times[order], group["score"].to_numpy(float)[order]
        cumulative = np.concatenate([[0.0], np.cumsum(values)])
        for close in closes:
            lo = np.searchsorted(times, np.datetime64((close - window).tz_convert("UTC").tz_localize(None), "ns"), "left")
            hi = np.searchsorted(times, np.datetime64((close - buffer).tz_convert("UTC").tz_localize(None), "ns"), "left")
            n = int(hi - lo)
            out.append({"ticker": ticker, "close": close, "posts": n,
                        "sentiment": (cumulative[hi] - cumulative[lo]) / n if n >= min_posts else np.nan})
    return pd.DataFrame(out)
