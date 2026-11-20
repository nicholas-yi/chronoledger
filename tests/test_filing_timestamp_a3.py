import asyncio
import hashlib
import json
from datetime import date, datetime, timedelta

import httpx
import pytest

from asof.filing_clock_basis import (
    clock_basis_test,
    cutoff_consistency,
    first_close_direction,
    identity_class,
    parse_header_dates,
    possible_early_close,
    qualify,
)
from asof.filing_header_pilot import resource_urls
from asof.filing_timestamp_a3 import (
    A3Session,
    AdaptiveLimiter,
    a3_order,
    effective_outcomes,
    raw_resource_bytes,
)
from asof.filing_timestamp_audit import AuditGuard
from asof.sec_documentation import DocumentationStop, MetadataUnknown

ACCESSION = "0000000123-23-000001"


def header(wall="20230605170000", filed=("20230605", "20230605"), form="10-Q"):
    return (f"<SEC-HEADER>{ACCESSION}.hdr.sgml : {filed[0]}\n<ACCEPTANCE-DATETIME>{wall}\n"
            f"<FILING-DATE>{filed[0]}\nACCESSION NUMBER:\t\t{ACCESSION}\n"
            f"CONFORMED SUBMISSION TYPE:\t{form}\nFILED AS OF DATE:\t\t{filed[1]}\n"
            "FILER:\n\tCENTRAL INDEX KEY:\t\t\t0000000123\n").encode("latin-1")


def test_header_dates_require_one_filing_date_and_type():
    assert parse_header_dates(header(), ACCESSION) == {
        "wall": "20230605170000", "filing_date": "20230605", "form": "10-Q",
        "UTC_assuming_Eastern": "2023-06-05T21:00:00+00:00"}
    assert parse_header_dates(header(filed=("20230605", "20230606")), ACCESSION)["unknown"] == (
        "missing_or_nonunique_filing_date")
    assert "unknown" in parse_header_dates(header(wall="20231105013000"), ACCESSION)


@pytest.mark.parametrize(("wall", "filed", "expected"), [
    ("20230605172959", "20230605", "consistent"),
    ("20230605173000", "20230605", "consistent"),
    ("20230605173000", "20230606", "inconsistent_early_roll"),
    ("20230605174500", "20230606", "consistent"),
    ("20230605174500", "20230605", "consistent_commencement_lag_possible"),
    ("20230610120000", "20230610", "inconsistent_weekend_same_day"),
    ("20230605120000", "20230602", "adjusted_earlier_filing_date"),
])
def test_cutoff_consistency_at_the_rule_boundary(wall, filed, expected):
    assert cutoff_consistency(wall, filed) == expected


def world(truth: str) -> list[dict]:
    """Synthetic filings whose true deemed date follows the 17:30 Eastern civil rule."""
    rows = []
    days = [date(2023, 6, 5) + timedelta(days=d) for d in range(60)]
    days = [d for d in days if d.weekday() < 5]
    for i, day in enumerate(days[:40]):
        # Civil 16:30-17:29 and 17:40-21:00, plus 07:00 mornings.
        for civil in (datetime.combine(day, datetime.min.time()) + timedelta(hours=16, minutes=30 + i),
                      datetime.combine(day, datetime.min.time()) + timedelta(hours=17, minutes=40 + 3 * i),
                      datetime.combine(day, datetime.min.time()) + timedelta(hours=7)):
            nxt = day + timedelta(days=3 if day.weekday() == 4 else 1)
            filed = nxt if civil.time() > datetime.strptime("17:30", "%H:%M").time() else day
            shown = (civil - timedelta(hours=1) if truth == "fixed_EST"
                     else civil + timedelta(hours=4) if truth == "UTC" else civil)
            rows.append({"wall": shown.strftime("%Y%m%d%H%M%S"),
                         "filing_date": filed.strftime("%Y%m%d"), "form": "10-Q"})
    return rows


