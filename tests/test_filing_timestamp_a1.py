import asyncio
import importlib.util
import json
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from asof.filing_header_pilot import resource_urls
from asof.filing_timestamp_a1 import (
    MIN_GAP,
    AmendedSession,
    QpcLimiter,
    remaining_order,
)
from asof.filing_timestamp_audit import AuditGuard
from asof.sec_documentation import DocumentationStop, MetadataUnknown


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []
        self.early = True

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        if self.early and seconds > 0.1:
            self.now += seconds / 2
            self.early = False
        else:
            self.now += seconds + 0.000001
        await asyncio.sleep(0)


def test_QPC_rechecks_an_early_wake_without_a_coarse_wall_clock():
    clock = Clock()
    limiter = QpcLimiter(clock, clock.sleep)
    limiter.mark()

    async def run():
        await limiter.wait(lambda: None)
        return limiter.mark()

    assert asyncio.run(run()) >= MIN_GAP
    assert len(clock.sleeps) == 2
    assert clock.sleeps[0] == MIN_GAP
    assert clock.sleeps[1] > 0


def test_QPC_coarsely_quantized_wakes_never_mean_early_dispatch():
    now = [1000000.0]
    coarse_wakes = []

    async def sleep(seconds):
        # A scheduler may wake before its requested deadline.
        advance = max(0.001, seconds - 0.015625)
        now[0] += advance
        coarse_wakes.append(advance)

    limiter = QpcLimiter(lambda: now[0], sleep)
    sends = [limiter.mark()]

    async def run():
        for _ in range(3):
            await limiter.wait(lambda: None)
            sends.append(limiter.mark())

    asyncio.run(run())
    assert len(coarse_wakes) > 3
    assert all(b - a >= MIN_GAP for a, b in pairwise(sends))
    with pytest.raises(DocumentationStop, match="dispatch_gap"):
        limiter.mark()


def urls(count):
    return [resource_urls(123, f"0000000123-23-{i:06}")["header"]
            for i in range(1, count + 1)]


def session(tmp_path, monkeypatch, handler, count=1):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"actual_HTTP_attempts": 1421, "ceiling": 34402}))
    clock = Clock()
    guard = AuditGuard(lambda: (clock.now, clock.now), lambda: 0, monotonic=clock)
    value = AmendedSession(set(urls(count)), budget, tmp_path, guard,
                           transport=httpx.MockTransport(handler),
                           limiter=QpcLimiter(clock, clock.sleep))
    return value, clock


@pytest.mark.parametrize("first", [503, 429])
def test_one_exact_URL_retry_after_at_least600_QPC_seconds(tmp_path, monkeypatch, first):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(first if len(seen) == 1 else 200, stream=httpx.ByteStream(b"ok"))

    s, clock = session(tmp_path, monkeypatch, handler)

    async def run():
        async with s:
            assert await s.fetch(urls(1)[0]) == b"ok"

    asyncio.run(run())
    assert seen == [urls(1)[0], urls(1)[0]] and s.charged == 2 and s.waits_used == 1
    assert clock.now >= 600
    rows = [json.loads(r) for r in s.aggregate.read_text().splitlines()]
    sends = [r for r in rows if r["event"] == "send"]
    assert len(sends) == 2 and sends[1]["send_perf_counter"] - sends[0]["send_perf_counter"] >= 600
    assert [r["historical_attempt"] for r in rows if r["event"] == "started"] == [1422, 1423]
    assert [r["A1_retry"] for r in rows if r["event"] == "started"] == [False, True]
    events = [json.loads(r) for r in s.events.read_text().splitlines()]
    assert [e["event"] for e in events] == ["wait_started", "wait_finished", "retry_started"]
    assert events[1]["elapsed_perf_seconds"] >= 600 and events[1]["status"] == "completed"


def test_retry_failure_stops_without_a_second_wait(tmp_path, monkeypatch):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(503 if len(seen) == 1 else 429, stream=httpx.ByteStream(b""))

    s, _ = session(tmp_path, monkeypatch, handler)

    async def run():
        async with s:
            with pytest.raises(DocumentationStop, match="HTTP_429"):
                await s.fetch(urls(1)[0])
            with pytest.raises(DocumentationStop, match="stopped"):
                await s.fetch(urls(1)[0])

    asyncio.run(run())
    assert s.stopped and len(seen) == 2 and s.waits_used == 1


