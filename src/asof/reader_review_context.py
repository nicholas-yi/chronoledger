"""Supplemental blind-review context forms; declarations and agreement never create human gold."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from asof.research_intake import IntakeReport

DIMENSIONS = ("issuer_binding", "metric_binding", "scope", "accounting_basis",
              "period_kind", "revision_status")
FIELDS = ("item_id", "reviewer_id", "AI_suggestion_seen", "source_packet_sha256",
          "field_name", "state", "value", "evidence_start", "evidence_end", "rationale")


def template_rows(item_count: int, packet_sha256: str) -> list[dict[str, str]]:
    if not 1 <= item_count <= 100 or re.fullmatch(r"[a-f0-9]{64}", packet_sha256) is None:
        raise ValueError("bounded item count and explicit packet SHA256 required")
    return [{
        **dict.fromkeys(FIELDS, ""), "item_id": f"REVIEW-{i:02d}", "field_name": dimension,
        "source_packet_sha256": packet_sha256,
    } for i in range(1, item_count+1) for dimension in DIMENSIONS]


def write_templates(destination: Path, *, item_count: int, packet_sha256: str) -> tuple[Path, Path]:
    rows = template_rows(item_count, packet_sha256)
    paths = tuple(destination / name for name in ("context_reviewer_a.csv", "context_reviewer_b.csv"))
    if any(path.exists() for path in paths):
        raise FileExistsError("context templates already exist; do not overwrite human work")
    destination.mkdir(parents=True, exist_ok=True)
    for path in paths:
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return paths


def check_context_reviews(items: list[dict], submissions: list[list[dict[str, str]]],
                          *, packet_sha256: str, base_submissions: list[list[dict[str, str]]]) -> dict:
    """Validate packet/offset/identity declarations in memory; no source reading or adjudication."""
    issues, reviewers, comparisons = [], [], {}
    by_id = {item["item_id"]: item for item in items}
    if not by_id or len(by_id) != len(items) or re.fullmatch(r"[a-f0-9]{64}", packet_sha256) is None:
        issues.append("unique_packet_and_pin_required")
    required = {(uid, field) for uid in by_id for field in DIMENSIONS}
    if len(submissions) != 2 or len(base_submissions) != 2:
        issues.append("two_matching_base_and_context_first_passes_required")
    for number, rows in enumerate(submissions):
        if any(not isinstance(value, str) for row in rows for value in row.values()):
            raise TypeError("context CSV cells must be strings")
        identities = {row.get("reviewer_id", "").strip() for row in rows}
        base_ids = ({row.get("reviewer_id", "").strip() for row in base_submissions[number]}
                    if number < len(base_submissions) else set())
        if len(identities) != 1 or "" in identities or identities != base_ids:
            issues.append(f"file{number+1}:same_named_reviewer_as_base_required")
        else:
            reviewers.extend(identities)
        if ({(row.get("item_id"), row.get("field_name")) for row in rows} != required
                or len(rows) != len(required)):
            issues.append(f"file{number+1}:complete_unique_item_dimension_coverage_required")
        values = {}
        for row in rows:
            if set(row) != set(FIELDS):
                issues.append(f"file{number+1}:field_contract_changed")
                continue
            if row["source_packet_sha256"] != packet_sha256:
                issues.append(f"file{number+1}:packet_pin_mismatch")
            if row["AI_suggestion_seen"].lower() != "false" or not row["rationale"].strip():
                issues.append(f"file{number+1}:blind_first_pass_and_rationale_required")
            state = row["state"]
            if state not in ("supported", "unknown", "not_applicable"):
                issues.append(f"file{number+1}:unfilled_or_invalid_state")
                continue
            if state == "supported":
                try:
                    left, right = int(row["evidence_start"]), int(row["evidence_end"])
                except ValueError:
                    issues.append(f"file{number+1}:exact_integer_offsets_required")
                    continue
                excerpt = by_id.get(row["item_id"], {}).get("excerpt", "")
                if not row["value"].strip() or not 0 <= left < right <= len(excerpt):
                    issues.append(f"file{number+1}:supported_value_and_in_excerpt_span_required")
            elif any(row[key] for key in ("value", "evidence_start", "evidence_end")):
                issues.append(f"file{number+1}:unknown_or_inapplicable_cannot_carry_value_or_span")
            key = (row["item_id"], row["field_name"])
            values[key] = (state, row["value"].strip())
        comparisons[number] = values
    if len(reviewers) == 2 and reviewers[0] == reviewers[1]:
        issues.append("same_reviewer_is_not_independent")
    complete = not issues
    disagreements = ([{"item_id": uid, "field_name": field}
                      for uid, field in sorted(required)
                      if comparisons[0][(uid, field)] != comparisons[1][(uid, field)]]
                     if complete else [])
    intake = IntakeReport(
        "blocked" if issues else "ready_for_human_review", "excerpt_context_first_passes_only",
        sum(len(rows) for rows in submissions), tuple(sorted(set(issues))),
        ("No reviewer authentication, semantic validation or automatic gold.",
         "Base first passes require their own existing validator; disagreements need human adjudication."))
    return {"intake": intake, "disagreements": disagreements,
            "independent_review_completed": False, "gold_labels": 0}
