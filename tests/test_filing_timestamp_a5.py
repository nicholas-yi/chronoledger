import asyncio
import json

import httpx
import pandas as pd
import pytest

from asof.filing_header_pilot import resource_urls
from asof.filing_timestamp_a3 import AdaptiveLimiter
from asof.filing_timestamp_a5 import A5Session, sensitive_accessions
from asof.filing_timestamp_audit import AuditGuard
from asof.sec_documentation import DocumentationStop


def filings():
    t = pd.Timestamp
    rows = [
        ("q-edge", 1, "10-Q", t("2012-01-01T03:00Z"), ""),
        ("y-edge", 1, "10-K", t("2015-12-31T22:00Z"), ""),
        ("calm", 1, "10-Q", t("2015-06-01T15:00Z"), ""),
        ("k", 2, "10-K", t("2016-03-01T21:00Z"), ""),
        ("ka", 2, "10-K/A", t("2016-03-02T01:00Z"), ""),
        ("q402", 3, "10-Q", t("2016-05-01T15:00Z"), ""),
        ("e402", 3, "8-K", t("2017-05-01T18:00Z"), "4.02"),
        ("far", 3, "8-K", t("2017-09-01T18:00Z"), "4.02"),
        ("k1", 4, "10-K", t("2014-03-01T15:00Z"), ""),
        ("k2", 4, "10-K", t("2014-03-01T20:00Z"), ""),
        ("other", 9, "10-K", t("2012-01-01T01:00Z"), ""),
    ]
    return pd.DataFrame(rows, columns=["accession", "cik", "form", "knowledge_time", "items"])


def test_population_flags_only_assignments_a_five_hour_error_could_change():
    flagged = sensitive_accessions(filings(), {1, 2, 3, 4})
    assert flagged["q-edge"] == ["dev_window_edge", "year_edge"]
    assert flagged["y-edge"] == ["year_edge"]
    assert "restatement_window_edge" in flagged["k"] and "restatement_window_edge_event" in flagged["ka"]
    assert "restatement_window_edge" in flagged["q402"] and "e402" in flagged
    assert flagged["k1"] == flagged["k2"] == ["same_company_10K_order"]
    assert {"calm", "far", "other"}.isdisjoint(flagged)


def test_A5_session_requires_the_raised_ceiling(tmp_path, monkeypatch):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    url = resource_urls(123, "0000000123-15-000001")["header"]

    def go(ceiling):
        path = tmp_path / f"b{ceiling}"
        path.mkdir()
        (path / "budget.json").write_text(json.dumps({"actual_HTTP_attempts": 34670, "ceiling": ceiling}))
        session = A5Session({url}, path / "budget.json", path,
                            AuditGuard(lambda: (0.0, 0.0), lambda: 0, wall_seconds=60),
                            start_used=34670, max_pauses=12, limiter=AdaptiveLimiter(),
                            transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=httpx.ByteStream(b"ok"))))

        async def fetch():
            async with session:
                return await session.fetch(url)
        return asyncio.run(fetch()), path

    body, path = go(35800)
    assert body == b"ok"
    assert json.loads((path / "budget.json").read_text())["actual_HTTP_attempts"] == 34671
    with pytest.raises(DocumentationStop, match="A5_shared_budget_changed"):
        go(35000)
