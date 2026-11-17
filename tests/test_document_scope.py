from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from asof.document_scope import DocumentDates, parse_document_date, require_eligible_documents
from asof.periods import HoldoutAccessError

SAFE = DocumentDates("2017-02-01T10:00:00Z", "2017-02-01T10:00:00Z", "2016-12-31")


@pytest.mark.parametrize("when", [
    "2011-12-31", "2019-01-01", "2021-12-31", "2022-01-01", "2025-06-30",
    "2024-07-01", "2026-06-30", "2026-10-31", "2027-01-01",
])
@pytest.mark.parametrize("field", ["accepted_at", "knowledge_at", "period_end"])
def test_each_date_role_rejects_reserved_boundaries_and_followups(when, field) -> None:
    with pytest.raises(HoldoutAccessError):
        require_eligible_documents((replace(SAFE, **{field: when}),))


def test_development_boundaries_named_months_and_utc_date_conversion() -> None:
    require_eligible_documents((DocumentDates("2012-01-01", "2012-01-01", "2012-01-01"),))
    require_eligible_documents((DocumentDates("2018-12-31", "2018-12-31", "December 31, 2018"),))
    assert parse_document_date("March 31, 2017", "period") == date(2017, 3, 31)
    with pytest.raises(HoldoutAccessError):
        require_eligible_documents((DocumentDates(
            "2018-12-31T23:30:00-05:00", "2018-12-31T23:30:00-05:00", "2018-12-31"),))


@pytest.mark.parametrize("value", [None, "", "unknown", "2017", "01/02/2017", True,
                                   datetime(2017, 1, 1)])
@pytest.mark.parametrize("field", ["accepted_at", "knowledge_at", "period_end"])
def test_unknown_or_unparseable_dates_fail_closed(value, field) -> None:
    with pytest.raises(HoldoutAccessError):
        require_eligible_documents((replace(SAFE, **{field: value}),))


def test_used_context_is_not_exempt_from_the_guard() -> None:
    with pytest.raises(HoldoutAccessError):
        require_eligible_documents((replace(SAFE, contexts=(
            replace(SAFE, knowledge_at="2023-01-01"),)),))
    require_eligible_documents((replace(SAFE, contexts=(SAFE,)),))
    with pytest.raises(HoldoutAccessError):
        require_eligible_documents(None)


def test_sec_body_guard_precedes_cache_or_transport(monkeypatch) -> None:
    from asof.edgar import EdgarClient

    client = EdgarClient.__new__(EdgarClient)
    seen = []
    monkeypatch.setattr(EdgarClient, "get_bytes", lambda self, url: seen.append(url) or b"fictional")
    with pytest.raises(HoldoutAccessError):
        client.filing_document(1, "fake", "a.htm")
    with pytest.raises(HoldoutAccessError):
        client.filing_document(1, "fake", "a.htm", dates=replace(SAFE, period_end="2023-01-01"))
    assert seen == []
    assert client.filing_document(1, "fake", "a.htm", dates=SAFE) == b"fictional"
    assert len(seen) == 1


def test_derived_report_feature_read_is_also_guarded(monkeypatch) -> None:
    from asof import features

    monkeypatch.setattr(features, "feature_path", lambda _: pytest.fail("no file access"))
    with pytest.raises(HoldoutAccessError):
        features.load("unknown")


def test_scope_does_not_accept_future_period_or_preacceptance_knowledge() -> None:
    with pytest.raises(HoldoutAccessError):
        require_eligible_documents((replace(SAFE, period_end="2018-12-31"),))
    with pytest.raises(HoldoutAccessError):
        require_eligible_documents((replace(SAFE, knowledge_at="2016-01-01"),))
    require_eligible_documents((DocumentDates(
        datetime(2017, 1, 1, tzinfo=UTC), datetime(2017, 1, 2, tzinfo=UTC), "2016-12-31"),))