def test_clock_basis_accepts_civil_and_rejects_fixed_EST_and_UTC_worlds():
    civil = clock_basis_test(world("civil"))
    assert civil["passed"] and civil["fixed_EST_rejected"] and civil["UTC_rejected"]
    est = clock_basis_test(world("fixed_EST"))
    assert not est["fixed_EST_rejected"] and not est["passed"]
    utc = clock_basis_test(world("UTC"))
    assert not utc["UTC_rejected"] and not utc["passed"]
    exempt = clock_basis_test([{**r, "form": "4"} for r in world("civil")])
    assert exempt["evaluated_headers"] == 0 and not exempt["passed"]


def test_early_close_superset_and_qualification_rule():
    assert possible_early_close(date(2023, 11, 24)) and possible_early_close(date(2023, 7, 3))
    assert not possible_early_close(date(2023, 11, 23))
    row = {"accession": ACCESSION, "conditional_UTC_assuming_Eastern": "2023-11-24T19:00:00+00:00",
           "outside_frozen_candidate_envelope": False}
    good = [{"wall": "20231124140000", "filing_date": "20231124", "form": "10-Q"}]
    result = qualify(row, good, True)
    assert result["qualified_UTC"] == row["conditional_UTC_assuming_Eastern"]
    assert result["first_close_status"] == "possible_early_close_unresolved"
    assert qualify(row, good, False)["qualified_UTC"] is None
    rolled = [{**good[0], "filing_date": "20231127"}]
    assert qualify(row, rolled, True)["unresolved_reasons"] == [
        "filing_date_inconsistent_with_declared_clock"]
    two_paths = good + [{**good[0], "wall": "20231124140001"}]
    assert qualify(row, two_paths, True)["qualified_UTC"] is None


def test_identity_classes_from_observed_header_roles():
    def row(pair, bulk, roles, unknown=None):
        return {"cik_pair": pair, "cik_bulk": bulk,
                "CIK_role_notes": [{"observed_roles": roles, "unknown": unknown}]}
    assert identity_class(row(1, 2, {"FILER": ["0000000001", "0000000002"]})).startswith("both")
    assert identity_class(row(1, 2, {"FILER": ["0000000002"]})) == "bulk_CIK_only"
    assert identity_class(row(1, 1, {"FILER": ["0000000001"]})) == "agreeing_CIK_in_header"
    assert identity_class(row(1, 2, {}, "HTTP_404")) == "header_unread"


def test_first_close_direction_flags_only_early_stored_times_as_lookahead():
    closes = [datetime.fromisoformat(f"2023-06-0{d}T20:00:00+00:00") for d in (5, 6, 7)]
    universe = [{"accession": "a", "pair_time": "2023-06-05T19:00:00+00:00",
                 "bulk_time": "2023-06-05T23:00:00+00:00"},
                {"accession": "b", "pair_time": "2023-06-06T21:00:00+00:00",
                 "bulk_time": "2023-06-06T21:00:00+00:00"}]
    qualified = {"a": "2023-06-05T23:00:00+00:00", "b": "2023-06-06T19:00:00+00:00"}
    result = first_close_direction(universe, qualified, closes)
    assert result["stored_pair"]["stored_earlier_lookahead_risk"] == 1
    assert result["stored_pair"]["stored_later_delay_only"] == 1
    assert result["stored_bulk"]["same_first_close"] == 1


def test_merge_replaces_only_reeligible_resources_and_order_puts_them_first():
    ok = {"URL": "u1", "parsed": {}}
    failed = {"URL": "u2", "parsed": {"unknown": "resource_failed:HTTP_503"}}
    capped = {"URL": "u4", "parsed": {"unknown": "body_reached_read_cap_unqualified"}}
    merged = effective_outcomes([[ok, failed, capped], [{"URL": "u2", "parsed": {}}]])
    assert merged["u2"]["parsed"] == {}
    with pytest.raises(ValueError, match="protected"):
        effective_outcomes([[ok], [{"URL": "u1", "parsed": {}}]])
    with pytest.raises(ValueError, match="protected"):
        effective_outcomes([[{"URL": "u5", "parsed": {"unknown": "HTTP_404"}}], [{"URL": "u5", "parsed": {}}]])
    inventory = [{"URL": u} for u in ("u1", "u2", "u3", "u4", "u6")]
    order = a3_order(inventory, [{"URL": u} for u in ("u6", "u2", "u3")],
                     {"u1": ok, "u2": failed, "u4": capped})
    assert [r["URL"] for r in order] == ["u2", "u4", "u6", "u3"]
    assert order[1]["A3_reeligible_prior_outcome"] == "body_reached_read_cap_unqualified"
    assert [r["a3_order"] for r in order] == [0, 1, 2, 3]


