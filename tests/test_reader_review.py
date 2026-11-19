import hashlib
import json
from copy import deepcopy

from asof import reader_review
from asof.reader_review import FIELDS, check_reviews, select_items
from asof.research.feasibility import FAMILIES


def fixture():
    refs = [{"accepted_at": f"{year}-02-01T10:00:00Z",
             "knowledge_time": f"{year}-02-01T10:00:00Z", "report_date": f"{year-1}-12-31",
             "accession": f"fiction-{year}", "cik": 1, "url": "https://example.invalid/invented"}
            for year in (2014, 2015, 2016)]
    manifest = {"cases": [{"case_id": "fiction", "cik": 1, "annual": refs, "context": []}]}
    row = {
        "case_id": "fiction", "cik": 1,
        "sources": [{"accession": r["accession"],
                     "stored_knowledge_time_unqualified": r["knowledge_time"],
                     "metadata_report_date": r["report_date"]} for r in refs],
        "source_statuses": [{"status": "available"} for _ in refs],
        "earlier_context": [], "public_history_complete": False,
        "metrics": {name: {"observations": [
            {"alias_mentions": 1, "numeric_context_mentions": 1,
             "evidence": [{"context": "Invented issuer evidence for 2015, value 10 USD million."}]}
            for _ in refs]} for name in FAMILIES},
    }
    return manifest, [row]


def test_packet_selection_is_bound_and_unlabelled_and_empty_templates_are_not_gold():
    manifest, cases = fixture()
    items = select_items(manifest, cases, seed=7, limit=12)
    assert len(items) == 1 and items[0]["expected_label"] is None
    template = [{key: items[0]["item_id"] if key == "item_id" else "" for key in FIELDS}]
    report = check_reviews(items, [template, template])
    assert report.status == "blocked" and not report.scientific_acceptance
    assert not report.creates_gold_or_fetches_data


def test_distinct_named_first_passes_still_require_external_adjudication():
    manifest, cases = fixture()
    items = select_items(manifest, cases, seed=7, limit=12)
    row = {key: "" for key in FIELDS}
    row.update(item_id=items[0]["item_id"], reviewer_id="reviewer-a",
               AI_suggestion_seen="false", status="insufficient_context",
               rationale="Excerpt does not establish a matching fiscal period.")
    same = check_reviews(items, [[row], [deepcopy(row)]])
    assert "same_reviewer_is_not_independent" in same.issues
    other = {**row, "reviewer_id": "reviewer-b"}
    ready = check_reviews(items, [[row], [other]])
    assert ready.status == "ready_for_human_review" and not ready.scientific_acceptance


def test_packet_curator_guards_dates_before_any_derived_text_read(tmp_path, monkeypatch):
    manifest, _ = fixture()
    manifest["cases"][0]["annual"][0]["knowledge_time"] = "2024-01-01T10:00:00Z"
    source = tmp_path / "data" / "kpi_omission_dev_v1"
    source.mkdir(parents=True)
    raw = json.dumps(manifest).encode()
    (source / "manifest.json").write_bytes(raw)
    results = tmp_path / "results"
    results.mkdir()
    (results / "reader_review_plan.json").write_text(json.dumps({
        "profile": "CL-FOCUS-REVIEW-PACKET-01", "max_items": 12, "minimum_items": 6,
        "seed": 202611190752, "raw_cache_reads_allowed": False, "model_calls_allowed": False,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(), "cases_sha256": "0"*64,
    }))
    monkeypatch.setattr(reader_review, "frozen_receipt",
                        lambda *args: {"freeze_commit": "fixture", "source_SHA256": {}})
    result = reader_review.prepare(tmp_path)
    assert result["status"] == "stopped" and result["derived_text_bytes_read"] == 0
    assert "outside D13" in result["stop_reason"]
    assert not result["independent_review_completed"] and result["gold_labels"] == 0
