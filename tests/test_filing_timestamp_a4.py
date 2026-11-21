import asyncio
import json

import httpx
import pytest

from asof.filing_header_pilot import resource_urls
from asof.filing_timestamp_a3 import AdaptiveLimiter
from asof.filing_timestamp_a4 import (
    A4Session,
    identity_decision,
    segment_allowance,
)
from asof.filing_timestamp_audit import AuditGuard
from asof.sec_documentation import DocumentationStop

ACCESSION = "0000000123-23-000001"


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds + 0.000001
        await asyncio.sleep(0)


def url():
    return resource_urls(123, ACCESSION)["header"]


def session(tmp_path, monkeypatch, statuses, *, max_pauses=12, ceiling=35000):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "budget.json").write_text(json.dumps({"actual_HTTP_attempts": 6054, "ceiling": ceiling}))
    calls = []

    def handler(request):
        calls.append(1)
        status = statuses[len(calls) - 1] if len(calls) <= len(statuses) else 200
        return httpx.Response(status, stream=httpx.ByteStream(b"ok"))

    clock = Clock()
    guard = AuditGuard(lambda: (clock.now, clock.now), lambda: 0, wall_seconds=50400, monotonic=clock)
    value = A4Session({url()}, tmp_path / "budget.json", tmp_path, guard, start_used=6054,
                      max_pauses=max_pauses, transport=httpx.MockTransport(handler),
                      limiter=AdaptiveLimiter(clock, clock.sleep))
    return value, clock, calls


def run_fetch(s):
    async def go():
        async with s:
            return await s.fetch(url())
    return asyncio.run(go())


@pytest.mark.parametrize("status", [502, 504])
def test_first_gateway_error_gets_a_short_uncounted_retry(tmp_path, monkeypatch, status):
    s, clock, calls = session(tmp_path, monkeypatch, [status])
    assert run_fetch(s) == b"ok"
    assert len(calls) == 2 and s.throttle_pauses == 0 and s.short_gateway_retries == 1
    assert 60 <= clock.now < 600 and s.limiter.gap == 0.667 and sum(s.window) == 1


def test_repeat_gateway_error_and_503_use_counted_pauses(tmp_path, monkeypatch):
    s, clock, calls = session(tmp_path, monkeypatch, [502, 504, 503])
    assert run_fetch(s) == b"ok"
    assert len(calls) == 4 and s.short_gateway_retries == 1 and s.throttle_pauses == 2
    assert s.limiter.gap == 1.0 and clock.now >= 60 + 1200
    assert json.loads((tmp_path / "budget.json").read_text())["actual_HTTP_attempts"] == 6058


def test_counted_pause_cap_stops_permanently(tmp_path, monkeypatch):
    s, _, _ = session(tmp_path, monkeypatch, [503], max_pauses=0)
    with pytest.raises(DocumentationStop, match="A4_counted_pause_cap"):
        run_fetch(s)
    assert s.stopped


def test_gateway_error_rate_above_three_percent_stops(tmp_path, monkeypatch):
    s, _, calls = session(tmp_path, monkeypatch, [502])
    s.window.extend([True] * 15 + [False] * 484)
    with pytest.raises(DocumentationStop, match="A4_gateway_error_rate"):
        run_fetch(s)
    assert len(calls) == 1


def test_other_server_errors_and_old_ceiling_stop_immediately(tmp_path, monkeypatch):
    s, _, calls = session(tmp_path / "a", monkeypatch, [500])
    with pytest.raises(DocumentationStop, match="HTTP_500"):
        run_fetch(s)
    assert len(calls) == 1
    s, _, calls = session(tmp_path / "b", monkeypatch, [], ceiling=34402)
    with pytest.raises(DocumentationStop, match="A4_shared_budget_changed"):
        run_fetch(s)
    assert calls == []


def test_A4_cap_is_not_limited_by_the_A3_cap(tmp_path, monkeypatch):
    s, _, _ = session(tmp_path, monkeypatch, [])
    assert s.max_pauses == 12
    with pytest.raises(ValueError):
        session(tmp_path / "x", monkeypatch, [], max_pauses=13)


def test_segment_allowance():
    assert segment_allowance([]) == {"pauses_before": 0, "max_pauses": 12, "start_gap": 0.667}
    walled = {"throttle_pauses": 3, "stop_reason": "A4_wall_cap"}
    assert segment_allowance([walled]) == {"pauses_before": 3, "max_pauses": 9, "start_gap": 1.0}
    with pytest.raises(RuntimeError, match="continues only"):
        segment_allowance([{"throttle_pauses": 12, "stop_reason": "A4_counted_pause_cap"}])
    with pytest.raises(RuntimeError, match="continues only"):
        segment_allowance([{"throttle_pauses": 0, "stop_reason": "A4_gateway_error_rate"}])


def test_identity_decision_rule():
    listed = {1}
    assert identity_decision(1, 2, {1, 2}, listed) == "qualified_pair_CIK_is_the_listed_security"
    assert identity_decision(1, 2, {1}, listed) == "header_lacks_a_stored_CIK"
    assert identity_decision(1, 2, None, listed) == "header_unread"
    assert identity_decision(2, 1, {1, 2}, listed) == "bulk_CIK_is_the_listed_security"
    assert identity_decision(1, 2, {1, 2}, {1, 2}) == "both_listed_ambiguous"
    assert identity_decision(1, 2, {1, 2}, set()) == "neither_listed"


def test_cache_hit_rows_read_the_pinned_cache_not_A4_attempts(tmp_path):
    from asof.filing_timestamp_a4 import a4_raw_bytes

    row = {"cache_hit": True, "A4_attempts": [], "A4_segment": "seg1"}
    assert a4_raw_bytes(row, {"seg1": tmp_path}, lambda r: b"cached") == b"cached"
    with pytest.raises(ValueError, match="no complete"):
        a4_raw_bytes({**row, "cache_hit": False}, {"seg1": tmp_path}, lambda r: b"cached")
