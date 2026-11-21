import json
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pandas as pd
import pytest

from asof.social import (
    BudgetExceeded,
    XArchiveClient,
    cashtag_query,
    estimate_cost,
    score_posts,
    signals_at_closes,
)


def test_client_refuses_without_owner_token_and_budget(tmp_path, monkeypatch):
    monkeypatch.delenv("ASOF_X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("ASOF_X_BUDGET_USD", raising=False)
    with pytest.raises(PermissionError):
        XArchiveClient(tmp_path / "log.jsonl")
    monkeypatch.setenv("ASOF_X_BEARER_TOKEN", "invented")
    monkeypatch.setenv("ASOF_X_BUDGET_USD", "0")
    with pytest.raises(PermissionError):
        XArchiveClient(tmp_path / "log.jsonl")


def test_budget_is_charged_before_each_page_and_text_is_not_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("ASOF_X_BEARER_TOKEN", "invented")
    monkeypatch.setenv("ASOF_X_BUDGET_USD", "0.75")
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        posts = [{"id": str(len(calls) * 1000 + i), "created_at": "2023-05-09T14:00:00.000Z",
                  "text": "great quarter" if i % 2 else "terrible guidance"} for i in range(100)]
        return httpx.Response(200, json={"data": posts, "meta": {"next_token": "more"}})

    client = XArchiveClient(tmp_path / "log.jsonl", transport=httpx.MockTransport(handler), sleep=lambda s: None)
    start, end = datetime(2023, 5, 1, tzinfo=UTC), datetime(2023, 5, 10, tzinfo=UTC)
    got = []
    with pytest.raises(BudgetExceeded):
        for post in client.search(cashtag_query("aapl"), start, end, max_posts=1000):
            got.append(post)  # noqa: PERF402 - keep the posts read before the budget stop
    assert len(calls) == 1 and len(got) == 100 and client.spent_usd == pytest.approx(0.5)
    assert calls[0]["query"] == "$AAPL lang:en -is:retweet"
    frame = score_posts(got, lambda text: 1.0 if "great" in text else -1.0, "AAPL")
    assert list(frame.columns) == ["id", "ticker", "created_at", "score"]
    assert [json.loads(line)["spent_usd"] for line in (tmp_path / "log.jsonl").read_text().splitlines()] == [0.5]
    assert estimate_cost(1_000_000) == 5000.0
    with pytest.raises(ValueError):
        cashtag_query("AAPL OR x")


def test_signals_use_only_posts_before_close_minus_buffer():
    close = pd.Timestamp("2023-05-09T20:00:00Z")
    times = [close - timedelta(hours=h) for h in (30, 20, 2, 1)] + [close - timedelta(minutes=10), close]
    scores = pd.DataFrame({"id": range(6), "ticker": "AAPL", "created_at": pd.to_datetime(times, utc=True),
                           "score": [9.0, 0.2, 0.4, 0.6, 50.0, 99.0]})
    out = signals_at_closes(scores, pd.DatetimeIndex([close]), min_posts=3)
    assert out.loc[0, "posts"] == 3 and out.loc[0, "sentiment"] == pytest.approx(0.4)
    late = scores.assign(score=np.where(scores["created_at"] >= close - timedelta(minutes=15), -999.0, scores["score"]))
    pd.testing.assert_frame_equal(out, signals_at_closes(late, pd.DatetimeIndex([close]), min_posts=3))
    assert np.isnan(signals_at_closes(scores, pd.DatetimeIndex([close]), min_posts=4).loc[0, "sentiment"])
