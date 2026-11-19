"""Guarded private excerpt-packet preparation; no human gold or independent review is created."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from asof.research.feasibility import FAMILIES, guard_manifest, project_cases
from asof.research_intake import IntakeReport
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

FIELDS = ("item_id", "reviewer_id", "AI_suggestion_seen", "status", "value", "unit",
          "reporting_year", "evidence_quote", "rationale")
SOURCES = ("src/asof/reader_review.py", "src/asof/runtime.py", "src/asof/document_scope.py",
           "src/asof/research/feasibility.py", "src/asof/research_intake.py",
           "scripts/prepare_reader_review.py", "tests/test_reader_review.py",
           "results/reader_review_plan.json", "docs/FOCUSED_READER.md")


def _read(path: Path, limit: int, expected: str, receipt: dict, role: str) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(limit+1)
    receipt[f"{role}_bytes_read"] = len(raw)
    if len(raw) > limit or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"prior private input content pin/cap failed: {path.name}")
    return raw


def select_items(manifest: dict, cases: list[dict], *, seed: int, limit: int) -> list[dict]:
    """Hash-ranked, issuer-disjoint current excerpt selection; not a random accuracy audit."""
    project_cases(manifest, cases)  # Bind every source/date/case to the guarded manifest.
    by_id = {row["case_id"]: row for row in manifest["cases"]}
    candidates = []
    for row in cases:
        for family in FAMILIES:
            metric = row["metrics"].get(family)
            if metric is None or not metric["observations"][2]["evidence"]:
                continue
            excerpt = metric["observations"][2]["evidence"][0]["context"]
            if not isinstance(excerpt, str) or not excerpt or len(excerpt) > 1024:
                raise ValueError("unexpected derived excerpt shape or size")
            key = hashlib.sha256(f"{seed}:{row['case_id']}:{family}".encode()).hexdigest()
            candidates.append((key, row, family, excerpt))
    result, issuers = [], set()
    for _, row, family, excerpt in sorted(candidates, key=lambda value: value[0]):
        if row["cik"] in issuers:
            continue
        issuers.add(row["cik"])
        ref = by_id[row["case_id"]]["annual"][2]
        result.append({
            "item_id": f"REVIEW-{len(result)+1:02d}", "metric_family": family,
            "question": "Does this excerpt support an issuer-owned value, stated unit and year? "
                        "If context/identity/period is insufficient, mark insufficient_context.",
            "excerpt": excerpt, "evidence_kind": "prior_derived_window_not_full_filing",
            "provenance": {key: ref[key] for key in (
                "accession", "cik", "accepted_at", "knowledge_time", "report_date", "url")},
            "requested_reporting_year": ref["report_date"][:4],
            "source_case_id": row["case_id"], "expected_label": None,
        })
        if len(result) == limit:
            break
    return result


def check_reviews(items: list[dict], submissions: list[list[dict]]) -> IntakeReport:
    """Check declared first-pass independence/completeness; never authenticate reviewers or gold."""
    issues = []
    identities = {item["item_id"] for item in items}
    if not identities or len(identities) != len(items):
        issues.append("nonempty_unique_packet_required")
    if len(submissions) != 2:
        issues.append("two_independent_first_passes_required")
    reviewers = []
    records = 0
    for number, rows in enumerate(submissions, 1):
        if any(not isinstance(value, str) for row in rows for value in row.values()):
            raise TypeError("review CSV cells must be strings")
        ids = {row.get("reviewer_id", "").strip() for row in rows}
        if len(ids) != 1 or "" in ids:
            issues.append(f"file{number}:one_named_independent_reviewer_required")
        else:
            reviewers.extend(ids)
        if {row.get("item_id") for row in rows} != identities or len(rows) != len(identities):
            issues.append(f"file{number}:packet_coverage_or_duplicate_error")
        for row in rows:
            records += 1
            if set(row) != set(FIELDS):
                issues.append(f"file{number}:field_contract_changed")
                continue
            if row["AI_suggestion_seen"].lower() != "false":
                issues.append(f"file{number}:blind_first_pass_not_declared")
            if row["status"] not in ("supported", "unsupported_within_excerpt", "insufficient_context"):
                issues.append(f"file{number}:unfilled_or_invalid_status")
            if not row["rationale"].strip():
                issues.append(f"file{number}:rationale_required")
            if row["status"] == "supported":
                item = next((item for item in items if item["item_id"] == row["item_id"]), None)
                try:
                    numeric = Decimal(row["value"])
                    valid_number = numeric.is_finite()
                except InvalidOperation:
                    valid_number = False
                if (not all(row[key].strip() for key in (
                        "value", "unit", "reporting_year", "evidence_quote"))
                        or not valid_number or item is None
                        or re.fullmatch(r"[0-9]{4}", row["reporting_year"]) is None
                        or row["reporting_year"] != item["requested_reporting_year"]
                        or row["evidence_quote"] not in item["excerpt"]):
                    issues.append(f"file{number}:complete_supported_tuple_and_verbatim_quote_required")
            elif any(row[key] for key in ("value", "unit", "reporting_year", "evidence_quote")):
                issues.append(f"file{number}:unresolved_item_cannot_also_have_answer")
    if len(reviewers) == 2 and reviewers[0] == reviewers[1]:
        issues.append("same_reviewer_is_not_independent")
    return IntakeReport(
        "blocked" if issues else "ready_for_human_review", "excerpt_scoped_not_full_disclosure",
        records, tuple(sorted(set(issues))),
        ("Declarations do not authenticate independence; agreement still needs source/adjudication review.",
         "Excerpt absence is not full-disclosure absence. No gold or scientific acceptance created."))


def prepare(root: Path) -> dict:
    plan = json.loads((root / "results" / "reader_review_plan.json").read_bytes())
    private = root / "data" / "reader_review_v1"
    report = root / "results" / "reader_review_packet.json"
    if report.exists() or (private / "attempt.json").exists():
        raise FileExistsError("review packet already attempted; no overwrite/reselection")
    if (plan["profile"] != "CL-FOCUS-REVIEW-PACKET-01" or plan["max_items"] != 12
            or plan["minimum_items"] != 6 or plan["seed"] != 202611190752
            or plan["raw_cache_reads_allowed"] is not False or plan["model_calls_allowed"] is not False):
        raise ValueError("review packet scope differs from the frozen bounded profile")
    lineage = frozen_receipt(root, SOURCES)
    private.mkdir(parents=True, exist_ok=True)
    write_receipt(private / "attempt.json", {"lineage": lineage, "plan": plan})
    result = {"status": "stopped", "independent_review_completed": False, "gold_labels": 0,
              "lineage": lineage, "derived_text_bytes_read": 0}
    started = time.monotonic()
    try:
        source = root / "data" / "kpi_omission_dev_v1"
        manifest_raw = _read(source / "manifest.json", 256 << 10, plan["manifest_sha256"],
                             result, "metadata")
        manifest = json.loads(manifest_raw)
        result["scope"] = guard_manifest(manifest)
        raw = _read(source / "cases.json", 1 << 20, plan["cases_sha256"],
                    result, "derived_text")
        result["derived_text_bytes_read"] = len(raw)
        items = select_items(manifest, json.loads(raw), seed=plan["seed"], limit=plan["max_items"])
        if len(items) < plan["minimum_items"]:
            raise ValueError("insufficient issuer-disjoint evidence windows; no raw-cache fallback")
        if time.monotonic()-started > 30 or peak_rss_bytes() > 256 << 20:
            raise RuntimeError("packet preparation time/RSS ceiling before writing excerpts")
        write_receipt(private / "packet.json", {
            "status": "unlabelled_private_excerpt_packet", "items": items,
            "no_AI_answers_or_expected_values_shown": True,
            "limitations": "Selected mention-bearing windows; may lack identity/unit/year context.",
        })
        template = [{key: item["item_id"] if key == "item_id" else "" for key in FIELDS}
                    for item in items]
        for name in ("reviewer_a.csv", "reviewer_b.csv"):
            with (private / name).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(template)
        intake = check_reviews(items, [template, template])
        result.update(
            status="prepared_unlabelled_not_independently_reviewed", item_count=len(items),
            input_manifest_sha256=plan["manifest_sha256"], input_cases_sha256=plan["cases_sha256"],
            packet_sha256=hashlib.sha256((private / "packet.json").read_bytes()).hexdigest(),
            blank_first_pass_files=2, intake_status=intake.status,
            blockers=list(intake.issues), raw_cache_body_reads=0,
            private_location="data/reader_review_v1", model_calls=0,
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        result["stop_reason"] = f"{type(exc).__name__}:{exc}"
    result["preparation_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    result["source_unchanged"] = all(
        hashlib.sha256(root.joinpath(*path.split("/")).read_bytes()).hexdigest() == digest
        for path, digest in lineage["source_SHA256"].items())
    if not result["source_unchanged"]:
        result["status"], result["stop_reason"] = "stopped", "packet preparation source changed"
    write_receipt(report, result)
    return result
