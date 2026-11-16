import asyncio
import errno
import importlib.util
import json
import math
from pathlib import Path

import httpx
import pytest
from scipy.stats import binom

from asof.filing_header_pilot import resource_urls
from asof.filing_timestamp_a1 import QpcLimiter
from asof.filing_timestamp_a2 import (
    A2Guard,
    BoundedSession,
    bounded_window,
    cp_upper,
    error_bounds,
    retry_kind,
)
from asof.filing_timestamp_audit import AuditGuard
from asof.sec_documentation import DocumentationStop


def test_next_new_window_does_not_force_old_timeout_back_to_front():
    order = [{"accession": a, "URL": f"{a}:{kind}", "kind": kind, "priority": "random_rest"}
             for a in ("old", "new1", "new2", "new3") for kind in ("header", "index")]
    previous = [{**order[0], "parsed": {}},
                {**order[1], "parsed": {"unknown": "TimeoutError"}}]
    selected = bounded_window(order, previous, size=2)
    assert [r["URL"] for r in selected] == [r["URL"] for r in order[2:6]]
    assert len({r["accession"] for r in selected}) == 2
    assert all(r["accession"] != "old" for r in selected)
    with pytest.raises(ValueError, match="exact frozen prefix"):
        bounded_window(order, previous[::-1], size=2)


def test_exact_one_sided_CP_zero_errors_and_nonzero_tail():
    assert cp_upper(0, 0) is None
    assert cp_upper(10, 10) == 1
    assert cp_upper(0, 100) == pytest.approx(1 - math.pow(0.05, 0.01), abs=1e-14)
    upper = cp_upper(3, 100)
    assert binom.cdf(3, 100, upper) == pytest.approx(0.05, abs=1e-12)
    with pytest.raises(ValueError):
        cp_upper(2, 1)


def test_both_source_error_bounds_use_only_agreeing_sample_and_show_all_unread():
    stamp = "2023-01-05T15:00:00+00:00"
    other = "2023-01-05T20:00:00+00:00"
    roster = [
        {"accession": a, "pair_time": stamp, "bulk_time": other if a == "disagree" else stamp,
         "pool": "candidate_calendar_boundary_or_clock_issue" if a == "boundary" else
                 "clock_agreement_sensitive"}
        for a in ("correct", "wrong", "unknown", "unvisited", "boundary", "disagree")]
    rows = [{"accession": r["accession"],
             "conditional_UTC_assuming_Eastern": (
                 None if r["accession"] in ("unknown", "unvisited")
                 else other if r["accession"] == "wrong" else stamp),
             "outside_frozen_candidate_envelope": False} for r in roster]
    selected = [r["accession"] for r in roster]
    visited = set(selected) - {"unvisited"}
    result = error_bounds(roster, rows, selected, visited)
    overall = result["by_pool_and_overall"]["overall"]
    assert (overall["selected_n"], overall["visited_n"], overall["complete_n"], overall["k"]) == (
        5, 4, 3, 1)
    assert overall["all_selected_unknown_n"] == 2
    assert overall["all_selected_unread_as_errors_k"] == 3
    assert overall["complete_case_one_sided95_CP_upper"] == cp_upper(1, 3)
    assert overall["all_selected_unread_as_errors_one_sided95_CP_upper"] == cp_upper(3, 5)
    assert result["by_pool_and_overall"]["candidate_calendar_boundary_or_clock_issue"]["complete_n"] == 1
    assert result["excluded_internally_disagreeing_by_pool"] == {"clock_agreement_sensitive": 1}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds + 0.000001
        await asyncio.sleep(0)


def url():
    return resource_urls(123, "0000000123-23-000001")["header"]


def session(tmp_path, monkeypatch, handler):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"actual_HTTP_attempts": 3137, "ceiling": 34402}))
    clock = Clock()
    guard = AuditGuard(lambda: (clock.now, clock.now), lambda: 0,
                       wall_seconds=14400, monotonic=clock)
    value = BoundedSession({url()}, budget, tmp_path, guard,
                           transport=httpx.MockTransport(handler),
                           limiter=QpcLimiter(clock, clock.sleep))
    return value, clock