def test_raw_bytes_are_hash_checked(tmp_path):
    folder = tmp_path / "seg" / "raw_metadata"
    folder.mkdir(parents=True)
    (folder / "request_1.bin").write_bytes(b"body")
    attempt = {"status": 200, "body_complete": True, "cache_file": "request_1.bin",
               "SHA256_observed_bytes": hashlib.sha256(b"body").hexdigest()}
    row = {"A3_segment": "seg", "A3_attempts": [attempt]}
    assert raw_resource_bytes(row, tmp_path, {"seg": tmp_path / "seg"}) == b"body"
    row["A3_attempts"] = [{**attempt, "SHA256_observed_bytes": "0" * 64}]
    with pytest.raises(ValueError, match="hash"):
        raw_resource_bytes(row, tmp_path, {"seg": tmp_path / "seg"})


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


def session(tmp_path, monkeypatch, handler, *, max_pauses=6, limit=None):
    monkeypatch.setenv("ASOF_USER_AGENT", "Fictional Test test@example.invalid")
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"actual_HTTP_attempts": 3254, "ceiling": 34402}))
    clock = Clock()
    guard = AuditGuard(lambda: (clock.now, clock.now), lambda: 0, wall_seconds=50400,
                       monotonic=clock)
    value = A3Session({url()}, budget, tmp_path, guard, start_used=3254, max_pauses=max_pauses,
                      attempt_limit=limit, transport=httpx.MockTransport(handler),
                      limiter=AdaptiveLimiter(clock, clock.sleep))
    return value, clock


def run_fetch(s):
    async def go():
        async with s:
            return await s.fetch(url())
    return asyncio.run(go())


def test_limiter_never_paces_faster_than_A1():
    with pytest.raises(ValueError):
        AdaptiveLimiter(gap=0.5)
    limiter = AdaptiveLimiter(gap=1.0)
    limiter.slow(0.667)
    assert limiter.gap == 1.0


def test_repeated_503_pauses_slow_down_and_count_against_cap(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        status = 503 if len(calls) <= 2 else 200
        return httpx.Response(status, stream=httpx.ByteStream(b"ok"))

    s, clock = session(tmp_path, monkeypatch, handler, max_pauses=2)
    assert run_fetch(s) == b"ok"
    assert len(calls) == 3 and s.throttle_pauses == 2 and s.charged == 3
    assert s.limiter.gap == 1.0 and clock.now >= 1200
    assert json.loads((tmp_path / "budget.json").read_text())["actual_HTTP_attempts"] == 3257


def test_throttle_cap_stops_permanently(tmp_path, monkeypatch):
    s, _ = session(tmp_path, monkeypatch,
                   lambda r: httpx.Response(503, stream=httpx.ByteStream(b"")), max_pauses=1)
    with pytest.raises(DocumentationStop, match="A3_throttle_pause_cap"):
        run_fetch(s)
    assert s.stopped and s.throttle_pauses == 1 and s.charged == 2


def test_second_transport_failure_is_unknown_not_a_stop(tmp_path, monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("invented", request=request)

    s, clock = session(tmp_path, monkeypatch, handler)
    with pytest.raises(MetadataUnknown, match="transport_unresolved:transport_timeout"):
        run_fetch(s)
    assert not s.stopped and s.charged == 2 and s.throttle_pauses == 0 and clock.now >= 60


def test_segment_attempt_limit_is_a_hard_guard(tmp_path, monkeypatch):
    s, _ = session(tmp_path, monkeypatch,
                   lambda r: httpx.Response(200, stream=httpx.ByteStream(b"ok")), limit=0)
    with pytest.raises(DocumentationStop, match="attempt_limit"):
        run_fetch(s)
    assert s.charged == 0


def test_bodies_above_the_old_64KiB_bound_are_read_completely(tmp_path, monkeypatch):
    body = b"x" * 100_000
    s, _ = session(tmp_path, monkeypatch, lambda r: httpx.Response(200, stream=httpx.ByteStream(body)))
    assert run_fetch(s) == body
