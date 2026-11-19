from copy import deepcopy

import pytest

from asof.reader_review_context import check_context_reviews, template_rows, write_templates

PIN = "a"*64


def test_context_templates_are_blank_and_never_overwrite_first_passes(tmp_path):
    paths = write_templates(tmp_path, item_count=12, packet_sha256=PIN)
    assert all(path.exists() for path in paths)
    rows = template_rows(12, PIN)
    assert len(rows) == 72 and all(not row["reviewer_id"] and not row["value"] for row in rows)
    with pytest.raises(FileExistsError, match="do not overwrite"):
        write_templates(tmp_path, item_count=12, packet_sha256=PIN)


def filled(reviewer):
    return [{**row, "reviewer_id": reviewer, "AI_suggestion_seen": "false", "state": "unknown",
             "rationale": "Excerpt does not establish this context."}
            for row in template_rows(1, PIN)]


def test_review_context_requires_distinct_named_blind_complete_first_passes_and_pins():
    items = [{"item_id": "REVIEW-01", "excerpt": "Invented fact"}]
    a, b = filled("reviewer-a"), filled("reviewer-b")
    base = [[{"reviewer_id": "reviewer-a"}], [{"reviewer_id": "reviewer-b"}]]
    good = check_context_reviews(items, [a, b], packet_sha256=PIN, base_submissions=base)
    assert good["intake"].status == "ready_for_human_review"
    assert not good["independent_review_completed"] and good["gold_labels"] == 0
    assert good["disagreements"] == []
    bad = deepcopy(b)
    bad[0].update(state="supported", value="Other", evidence_start="0", evidence_end="999")
    assert check_context_reviews(items, [a, bad], packet_sha256=PIN,
                                 base_submissions=base)["intake"].status == "blocked"
    assert check_context_reviews(items, [a, a], packet_sha256=PIN,
                                 base_submissions=[base[0], base[0]])["intake"].status == "blocked"
    bad = deepcopy(b)
    bad[0]["AI_suggestion_seen"] = "true"
    assert check_context_reviews(items, [a, bad], packet_sha256=PIN,
                                 base_submissions=base)["intake"].status == "blocked"


def test_disagreement_is_retained_and_unknown_cannot_silently_acquire_a_value():
    items = [{"item_id": "REVIEW-01", "excerpt": "Invented fact"}]
    a, b = filled("reviewer-a"), filled("reviewer-b")
    base = [[{"reviewer_id": "reviewer-a"}], [{"reviewer_id": "reviewer-b"}]]
    b[0].update(state="supported", value="Invented", evidence_start="0", evidence_end="8")
    report = check_context_reviews(items, [a, b], packet_sha256=PIN, base_submissions=base)
    assert report["disagreements"] == [{"item_id": "REVIEW-01", "field_name": "issuer_binding"}]
    assert report["gold_labels"] == 0
    b[0]["state"] = "unknown"
    assert check_context_reviews(items, [a, b], packet_sha256=PIN,
                                 base_submissions=base)["intake"].status == "blocked"
