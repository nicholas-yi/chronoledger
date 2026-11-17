"""Blind input projection and fixed reporting for the REAL3 format comparison."""

from __future__ import annotations

import json
from pathlib import Path

from asof.benchmark_baseline import TableInput
from asof.document_scope import DocumentDates, require_eligible_documents
from asof.reader_real_report import ANSWER_TYPES, VALID_OUTCOMES, arm_summary, exact_mcnemar

ARMS = ("column_format", "answer_first")


def _blind_object(value: dict) -> dict:
    if "uid" in value and "question" in value:
        return {"uid": value["uid"], "question": value["question"]}
    return value


def blind_inputs(
    path: Path, *, documents: tuple[DocumentDates, ...] | None = None,
) -> dict[str, TableInput]:
    """Drop question annotations at decode; inference gets only UID, question and source."""
    require_eligible_documents(documents)
    contexts = json.loads(path.read_bytes(), object_hook=_blind_object)
    result = {}
    for context in contexts:
        table = tuple(tuple(row) for row in context["table"]["table"])
        paragraphs = tuple(p["text"] for p in context["paragraphs"])
        for question in context["questions"]:
            uid = question["uid"]
            if uid in result:
                raise ValueError("duplicate_development_UID")
            result[uid] = TableInput(question["question"], table, paragraphs)
    return result


def paired(rows: list[dict]) -> dict:
    both = sum(r[ARMS[0]]["native_EM"] == r[ARMS[1]]["native_EM"] == 1 for r in rows)
    a = sum(r[ARMS[0]]["native_EM"] == 1 and r[ARMS[1]]["native_EM"] == 0 for r in rows)
    b = sum(r[ARMS[1]]["native_EM"] == 1 and r[ARMS[0]]["native_EM"] == 0 for r in rows)
    return {"n": len(rows), "right_only_with_A": a, "right_only_with_B": b,
            "both_right": both, "neither_right": len(rows) - a - b - both,
            "exact_McNemar_p_descriptive": exact_mcnemar(a, b) if rows else None}


def report(rows: list[dict]) -> dict:
    if len(rows) != 30 or len({r["id"] for r in rows}) != 30:
        raise ValueError("exactly_thirty_unique_questions_required")
    if any(r["answer_type"] not in ANSWER_TYPES for r in rows):
        raise ValueError("unexpected_native_answer_type")
    valid = [r for r in rows if all(r[a]["outcome"] in VALID_OUTCOMES for a in ARMS)]
    arms = {a: arm_summary(rows, a) for a in ARMS}
    for arm, summary in arms.items():
        summary["condition_attempts"] = summary.pop("generation_attempts")
        summary["generation_calls"] = sum(len(r[arm].get("calls", [])) for r in rows)
    return {
        "arms": arms,
        "paired_all30": paired(rows), "paired_valid_only": paired(valid),
        "completed_pairs": {
            "both_predictions_valid": len(valid),
            "both_condition_generations_finished": sum(all(
                r[a].get("generation_finished", False) for a in ARMS) for r in rows),
            "both_HTTP_responses": sum(all(r[a].get("response_received", False) for a in ARMS)
                                       for r in rows),
        },
        "by_answer_type": {kind: {a: arm_summary(
            [r for r in rows if r["answer_type"] == kind], a) for a in ARMS}
            for kind in ANSWER_TYPES},
        "arm_A_abstentions": {
            source: sum(r[ARMS[0]].get("abstention_source") == source for r in rows)
            for source in ("model", "system")},
        "arm_A_code_computed_arithmetic": sum(
            r[ARMS[0]].get("computed_by_code", False) for r in rows),
        "meaning": "Small public sample; possible training exposure. ArmA missed its invented "
                   "bar18/21+2/3 and user explicitly chose this comparison anyway. "
                   "Not historical usability,formalH1 or returns. Intervals ignore shared-report "
                   "dependence;McNemar descriptive. A uses up to2calls,B1: not matched compute.",
    }
