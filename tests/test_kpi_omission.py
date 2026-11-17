import gzip

import pytest

from asof.kpi_omission import (
    METRICS,
    CachedText,
    analyze_case,
    metric_mentions,
    pin_filing,
    read_cached,
    summarize,
)


def document(text: str, accession: str = "test") -> CachedText:
    return CachedText("available", text, len(text), {"accession": accession})


def test_lexical_absence_is_a_candidate_not_semantic_or_public_novelty() -> None:
    previous = document("Our order backlog was 25 million units.")
    current = document("Our new capacity grew 10 percent.")
    case = analyze_case({"case_id": "test", "cik": 1}, [previous, previous, current], [previous])
    assert case["candidate_metrics"] == ["backlog"]
    assert case["metrics"]["backlog"]["earlier_cached_primary_mentions"] == ["test"]
    assert case["metrics"]["backlog"]["market_novelty"] == "unresolved_incomplete_public_history"
    assert not case["human_gold"] and not case["public_history_complete"]


def test_missing_document_is_unknown_not_omission_or_zero() -> None:
    old = document("Our backlog was 20 units.")
    missing = CachedText("unavailable", None, 0, {}, "not_cached")
    case = analyze_case({"case_id": "test", "cik": 1}, [old, old, missing], [])
    assert case["status"] == "incomplete_source_coverage"
    assert case["candidate_count"] is None
    assert case["baselines"] is None


def test_alias_presence_and_numeric_context_do_not_certify_reporting() -> None:
    definition = document("We explain backlog in our annual report.")
    old = document("Our backlog was 20 units.")
    current = document("We no longer report backlog.")
    insufficient = analyze_case({"case_id": "a", "cik": 1}, [definition, old, current], [])
    assert insufficient["candidate_count"] == 0
    observed = analyze_case({"case_id": "a", "cik": 1}, [old, old, current], [])
    assert observed["candidate_count"] == 0
    assert observed["persistent_alias_controls"] == ["backlog"]
    assert "no longer" in observed["metrics"]["backlog"]["observations"][2][
        "evidence"][0]["explanation_cues_for_review"]


def test_metric_scope_and_exact_evidence_offsets_are_preserved() -> None:
    text = "Gross revenue retention is 92%. Net revenue retention is 110%."
    matches = metric_mentions(text, METRICS["net_revenue_retention"])
    assert matches["alias_mentions"] == 1
    e = matches["evidence"][0]
    assert text[e["match_start"]:e["match_end"]] == "Net revenue retention"
    assert text[e["context_start"]:e["context_end"]] == e["context"]


def test_cached_reader_uses_hash_pin_and_rejects_identity_conflict(tmp_path) -> None:
    from asof.edgar import response_cache_path
    from asof.kpi_omission import filing_url

    row = {"cik": 1, "accession": "0000000001-23-000001", "primary_doc": "a.htm",
           "form": "10-K", "knowledge_time": "2023-02-01T10:00:00+00:00",
           "report_date": "2022-12-31"}
    path = response_cache_path(filing_url(row), tmp_path)
    path.parent.mkdir()
    body = (b'<html><ix:nonNumeric name="dei:EntityCentralIndexKey">2</ix:nonNumeric>'
            b"<p>Backlog 20 units.</p></html>")
    path.write_bytes(gzip.compress(body))
    ref = pin_filing(row, tmp_path)
    assert read_cached(ref, tmp_path).reason == "inline_CIK_conflict"
    path.write_bytes(gzip.compress(body + b"changed"))
    with pytest.raises(ValueError, match="cache changed"):
        read_cached(ref, tmp_path)


def test_summary_does_not_invent_precision_and_handles_constant_baselines() -> None:
    old = document("Backlog was 20 units.")
    current = document("Backlog is 30 units.")
    rows = [analyze_case({"case_id": str(i), "cik": i}, [old, old, current], [])
            for i in range(4)]
    result = summarize(rows)
    assert result["validated_precision"] is None
    assert not result["incremental_alpha_established"]
    assert all(v["status"] == "not_estimable" for v in result["baseline_associations"].values())
    assert result["casebook_selection"].startswith("up to 6")


def test_body_cap_is_unknown_and_cache_miss_never_constructs_http_client(
    tmp_path, monkeypatch,
) -> None:
    import httpx

    import asof.kpi_omission as module
    from asof.edgar import response_cache_path

    def forbidden(*args, **kwargs):
        pytest.fail("offline reader must not create an HTTP client")

    monkeypatch.setattr(httpx, "Client", forbidden)
    row = {"cik": 1, "accession": "0000000001-23-000001", "primary_doc": "a.htm",
           "form": "10-K", "knowledge_time": "2023-02-01T10:00:00+00:00",
           "report_date": "2022-12-31"}
    absent = pin_filing(row, tmp_path)
    assert read_cached(absent, tmp_path).reason == "not_cached_at_freeze"
    path = response_cache_path(module.filing_url(row), tmp_path)
    path.parent.mkdir()
    path.write_bytes(gzip.compress(b"<html><p>Backlog 20 units.</p></html>"))
    ref = pin_filing(row, tmp_path)
    monkeypatch.setattr(module, "MAX_BODY", 8)
    capped = read_cached(ref, tmp_path)
    assert capped.text is None
    assert capped.reason == "body_cap_not_read_complete"
