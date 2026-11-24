"""REVIEW-PIPELINE-01: deterministic source rules first, the frozen AI-REVIEWER-02 only where rules defer.

Declared before its fresh measurement. Neither component is changed: the rules are the frozen claim
verifier and the AI arm is the frozen decomposed v2 reviewer. Only the routing below is new.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asof.claim_verifier import Claim, resolve_fact, verify_claim
from asof.reader_ai_review import ReviewTask

PIPELINE_ID = "REVIEW-PIPELINE-01"
RULE_VERDICT = {"supported": "supported", "contradicted": "unsupported", "review": "uncertain"}


@dataclass(frozen=True)
class Probe:
    """One review item: a candidate answer, its source, and the author's declared source status."""

    task: ReviewTask
    source_status: Literal["stated", "not_stated", "conflicting"]
    source_fact: tuple[str, str] | None
    category: str


def rule_decision(probe) -> dict:
    """Answered candidates become claim sentences; abstentions are refuted only by a proved source fact."""
    case, candidate = probe.task.case, probe.task.candidate
    if candidate.abstain:
        fact = resolve_fact(case.source, Claim(case.issuer, case.metric, "0", "usd million",
                                               case.requested_period, False))
        return {"verdict": "unsupported" if fact is not None else "uncertain",
                "reason": "source_fact_proved" if fact is not None else "nondisclosure_not_provable_by_rules"}
    claim = f"{case.issuer}'s {candidate.period} {case.metric} was {candidate.value} {candidate.unit}."
    decision = verify_claim(case.source, claim)
    return {"verdict": RULE_VERDICT[decision["verdict"]], "reason": decision["reason"], "claim": claim,
            "proof_valid": decision["proof_valid"]}


def route(rule: dict, ai_row: dict | None) -> tuple[str, str]:
    if rule["verdict"] in ("supported", "unsupported"):
        return rule["verdict"], "rules"
    if ai_row is not None and ai_row.get("valid"):
        return ai_row["verdict"], "ai_fallback"
    return "uncertain", "no_valid_ai_fallback"


def score(rows: list[dict], key: str) -> dict:
    resolved = [row for row in rows if row[key] in ("supported", "unsupported")]
    return {
        "planned": len(rows), "correct_verdicts": sum(row[key] == row["expected"] for row in rows),
        "false_support": sum(row[key] == "supported" and row["expected"] == "unsupported" for row in rows),
        "false_rejection": sum(row[key] == "unsupported" and row["expected"] == "supported" for row in rows),
        "uncertain_or_invalid": len(rows)-len(resolved), "resolved": len(resolved),
        "resolved_correct": sum(row[key] == row["expected"] for row in resolved),
    }


def evaluate(probes, ai_records: dict) -> dict:
    rows = []
    for probe in probes:
        rule = rule_decision(probe)
        ai_row = ai_records.get(probe.task.case.id, {}).get("ai_review_v3")
        verdict, source = route(rule, ai_row)
        rows.append({"id": probe.task.case.id, "category": probe.category, "expected": probe.task.expected_verdict,
                     "rules": rule["verdict"], "rule_detail": rule,
                     "ai": ai_row["verdict"] if ai_row is not None and ai_row.get("valid") else None,
                     "pipeline": verdict, "decided_by": source})
    return {
        "pipeline_id": PIPELINE_ID, "pipeline": score(rows, "pipeline"),
        "rules_only": score(rows, "rules"), "ai_only": score(rows, "ai"),
        "decided_by": {name: sum(row["decided_by"] == name for row in rows)
                       for name in ("rules", "ai_fallback", "no_valid_ai_fallback")},
        "rows": rows, "independent_human_gold": False, "promote": False,
    }