def test_normal_dispatch_receipts_use_QPC_and_minimum_gap(tmp_path, monkeypatch):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, stream=httpx.ByteStream(b"ok"))

    s, _ = session(tmp_path, monkeypatch, handler, count=2)

    async def run():
        async with s:
            for url in urls(2):
                assert await s.fetch(url) == b"ok"

    asyncio.run(run())
    logs = [json.loads(r) for r in s.aggregate.read_text().splitlines()]
    sends = [r for r in logs if r["event"] == "send"]
    assert seen == urls(2) and len(sends) == 2
    assert sends[1]["send_perf_counter"] - sends[0]["send_perf_counter"] >= MIN_GAP
    assert all(r["send_UTC"] for r in sends)


def test_sleep_during_wait_records_interruption_without_retry(tmp_path, monkeypatch):
    s, clock = session(tmp_path, monkeypatch, lambda request: httpx.Response(
        503, stream=httpx.ByteStream(b"")))
    s.guard.clocks = lambda: (clock.now + (10 if clock.now > 2 else 0), clock.now)

    async def run():
        async with s:
            with pytest.raises(DocumentationStop, match="sleep"):
                await s.fetch(urls(1)[0])

    asyncio.run(run())
    events = [json.loads(r) for r in s.events.read_text().splitlines()]
    assert [r["event"] for r in events] == ["wait_started", "wait_finished"]
    assert events[-1]["status"] == "interrupted" and s.charged == 1 and s.stopped


@pytest.mark.parametrize("failure", [403, 500, 502, 302, "transport"])
def test_other_failures_never_wait_or_retry(tmp_path, monkeypatch, failure):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if failure == "transport":
            raise httpx.ConnectError("invented", request=request)
        return httpx.Response(failure, headers={"location": urls(1)[0]},
                              stream=httpx.ByteStream(b""))

    s, clock = session(tmp_path, monkeypatch, handler)

    async def run():
        async with s:
            with pytest.raises(DocumentationStop):
                await s.fetch(urls(1)[0])

    asyncio.run(run())
    assert len(seen) == 1 and s.charged == 1 and s.waits_used == 0 and clock.now < 1


def test_sixth_wait_stops_and_never_charges_a_sixth_retry(tmp_path, monkeypatch):
    seen = {}

    def handler(request):
        url = str(request.url)
        seen[url] = seen.get(url, 0) + 1
        return httpx.Response(503 if seen[url] == 1 else 200, stream=httpx.ByteStream(b"ok"))

    s, _ = session(tmp_path, monkeypatch, handler, count=6)

    async def run():
        async with s:
            for url in urls(6)[:5]:
                assert await s.fetch(url) == b"ok"
            with pytest.raises(DocumentationStop, match="sixth_wait"):
                await s.fetch(urls(6)[5])

    asyncio.run(run())
    assert s.waits_used == 5 and s.charged == 11 and seen[urls(6)[5]] == 1
    assert s.stopped


def test_missing_resource_is_unknown_and_cannot_be_requested_again(tmp_path, monkeypatch):
    s, _ = session(tmp_path, monkeypatch, lambda request: httpx.Response(
        404, stream=httpx.ByteStream(b"")))

    async def run():
        async with s:
            with pytest.raises(MetadataUnknown):
                await s.fetch(urls(1)[0])
            assert not s.stopped and s.waits_used == 0
            with pytest.raises(DocumentationStop, match="duplicate"):
                await s.fetch(urls(1)[0])

    asyncio.run(run())
    assert s.charged == 1


def test_remaining_order_protects_success_and_caps_but_reopens_only_old503():
    names = ["w", "s", "c", "a", "b", "d"]
    pools = ["clock_disagreement_winter", "clock_disagreement_summer", "CIK_disagreement",
             "clock_agreement_sensitive", "clock_agreement_sensitive", "clock_agreement_sensitive"]
    roster = [{"accession": a, "pool": p} for a, p in zip(names, pools, strict=True)]
    inventory = [{"accession": a, "URL": f"{a}:{kind}", "kind": kind}
                 for a in names for kind in ("header", "index")]
    prior = [
        {"URL": "a:header", "request": {"status": 200}},
        {"URL": "a:index", "request": {"status": 200}, "parsed": {"unknown": "read_cap"}},
        {"URL": "b:header", "request": {"status": 503}},
    ]
    order = remaining_order(inventory, prior, roster)
    assert [r["accession"] for r in order[:6]] == ["s", "s", "w", "w", "c", "c"]
    assert {r["URL"] for r in order} == {r["URL"] for r in inventory} - {"a:header", "a:index"}
    assert sum(r["previous503_reeligible"] for r in order) == 1
    assert order == remaining_order(inventory, prior, roster)


