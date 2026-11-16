import asyncio
import hashlib
import json

import httpx
import pytest

from asof import sec_documentation as docs

URL = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
OTHER = "https://www.sec.gov/files/synthetic-field-definition.txt"


class Bytes(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


def setup(tmp_path, monkeypatch, handler, *, used=46):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    budget, receipt = tmp_path / "budget.json", tmp_path / "receipts.jsonl"
    budget.write_text(json.dumps({"actual_HTTP_attempts": used, "ceiling": 150}))
    client = docs.StrictSecDocumentation(
        (URL, OTHER), budget, receipt, tmp_path / "cache",
        transport=httpx.MockTransport(handler),
    )
    return client, budget, receipt


def test_complete_receipt_budget_precharge_declared_agent_hash_and_no_redirects(tmp_path, monkeypatch):
    seen = []

    def handle(request):
        assert json.loads((tmp_path / "budget.json").read_text())["actual_HTTP_attempts"] == 47
        assert request.headers["user-agent"] == "Fictional Test test@example.invalid"
        assert request.headers["accept-encoding"] == "identity"
        seen.append(str(request.url))
        return httpx.Response(200, stream=Bytes([b"Acceptance field definition."]),
                              headers={"content-type": "text/plain"})

    client, budget, receipt = setup(tmp_path, monkeypatch, handle)

    async def run():
        async with client:
            return await client.fetch(URL)

    assert asyncio.run(run()) == b"Acceptance field definition."
    rows = [json.loads(x) for x in receipt.read_text().splitlines()]
    assert [r["event"] for r in rows] == ["started", "finished"]
    assert rows[-1]["body_complete"] and rows[-1]["status"] == 200
    assert rows[-1]["bytes"] == len(b"Acceptance field definition.")
    assert rows[-1]["SHA256_observed_bytes"] == hashlib.sha256(b"Acceptance field definition.").hexdigest()
    assert json.loads(budget.read_text())["actual_HTTP_attempts"] == 47 and seen == [URL]


@pytest.mark.parametrize("status", [301, 302, 307, 403, 404, 429, 500, 503])
def test_status_stop_is_permanent_without_redirect_or_retry(tmp_path, monkeypatch, status):
    seen = []

    def handle(request):
        seen.append(str(request.url))
        return httpx.Response(status, headers={"location": OTHER}, stream=Bytes([b"unread"]))

    client, budget, receipt = setup(tmp_path, monkeypatch, handle)

    async def run():
        async with client:
            with pytest.raises(docs.DocumentationStop, match=f"HTTP_{status}"):
                await client.fetch(URL)
            with pytest.raises(docs.DocumentationStop, match="already_stopped"):
                await client.fetch(OTHER)

    asyncio.run(run())
    assert seen == [URL] and json.loads(budget.read_text())["actual_HTTP_attempts"] == 47
    final = json.loads(receipt.read_text().splitlines()[-1])
    assert final["bytes"] == 0 and not final["body_complete"]


@pytest.mark.parametrize("kind", ["transport", "timeout", "deadline"])
def test_transport_and_total_deadline_stop_once(tmp_path, monkeypatch, kind):
    seen = []

    async def handle(request):
        seen.append(str(request.url))
        if kind == "transport":
            raise httpx.ConnectError("synthetic transport failure", request=request)
        if kind == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        await asyncio.sleep(10)

    monkeypatch.setattr(docs, "TIMEOUT_SECONDS", 0.01)
    client, budget, receipt = setup(tmp_path, monkeypatch, handle)

    async def run():
        async with client:
            with pytest.raises(docs.DocumentationStop):
                await client.fetch(URL)

    asyncio.run(run())
    assert seen == [URL] and json.loads(budget.read_text())["actual_HTTP_attempts"] == 47
    assert json.loads(receipt.read_text().splitlines()[-1])["stop_reason"]


@pytest.mark.parametrize("declared", [True, False])
def test_read_cap_is_unknown_not_silently_truncated_success(tmp_path, monkeypatch, declared):
    def handle(request):
        return httpx.Response(200, stream=Bytes([b"x" * 70000]),
                              headers={"content-length": "70000"} if declared else {})

    client, _, receipt = setup(tmp_path, monkeypatch, handle)

    async def run():
        async with client:
            with pytest.raises(docs.DocumentationStop, match="read_cap"):
                await client.fetch(URL)

    asyncio.run(run())
    final = json.loads(receipt.read_text().splitlines()[-1])
    assert not final["body_complete"] and final["bytes"] <= 65536
    assert final["bytes"] == (0 if declared else 65536)


@pytest.mark.parametrize("failure", ["historical_budget", "local_budget", "scope", "parallel", "encoding"])
def test_budget_scope_serial_and_encoding_stops(tmp_path, monkeypatch, failure):
    seen = []

    def handle(request):
        seen.append(str(request.url))
        return httpx.Response(200, stream=Bytes([b"x"]), headers={"content-encoding": "gzip"})

    client, budget, _ = setup(tmp_path, monkeypatch, handle,
                              used=150 if failure == "historical_budget" else 46)
    if failure == "local_budget":
        client.attempts = 8
    if failure == "parallel":
        client.active = True

    async def run():
        async with client:
            with pytest.raises(docs.DocumentationStop):
                await client.fetch("https://www.sec.gov/Archives/edgar/data/1/x" if failure == "scope"
                                   else URL)

    asyncio.run(run())
    assert len(seen) == (1 if failure == "encoding" else 0)
    assert json.loads(budget.read_text())["actual_HTTP_attempts"] == (
        150 if failure == "historical_budget" else 47 if failure == "encoding" else 46)


def test_serial_start_rate_and_duplicate_request_stop(tmp_path, monkeypatch):
    starts = []

    def handle(request):
        import time
        starts.append(time.monotonic())
        return httpx.Response(200, stream=Bytes([b"plain text"]))

    client, _, _ = setup(tmp_path, monkeypatch, handle)

    async def run():
        async with client:
            await client.fetch(URL)
            await client.fetch(OTHER)
            with pytest.raises(docs.DocumentationStop, match="duplicate"):
                await client.fetch(URL)

    asyncio.run(run())
    assert len(starts) == 2 and starts[1] - starts[0] >= 0.49


def test_approved_documentation_cap_only_changes_read_bound(tmp_path, monkeypatch):
    seen = []

    def handle(request):
        seen.append(str(request.url))
        return httpx.Response(200, stream=Bytes([b"x" * 70000]))

    client, budget, receipt = setup(tmp_path, monkeypatch, handle)
    asyncio.run(client.client.aclose())
    client = docs.StrictSecDocumentation(
        (URL,), budget, receipt, tmp_path / "cache",
        transport=httpx.MockTransport(handle), read_cap_bytes=4 << 20,
    )

    async def run():
        async with client:
            return await client.fetch(URL)

    assert len(asyncio.run(run())) == 70000 and seen == [URL]
    assert json.loads(receipt.read_text().splitlines()[-1])["body_complete"]
