import asyncio
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from asof.filing_header_pilot import parse_header, parse_index, resource_urls
from asof.filing_timestamp_audit import (
    DISK_BYTES,
    AuditGuard,
    FullScopedFilingMetadata,
    accession_result,
    assignment_counts,
    guarded_fetch,
)
from asof.sec_documentation import DocumentationStop, MetadataUnknown

ACC = "0000000123-23-000001"
URLS = resource_urls(123, ACC)


class Bytes(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"x" * 100000


def client(tmp_path, monkeypatch, handler, used=140):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"actual_HTTP_attempts": used, "ceiling": 34402}))
    c = FullScopedFilingMetadata(tuple(URLS.values()), budget, tmp_path / "requests.jsonl",
                                 tmp_path / "raw", transport=httpx.MockTransport(handler))
    c.check = lambda: None
    return c


def test_full_cap_is_unknown_bounded_and_next_resource_can_finish(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return (httpx.Response(200, stream=Bytes()) if len(calls) == 1
                else httpx.Response(200, stream=httpx.ByteStream(b"bounded")))

    c = client(tmp_path, monkeypatch, handler)

    async def run():
        async with c:
            with pytest.raises(MetadataUnknown):
                await c.fetch(URLS["header"])
            assert c.last_record["bytes"] == 65536
            assert not c.last_record["body_complete"] and not c.stopped
            assert await c.fetch(URLS["index"]) == b"bounded"

    asyncio.run(run())
    assert calls == list(URLS.values())
    assert json.loads(c.budget_path.read_text()) == {"actual_HTTP_attempts": 142, "ceiling": 34402}


@pytest.mark.parametrize("failure", [403, 429, 503, 302, "transport"])
def test_full_adapter_failure_is_final_without_retry(tmp_path, monkeypatch, failure):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if failure == "transport":
            raise httpx.ConnectError("invented", request=request)
        return httpx.Response(failure, headers={"location": URLS["index"]},
                              stream=httpx.ByteStream(b""))

    c = client(tmp_path, monkeypatch, handler)

    async def run():
        async with c:
            with pytest.raises(DocumentationStop):
                await c.fetch(URLS["header"])
            with pytest.raises(DocumentationStop, match="already_stopped"):
                await c.fetch(URLS["index"])

    asyncio.run(run())
    assert calls == [URLS["header"]] and c.attempts == 1


def test_full_budget_ceiling_stops_before_transport(tmp_path, monkeypatch):
    def handler(request):
        pytest.fail("exhausted budget reached transport")

    c = client(tmp_path, monkeypatch, handler, used=34402)

    async def run():
        async with c:
            with pytest.raises(DocumentationStop, match="budget_exhausted"):
                await c.fetch(URLS["header"])

    asyncio.run(run())
    assert c.attempts == 0


def test_cancelled_transport_records_charged_attempt_and_partial_body(tmp_path, monkeypatch):
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    c = client(tmp_path, monkeypatch, handler)

    async def run():
        async with c:
            task = asyncio.create_task(c.fetch(URLS["header"]))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())
    assert c.stopped and c.attempts == 1
    assert c.last_record["stop_reason"] == "cancelled_before_completion"
    assert not c.last_record["body_complete"]


def test_guard_failure_cannot_be_masked_by_completed_unknown(tmp_path, monkeypatch):
    def handler(request):
        return httpx.Response(404, stream=httpx.ByteStream(b""))

    c = client(tmp_path, monkeypatch, handler)

    clocks = iter([(100, 100), (101, 101), (106, 102)])
    guard = AuditGuard(lambda: next(clocks), lambda: 0)

    async def run():
        async with c:
            with pytest.raises(DocumentationStop, match="host_sleep"):
                await guarded_fetch(c, URLS["header"], guard)

    asyncio.run(run())
    assert c.attempts == 1


@pytest.mark.parametrize("reason", ["sleep", "wall", "disk"])
def test_record_and_stop_guards(reason):
    clocks = iter([(100, 100), (106, 101) if reason == "sleep" else (101, 101)])
    now = [0]
    guard = AuditGuard(lambda: next(clocks), lambda: DISK_BYTES if reason == "disk" else 0,
                       wall_seconds=10, monotonic=lambda: now[0])
    now[0] = 11 if reason == "wall" else 1
    with pytest.raises(DocumentationStop):
        guard.check()
    assert bool(guard.interruptions) == (reason == "sleep")


def test_source_agreement_is_not_qualified_UTC_and_conflicting_paths_stay_unknown():
    stamp = "2023-01-05T15:30:00+00:00"
    row = {"accession": ACC, "pool": "invented", "pair_time": stamp, "bulk_time": stamp,
           "cik_pair": 123, "cik_bulk": 123, "candidate_times": [stamp]}
    header = parse_header(
        f"ACCESSION NUMBER: {ACC}\n<ACCEPTANCE-DATETIME>20230105103000\n"
        "FILER:\n CENTRAL INDEX KEY: 0000000123".encode(), ACC)
    index = parse_index(b"Accepted</div><div>2023-01-05 10:30:00</div>")
    resources = [{"kind": "header", "parsed": header, "path_CIK": 123},
                 {"kind": "index", "parsed": index, "path_CIK": 123}]
    value = accession_result(row, resources)
    assert value["agreement_class"] == "both_match_assumption"
    assert value["conditional_UTC_assuming_Eastern"] == stamp
    assert value["qualified_UTC"] is None and value["unresolved_reasons"]
    resources.append({"kind": "header", "parsed": {"unknown": "missing"}, "path_CIK": 456})
    assert accession_result(row, resources)["conditional_UTC_assuming_Eastern"] is None


