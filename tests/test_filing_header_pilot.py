import asyncio
import json

import httpx
import pytest

from asof.filing_header_pilot import (
    POOLS,
    ScopedFilingMetadata,
    comparison,
    parse_header,
    parse_index,
    pool_for,
    resource_urls,
)
from asof.sec_documentation import DocumentationStop, MetadataUnknown

ACC = "0000000123-23-000001"
URLS = resource_urls(123, ACC)


class Bytes(httpx.AsyncByteStream):
    def __init__(self, value):
        self.value = value

    async def __aiter__(self):
        yield self.value


def client(tmp_path, monkeypatch, handler, *, used=48, urls=None):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"actual_HTTP_attempts": used, "ceiling": 150}))
    return ScopedFilingMetadata(tuple((urls or URLS).values()), budget,
        tmp_path / "receipt.jsonl", tmp_path / "cache", transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("kind", ["stream_cap", "declared_cap", "missing"])
def test_unknown_resource_does_not_promote_or_stop_next_resource(tmp_path, monkeypatch, kind):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if len(seen) == 1:
            return httpx.Response(404 if kind == "missing" else 200,
                headers={"content-length": "70000"} if kind == "declared_cap" else {},
                stream=Bytes(b"x" * 70000))
        return httpx.Response(200, stream=Bytes(b"bounded metadata"))

    c = client(tmp_path, monkeypatch, handler)

    async def run():
        async with c:
            with pytest.raises(MetadataUnknown):
                await c.fetch(URLS["header"])
            assert not c.stopped and not c.last_record["body_complete"]
            return await c.fetch(URLS["index"])

    assert asyncio.run(run()) == b"bounded metadata"
    assert seen == list(URLS.values()) and c.attempts == 2


@pytest.mark.parametrize("failure", [301, 302, 307, 403, 429, 500, 503, "transport"])
def test_new_adapter_stops_pilot_without_follow_or_retry(tmp_path, monkeypatch, failure):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if failure == "transport":
            raise httpx.ConnectError("synthetic transport", request=request)
        return httpx.Response(failure, headers={"location": URLS["index"]}, stream=Bytes(b"x"))

    c = client(tmp_path, monkeypatch, handler)

    async def run():
        async with c:
            with pytest.raises(DocumentationStop):
                await c.fetch(URLS["header"])
            with pytest.raises(DocumentationStop, match="already_stopped"):
                await c.fetch(URLS["index"])

    asyncio.run(run())
    assert seen == [URLS["header"]] and c.attempts == 1


@pytest.mark.parametrize("failure", ["budget", "local_limit", "body_url", "wrong_accession_folder"])
def test_pilot_budget_and_exact_metadata_scope(tmp_path, monkeypatch, failure):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, stream=Bytes(b"x"))

    urls = dict(URLS)
    if failure == "body_url":
        urls["bad"] = URLS["header"].replace("-index-headers.html", ".txt")
    if failure == "wrong_accession_folder":
        urls["bad"] = URLS["header"].replace("/000000012323000001/", "/000000012323000002/")
    c = client(tmp_path, monkeypatch, handler, used=144 if failure == "budget" else 48, urls=urls)
    if failure == "local_limit":
        c.attempts = 96

    async def run():
        async with c:
            with pytest.raises(DocumentationStop):
                await c.fetch(urls.get("bad", urls["header"]))

    asyncio.run(run())
    assert not seen


def test_synthetic_clock_role_and_index_rehearsal_preserves_conditional_meaning():
    raw = (f"ACCESSION NUMBER: {ACC}\n<ACCEPTANCE-DATETIME>20230105103000\n"
           "FILER:\n CENTRAL INDEX KEY: 0000000123\n"
           "SUBJECT COMPANY:\n CENTRAL INDEX KEY: 0000000456").encode()
    header = parse_header(raw, ACC)
    assert header["header_CIKs_by_role"] == {
        "FILER": ["0000000123"], "SUBJECT COMPANY": ["0000000456"]}
    index = parse_index(b"Accepted</div><div>2023-01-05 10:30:00</div>")
    result = comparison({"pair_time": "2023-01-05T15:30:00+00:00",
                         "bulk_time": "2023-01-05T10:30:00+00:00"}, header, index)
    assert result["class"] == "pair_only_matches_assumption"
    assert result["bulk_offset_hours"] == -5 and result["index_header_wall_agree"]
    with pytest.raises(ValueError, match="scope_failure"):
        parse_header(raw.replace(ACC.encode(), b"0000000456-23-000001"), ACC)
    for wall in ("20231105013000", "20230312023000", "202301051030000"):
        bad = raw.replace(b"20230105103000", wall.encode())
        assert parse_header(bad, ACC).get("unknown")
    assert comparison({"pair_time": "2023-01-05T15:30:00+00:00",
                       "bulk_time": "2023-01-05T10:30:00+00:00"},
                      {"unknown": "oversized"}, index)["class"] == "unknown_header"


def test_exclusive_pool_priority_uses_only_metadata():
    row = {"CIKs_agree": True, "candidate_times": ["2023-01-05T15:30:00+00:00"],
           "clock_issues": [], "source_times_agree": True, "assignment_sensitive": False,
           "pair_time": "2023-01-05T15:30:00+00:00"}
    assert pool_for(row) == POOLS[5]
    assert pool_for({**row, "assignment_sensitive": True}) == POOLS[4]
    assert pool_for({**row, "source_times_agree": False}) == POOLS[2]
    assert pool_for({**row, "pair_time": "2023-07-05T15:30:00+00:00",
                     "source_times_agree": False}) == POOLS[3]
    assert pool_for({**row, "clock_issues": ["synthetic"]}) == POOLS[1]
    assert pool_for({**row, "clock_issues": ["synthetic"], "CIKs_agree": False}) == POOLS[0]


def test_identical_rendered_clock_duplicates_are_not_conflicting_clocks():
    raw = (f"<ACCESSION-NUMBER>{ACC}\n<ACCEPTANCE-DATETIME>20230105103000\n"
           f"ACCESSION NUMBER: {ACC}\n<ACCEPTANCE-DATETIME>20230105103000\n"
           "FILER:\n CENTRAL INDEX KEY: 0000000123").encode()
    parsed = parse_header(raw, ACC)
    assert parsed.get("UTC_assuming_Eastern") == "2023-01-05T15:30:00+00:00"
    conflict = raw.replace(b"20230105103000", b"20230105103001", 1)
    assert parse_header(conflict, ACC).get("unknown")
