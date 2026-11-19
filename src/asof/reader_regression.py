"""Reproducible current-candidate replay of exposed invented cohorts, never historical regrading."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from asof.focused_reader import Case
from asof.reader_cells import audit_fixture
from asof.reader_field_challenge import build_coverage
from asof.reader_fields import (
    contexts,
    field_record,
    guarded_parser,
    load_field_cases,
    validate_source,
)
from asof.reader_reliability import canonical_unit
from asof.reader_stress import audit_cases, build_fixture
from asof.verified_reader import load_robustness_cases

FIXTURES = ("focused_reader", "verified_reader", "reader_stress", "linked_challenge",
            "reader_fields", "reader_reliability")


def cohorts(root: Path) -> tuple[dict[str, tuple[Case, ...]], dict[str, dict[str, dict]], dict[str, str]]:
    payloads, hashes = {}, {}
    for stem in FIXTURES:
        path = root / "tests" / "fixtures" / f"{stem}.json"
        raw = path.read_bytes()
        hashes[str(path.relative_to(root)).replace("\\", "/")] = hashlib.sha256(raw).hexdigest()
        payloads[stem] = json.loads(raw)
    original = tuple(Case(**{**row, "split": split,
                             "expected": tuple(row["expected"]) if row["expected"] else None})
                     for split, rows in payloads["focused_reader"].items() for row in rows)
    stress = build_fixture(payloads["reader_stress"])
    coverage_cases, coverage_labels = build_coverage()
    cell_cases, cell_labels = audit_fixture()
    labels = {
        stem: contexts(payloads[stem]) for stem in ("reader_fields", "reader_reliability")}
    labels.update(context_coverage192=coverage_labels, cell_sources12=cell_labels)
    return {
        "focused_original12": original,
        "grammar_robustness24": load_robustness_cases(payloads["verified_reader"]),
        "harder_model_subset24": audit_cases(stress),
        "harder_all288": tuple(case for pair in stress["pairs"] for case in pair["cases"]),
        "linked_challenge24": load_robustness_cases(payloads["linked_challenge"]),
        **{stem: load_field_cases(payloads[stem]) for stem in ("reader_fields", "reader_reliability")},
        "context_coverage192": coverage_cases, "cell_sources12": cell_cases,
    }, labels, hashes


def source_score(case: Case) -> dict:
    result = guarded_parser(case)
    answer = result.answer
    valid_proof = result.bundle is not None and not validate_source(case, result.bundle)
    if answer is None:
        correct, outcome = False, "invalid_response"
    elif answer.abstain:
        correct = case.expected is None
        outcome = "correct_refusal" if correct else "missed_answer"
    else:
        expected = case.expected
        correct = (expected is not None and Decimal(answer.value) == Decimal(expected[0])
                   and canonical_unit(answer.unit) == canonical_unit(expected[1])
                   and canonical_unit(answer.unit) is not None
                   and answer.period == expected[2] and valid_proof)
        outcome = "correct_answer" if correct else "wrong_admitted_answer"
    return {
        "correct": bool(correct), "outcome": outcome, "source_proof_valid": valid_proof,
        "answered": answer is not None and not answer.abstain,
        "proof_contract": result.bundle.contract if result.bundle is not None else None,
    }


def regression_matrix(root: Path) -> dict:
    datasets, labels, pins = cohorts(root)
    summaries = {}
    for name, cases in datasets.items():
        rows = {}
        for case in cases:
            row = source_score(case)
            if name in labels:
                record = field_record(case, guarded_parser(case), labels[name][case.id])
                row.update(correct=record["score"]["correct"], field_correct=record["field_correct"])
            rows[case.id] = row
        positives = sum(case.expected is not None for case in cases)
        correct = sum(row["correct"] for row in rows.values())
        summaries[name] = {
            "contract": "field-record-v1" if name in labels else "current_tuple_and_source_proof_diagnostic",
            "planned": len(cases), "correct": correct, "answerable": positives,
            "complete_answers": sum(row["correct"] and row["answered"] for row in rows.values()),
            "correct_refusals": sum(row["correct"] and not row["answered"] for row in rows.values()),
            "wrong_admitted_answers": sum(not row["correct"] and row["answered"] for row in rows.values()),
            "misses": [uid for uid, row in rows.items() if not row["correct"]],
            "proof_checks": {
                "answered": sum(row["answered"] for row in rows.values()),
                "valid": sum(row["answered"] and row["source_proof_valid"] for row in rows.values()),
            },
            "field_checks": (
                {field: {"correct": sum(row["field_correct"][field] is True for row in rows.values()),
                         "planned_answerable": positives}
                 for field in next(iter(rows.values()))["field_correct"]} if name in labels else None),
        }
    return {
        "status": "complete_exposed_current_candidate_regression",
        "cohorts": summaries, "fixture_sha256": pins,
        "posthoc_after_source_and_outcome_exposure": True,
        "historical_results_rewritten": False, "new_model_calls": 0,
        "independent_gold": False, "promote": False,
        "overlap": "Harder model subset overlaps all288; coverage/cell sources are reused elsewhere. Do not pool as independent observations.",
        "contract_warning": "Old cohorts use a new source-proof diagnostic, not their original single-quote scorer. Field-labelled cohorts retain field-record-v1.",
        "requirements": {
            "target": "Every declared supported regression case correct; never loosen proof/tuple checks to reach target.",
            "unknown_context_is_not_discovered_fact": True,
            "real_world_accuracy_established": False,
        },
    }