@pytest.mark.parametrize("kind", ["timeout", "reset", "status503", "status429"])
def test_A2_retry_wait_duration_and_separate_charge(tmp_path, monkeypatch, kind):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            if kind == "timeout":
                raise httpx.ReadTimeout("invented", request=request)
            if kind == "reset":
                raise httpx.ReadError("invented", request=request) from ConnectionResetError(
                    errno.ECONNRESET, "invented")
            return httpx.Response(503 if kind == "status503" else 429,
                                  stream=httpx.ByteStream(b""))
        return httpx.Response(200, stream=httpx.ByteStream(b"ok"))

    s, clock = session(tmp_path, monkeypatch, handler)

    async def run():
        async with s:
            assert await s.fetch(url()) == b"ok"

    asyncio.run(run())
    expected = 600 if kind.startswith("status") else 60
    assert clock.now >= expected and calls == [url(), url()]
    assert s.charged == 2 and s.waits_used == 1 and s.waiting_seconds >= expected
    records = [json.loads(r) for r in s.aggregate.read_text().splitlines()]
    starts = [r for r in records if r["event"] == "started"]
    assert [r["historical_attempt"] for r in starts] == [3138, 3139]
    assert [r["A2_retry"] for r in starts] == [False, True]


def test_second_transport_failure_stops_without_another_wait(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        raise httpx.ReadTimeout("invented", request=request)

    s, _ = session(tmp_path, monkeypatch, handler)

    async def run():
        async with s:
            with pytest.raises(DocumentationStop, match="ReadTimeout"):
                await s.fetch(url())

    asyncio.run(run())
    assert len(calls) == 2 and s.waits_used == 1 and s.stopped


@pytest.mark.parametrize("limit", ["status_count", "all_wait_seconds"])
def test_A2_wait_budgets_decline_before_retry(tmp_path, monkeypatch, limit):
    s, _ = session(tmp_path, monkeypatch, lambda request: httpx.Response(
        503, stream=httpx.ByteStream(b"")))
    if limit == "status_count":
        s.status_waits_used = 20
    else:
        s.waiting_seconds = 7190

    async def run():
        async with s:
            with pytest.raises(DocumentationStop, match="wait_count_or_cumulative"):
                await s.fetch(url())

    asyncio.run(run())
    assert s.charged == 1 and s.waits_used == 0
    events = [json.loads(r) for r in s.events.read_text().splitlines()]
    assert len(events) == 1 and events[0]["event"] == "wait_not_started"


@pytest.mark.parametrize("failure", [403, 500, 502, 302, "connect_refused"])
def test_unapproved_errors_have_no_backoff(tmp_path, monkeypatch, failure):
    def handler(request):
        if failure == "connect_refused":
            raise httpx.ConnectError("invented", request=request) from OSError(
                errno.ECONNREFUSED, "invented")
        return httpx.Response(failure, headers={"location": url()}, stream=httpx.ByteStream(b""))

    s, clock = session(tmp_path, monkeypatch, handler)

    async def run():
        async with s:
            with pytest.raises(DocumentationStop):
                await s.fetch(url())

    asyncio.run(run())
    assert s.charged == 1 and s.waits_used == 0 and clock.now < 1


def test_generic_ConnectError_does_not_become_a_connection_reset():
    assert retry_kind(DocumentationStop("ConnectError")) is None
    assert retry_kind(DocumentationStop("HTTP_403")) is None


def test_four_hour_guard_uses_correct_amendment_label():
    now = [0]
    guard = A2Guard(lambda: (0, 0), lambda: 0, wall_seconds=14400, monotonic=lambda: now[0])
    now[0] = 14401
    with pytest.raises(DocumentationStop, match="A2_4h_wall_cap"):
        guard.check()


def runner_module(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("timestamp_a2_runner",
                                                 scripts / "run_full_timestamps_a2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_second_A2_run_refuses_before_config_or_transport(tmp_path, monkeypatch):
    runner = runner_module(monkeypatch)
    marker = tmp_path / "started.json"
    marker.write_text("{}")
    monkeypatch.setattr(runner, "STARTED", marker)
    with pytest.raises(RuntimeError, match="already attempted"):
        asyncio.run(runner.run())


def test_report_combines_only_declared_sample_and_preserves_conditional_meaning(tmp_path, monkeypatch):
    runner = runner_module(monkeypatch)
    old, first, current = tmp_path / "old", tmp_path / "a1", tmp_path / "a2"
    for path in (old, first, current):
        path.mkdir()
    monkeypatch.setattr(runner, "PRIVATE", current)
    monkeypatch.setattr(runner.a1, "PRIVATE", first)
    monkeypatch.setattr(runner.base, "PRIVATE", old)
    monkeypatch.setattr(runner.base, "PROJECT_ROOT", tmp_path)
    for name in ("CONFIG", "STATUS", "REPORT", "ORDER", "SAMPLE", "OUTCOMES", "REQUESTS",
                 "EVENTS", "CHECKPOINT", "TABLE"):
        monkeypatch.setattr(runner, name, current / f"{name.lower()}.json")
    for name in ("OUTCOMES", "ORDER"):
        monkeypatch.setattr(runner.a1, name, first / f"{name.lower()}.json")
    for name in ("BUDGET", "OUTCOMES", "INVENTORY", "ROSTER", "UNIVERSE", "CALENDAR"):
        monkeypatch.setattr(runner.base, name, old / f"{name.lower()}.json")
    runner.base.atomic_json(runner.CONFIG, {
        "input_SHA256": {}, "ancestor_source_SHA256": {}, "source_SHA256": {}, "sample_order_SHA256": {}})
    runner.base.atomic_json(runner.STATUS, {
        "status": "bounded3000_complete_conditional_A2", "amendment_commit": "fixture"})
    runner.base.atomic_json(runner.base.BUDGET, {"actual_HTTP_attempts": 3139, "ceiling": 34402})
    stamp, other = "2023-01-05T15:00:00+00:00", "2023-01-05T20:00:00+00:00"
    roster = [{"accession": a, "pool": "clock_agreement_sensitive", "cik_pair": 123, "cik_bulk": 123,
               "pair_time": stamp, "bulk_time": stamp, "candidate_times": [stamp, other]}
              for a in ("P", "Q")]
    inventory = [{"URL": f"{a}:{kind}", "accession": a, "kind": kind, "path_CIK": 123,
                  "priority": "random_rest"} for a in ("P", "Q") for kind in ("header", "index")]
    outcomes = []
    for resource in inventory:
        changed = resource["accession"] == "Q"
        wall = "20230105150000" if changed else "20230105100000"
        parsed = ({"header_wall": wall, "UTC_assuming_Eastern": other if changed else stamp,
                   "header_CIKs_by_role": {"FILER": ["0000000123"]}} if resource["kind"] == "header"
                  else {"index_wall": wall})
        outcomes.append({**resource, "parsed": parsed})
    for path, values in ((runner.base.INVENTORY, inventory), (runner.base.ROSTER, roster),
                         (runner.base.UNIVERSE, roster), (runner.base.OUTCOMES, []),
                         (runner.a1.ORDER, inventory[:2]), (runner.a1.OUTCOMES, outcomes[:2]),
                         (runner.ORDER, inventory[2:]), (runner.OUTCOMES, outcomes[2:]),
                         (runner.SAMPLE, [{"accession": "P"}, {"accession": "Q"}])):
        runner.base.write_lines(path, values)
    runner.base.atomic_json(runner.base.CALENDAR, {
        "closes": ["2023-01-05T21:00:00+00:00"], "formations": [],
        "start": "2023-01-01T00:00:00+00:00", "end": "2023-02-01T00:00:00+00:00"})
    logs = []
    for i, perf in enumerate((100.0, 100.668), 3138):
        logs.extend([{"event": "started", "historical_attempt": i, "A2_retry": False},
                     {"event": "send", "send_perf_counter": perf},
                     {"event": "finished", "historical_attempt": i, "attempted": True, "status": 200}])
    runner.base.write_lines(runner.REQUESTS, logs)
    runner.report()
    report = json.loads(runner.REPORT.read_text())
    stats = report["predeclared_conditional_error_bounds"]["by_pool_and_overall"]["overall"]
    assert (stats["k"], stats["complete_n"]) == (1, 2)
    assert stats["complete_case_one_sided95_CP_upper"] == cp_upper(1, 2)
    assert report["qualified_UTC"] == 0 and report["unique_conditional_UTC"] == 2