def runner_module(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("timestamp_a1_runner",
                                                 scripts / "run_full_timestamps_a1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_combined_view_never_replaces_a_protected_parent_outcome(monkeypatch):
    runner = runner_module(monkeypatch)
    prior = [{"URL": "good", "request": {"status": 200}},
             {"URL": "failed", "request": {"status": 503}}]
    order = [{"URL": "failed"}, {"URL": "new"}]
    assert runner.merge_outcomes(prior, [{"URL": "failed", "new": True}], order)["good"] == prior[0]
    with pytest.raises(ValueError, match="outside"):
        runner.merge_outcomes(prior, [{"URL": "good"}], order)


def test_second_amended_run_refuses_before_config_or_transport(tmp_path, monkeypatch):
    runner = runner_module(monkeypatch)
    marker = tmp_path / "started.json"
    marker.write_text("{}")
    monkeypatch.setattr(runner, "STARTED", marker)
    with pytest.raises(RuntimeError, match="already attempted"):
        asyncio.run(runner.run())


def test_combined_report_keeps_parent_and_labels_conditional_not_qualified(tmp_path, monkeypatch):
    runner = runner_module(monkeypatch)
    parent, amended = tmp_path / "parent", tmp_path / "amended"
    parent.mkdir()
    amended.mkdir()
    monkeypatch.setattr(runner, "PRIVATE", amended)
    monkeypatch.setattr(runner.base, "PRIVATE", parent)
    monkeypatch.setattr(runner.base, "PROJECT_ROOT", tmp_path)
    for name in ("CONFIG", "STATUS", "REPORT", "ORDER", "OUTCOMES", "REQUESTS", "EVENTS",
                 "CHECKPOINT", "TABLE"):
        monkeypatch.setattr(runner, name, amended / f"{name.lower()}.json")
    for name in ("BUDGET", "OUTCOMES", "INVENTORY", "ROSTER", "UNIVERSE", "CALENDAR"):
        monkeypatch.setattr(runner.base, name, parent / f"{name.lower()}.json")
    runner.base.atomic_json(runner.CONFIG, {
        "input_SHA256": {}, "parent_source_SHA256": {}, "source_SHA256": {}, "order_SHA256": {},
        "parent_freeze_commit": "synthetic", "original_rate_context": "own precision miss"})
    runner.base.atomic_json(runner.STATUS, {"status": "stopped_final", "amendment_commit": "fixture",
                                           "stop_reason": "synthetic_stop"})
    runner.base.atomic_json(runner.base.BUDGET, {"actual_HTTP_attempts": 1422, "ceiling": 34402})
    row = {"accession": "A", "pool": "clock_disagreement_winter", "cik_pair": 123, "cik_bulk": 123,
           "pair_time": "2023-01-05T15:30:00+00:00", "bulk_time": "2023-01-05T20:30:00+00:00",
           "candidate_times": ["2023-01-05T15:30:00+00:00", "2023-01-05T20:30:00+00:00"]}
    inventory = [{"URL": k, "accession": "A", "kind": k, "path_CIK": 123}
                 for k in ("header", "index")]
    header = {**inventory[0], "parsed": {"header_wall": "20230105103000",
              "UTC_assuming_Eastern": row["pair_time"], "header_CIKs_by_role": {"FILER": ["0000000123"]}}}
    old = [{**inventory[0], "request": {"status": 503}, "parsed": {"unknown": "HTTP503"}},
           {**inventory[1], "parsed": {"index_wall": "20230105103000"}}]
    for path, values in ((runner.base.INVENTORY, inventory), (runner.base.ROSTER, [row]),
                         (runner.base.UNIVERSE, [row]), (runner.base.OUTCOMES, old),
                         (runner.ORDER, inventory[:1]), (runner.OUTCOMES, [header])):
        runner.base.write_lines(path, values)
    runner.base.atomic_json(runner.base.CALENDAR, {
        "closes": ["2023-01-05T21:00:00+00:00"], "formations": [],
        "start": "2023-01-01T00:00:00+00:00", "end": "2023-02-01T00:00:00+00:00"})
    runner.base.write_lines(runner.REQUESTS, [
        {"event": "started", "historical_attempt": 1422, "A1_retry": False},
        {"event": "send", "send_perf_counter": 100.0},
        {"event": "finished", "attempted": True, "status": 200}])
    runner.report()
    result = json.loads(runner.REPORT.read_text())
    assert result["A1_attempts"] == 1 and result["effective_unique_resource_outcomes"] == 2
    assert result["qualified_UTC"]["historically_qualified"] == 0
    assert result["qualified_UTC"]["unique_conditional_assuming_Eastern"] == 1
    assert result["designated108_first"]["clock_disagreement_winter"]["agreement_classes"] == {
        "pair_only_matches_assumption": 1}
    assert runner.base.load_lines(runner.base.OUTCOMES) == old