def test_offline_assignment_counts_keep_missing_and_actual_vs_conditional_distinct():
    before, after = "2023-01-31T20:45:00+00:00", "2023-02-01T00:30:00+00:00"
    universe = [
        {"accession": "A", "cik_pair": 123, "pair_time": before, "bulk_time": before,
         "candidate_times": [before, after]},
        {"accession": "B", "cik_pair": 123, "pair_time": "2023-01-31T20:30:00+00:00",
         "bulk_time": "2023-01-31T20:30:00+00:00",
         "candidate_times": ["2023-01-31T20:30:00+00:00"]},
    ]
    audited = [{"accession": "A", "conditional_UTC_assuming_Eastern": after,
                "outside_frozen_candidate_envelope": False}]
    closes = [datetime.fromisoformat(t) for t in
              ("2023-01-31T21:00:00+00:00", "2023-02-01T21:00:00+00:00")]
    start, end = datetime.fromisoformat("2023-01-01T00:00:00+00:00"), datetime.fromisoformat(
        "2023-03-01T00:00:00+00:00")
    result = assignment_counts(universe, audited, closes, closes[:1], start, end)
    counts = result["conditional_diagnostics_only"]["stored_pair_versus_conditional"]
    assert counts["first_registered_close_changed"] == counts["UTC_month_changed"] == 1
    assert counts["eligibility_record_month_instances_changed"] == 1
    assert counts["latest_filing_firm_months_changed"] == 1
    assert result["qualified_assignment_changes"] is None
    audited[0]["conditional_UTC_assuming_Eastern"] = None
    missing = assignment_counts(universe, audited, closes, closes[:1], start, end)
    counts = missing["conditional_diagnostics_only"]["stored_pair_versus_conditional"]
    assert counts["conditional_accessions"] == 0
    assert counts["latest_filing_firm_months_unresolved"] == 1


def runner_module(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("full_timestamp_runner",
                                                 scripts / "run_full_timestamps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_second_run_refuses_before_loading_config_or_transport(tmp_path, monkeypatch):
    runner = runner_module(monkeypatch)
    status = tmp_path / "status.json"
    status.write_text("{}")
    monkeypatch.setattr(runner, "STATUS", status)
    with pytest.raises(RuntimeError, match="already attempted"):
        asyncio.run(runner.run())


def test_report_accounts_for_all_unattempted_after_pre_request_stop(tmp_path, monkeypatch):
    runner = runner_module(monkeypatch)
    for name in ("CONFIG", "STATUS", "REPORT", "BUDGET", "INVENTORY", "ROSTER", "UNIVERSE",
                 "CALENDAR", "OUTCOMES", "REQUESTS", "CHECKPOINT", "TABLE"):
        monkeypatch.setattr(runner, name, tmp_path / f"{name.lower()}.json")
    monkeypatch.setattr(runner, "PRIVATE", tmp_path)
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    runner.CONFIG.write_text(json.dumps({"exact_lists": {}, "input_SHA256": {},
                                         "source_SHA256": {}, "documentation": {"URLs": []}}))
    runner.STATUS.write_text(json.dumps({"status": "stopped_final", "freeze_commit": "invented"}))
    runner.BUDGET.write_text(json.dumps({"actual_HTTP_attempts": 140, "ceiling": 34402}))
    row = {"accession": ACC, "pool": "invented", "cik_pair": 123, "cik_bulk": 123,
           "pair_time": "2023-01-05T15:30:00+00:00", "bulk_time": "2023-01-05T15:30:00+00:00",
           "candidate_times": ["2023-01-05T15:30:00+00:00"]}
    runner.write_lines(runner.ROSTER, [row])
    runner.write_lines(runner.UNIVERSE, [row])
    runner.write_lines(runner.INVENTORY, [
        {"accession": ACC, "URL": u, "kind": k, "path_CIK": 123}
        for k, u in URLS.items()])
    runner.CALENDAR.write_text(json.dumps({
        "closes": ["2023-01-05T21:00:00+00:00"], "formations": [],
        "start": "2023-01-01T00:00:00+00:00", "end": "2023-02-01T00:00:00+00:00"}))
    runner.report()
    value = json.loads(runner.REPORT.read_text())
    assert value["accessions_accounted_for"] == value["unresolved_accessions"] == 1
    assert value["resources_not_attempted"] == 2 and value["new_HTTP_attempts"] == 0
    assert value["qualified_UTC_accessions"] == 0
    assert runner.load_lines(runner.TABLE)[0]["qualified_UTC"] is None
