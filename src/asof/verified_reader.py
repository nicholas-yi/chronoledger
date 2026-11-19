"""Narrow grammar-backed verification/blank-unit repair; no judge, I/O or gold access."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, ValidationError

from asof.extraction import normalize
from asof.focused_reader import Answer, Case, abstention, grounded

UNITS = r"(?:usd million|usd thousand|eur million|eur thousand|subscribers|%)"
NUMBER = r"-?\d+(?:\.\d+)?"
ARMS = ("parser", "binding_parser", "single_pass", "verified")


@dataclass(frozen=True)
class Binding:
    value: str
    unit: str
    period: str
    evidence: str


def bindings(case: Case) -> tuple[Binding, ...]:
    """Recognize only explicit positive sentence forms, not general financial semantics."""
    issuer, metric, year = (re.escape(normalize(value)) for value in (
        case.issuer, case.metric, case.requested_period))
    prefix = r"(?:^|(?<=\. ))"
    patterns = [
        (rf"{prefix}{issuer} reported {metric} of (?P<value>{NUMBER}) "
         rf"(?P<unit>{UNITS}) for {year}\."),
    ]
    if normalize(case.metric) == "subscribers":
        patterns += [
            rf"{prefix}for {year}, {issuer} had (?P<value>{NUMBER}) (?P<unit>subscribers)\.",
            rf"{prefix}{issuer} had (?P<value>{NUMBER}) (?P<unit>subscribers) in {year}\.",
        ]
    source = normalize(case.source)
    return tuple(Binding(match["value"], match["unit"], case.requested_period,
                         match[0].removeprefix(" "))
                 for pattern in patterns for match in re.finditer(pattern, source))


def binding_parser(case: Case) -> Answer:
    """Stronger parser control: expose the deterministic capability behind the verifier."""
    candidates = bindings(case)
    identities = {(Decimal(row.value), row.unit, row.period) for row in candidates}
    if len(identities) != 1:
        return abstention("binding_grammar_missing_or_conflicting")
    row = candidates[0]
    return Answer(value=row.value, unit=row.unit, period=row.period, evidence=row.evidence,
                  abstain=False, reason="")


class WireFields(BaseModel):
    """Only decode the documented fields; blank unit may be repaired, other errors are not coerced."""

    model_config = ConfigDict(extra="forbid", strict=True)
    value: str | None
    unit: str
    period: str
    evidence: str
    abstain: bool
    reason: str


@dataclass(frozen=True)
class Verification:
    answer: Answer | None
    status: str
    reasons: tuple[str, ...]


def verify_response(case: Case, content: str) -> Verification:
    """Never use expected/gold; repair only an empty unit from uniquely bound quoted evidence.

    Accepted nonabstentions require a supported finite sentence grammar. Unsupported
    language is unavailable, not certified false. Existing explicit units/values/years
    are never changed. This does not certify source truth or general semantic entailment.
    """
    try:
        original = Answer.model_validate_json(content)
    except ValidationError:
        original = None
    if original is not None and original.abstain:
        return Verification(original, "preserved_abstention", ())
    try:
        wire = WireFields.model_validate_json(content)
    except ValidationError:
        return Verification(None, "invalid_response", ("malformed_or_wrong_field_types",))
    repair = wire.unit == "" and not wire.abstain
    if original is None:
        if not repair:
            return Verification(None, "invalid_response", ("not_a_blank_unit_only_error",))
        try:
            # A placeholder is used only to validate every other field before reading bindings.
            Answer(**{**wire.model_dump(), "unit": "pending-source-binding"})
        except ValidationError:
            return Verification(None, "invalid_response", ("not_a_blank_unit_only_error",))
    if wire.period != case.requested_period:
        return Verification(abstention("verifier_period_mismatch"), "rejected", ("period_mismatch",))
    if not wire.evidence or normalize(wire.evidence) not in normalize(case.source):
        return Verification(abstention("verifier_quote_unsupported"), "rejected", ("quote_unsupported",))
    candidates = bindings(case)
    identities = {(Decimal(row.value), row.unit, row.period) for row in candidates}
    if len(identities) != 1:
        return Verification(abstention("verifier_binding_missing_or_conflicting"), "rejected",
                            ("binding_missing_or_conflicting",))
    quoted = [row for row in candidates if normalize(row.evidence) in normalize(wire.evidence)
              and wire.value is not None and Decimal(row.value) == Decimal(wire.value)]
    if not quoted:
        return Verification(abstention("verifier_value_not_uniquely_bound_in_quote"), "rejected",
                            ("value_not_bound_in_quote",))
    unit = quoted[0].unit
    if not repair and normalize(wire.unit) != unit:
        return Verification(abstention("verifier_explicit_unit_mismatch"), "rejected",
                            ("explicit_unit_mismatch",))
    result = Answer(**{**wire.model_dump(), "unit": unit if repair else wire.unit})
    failures = grounded(case, result)
    if failures:
        return Verification(abstention("verifier_grounding_failure"), "rejected", failures)
    return Verification(result, "repaired_blank_unit" if repair else "verified_binding", ())


def load_robustness_cases(payload: dict) -> tuple[Case, ...]:
    if set(payload) != {"pairs"} or len(payload["pairs"]) != 12:
        raise ValueError("the frozen robustness fixture must contain twelve pairs")
    cases = []
    seen = set()
    for pair in payload["pairs"]:
        if pair["relation"] not in ("same", "changed") or len(pair["cases"]) != 2:
            raise ValueError("each pair needs two cases and a declared relation")
        for i, row in enumerate(pair["cases"]):
            if row["id"] != f"{pair['id']}-{i}" or row["id"] in seen:
                raise ValueError("pair/case identities must be unique and bound")
            seen.add(row["id"])
            cases.append(Case(**{**row, "split": "evaluation", "category": pair["category"],
                                 "expected": tuple(row["expected"]) if row["expected"] else None}))
        equal = cases[-2].expected == cases[-1].expected
        if equal != (pair["relation"] == "same"):
            raise ValueError("authored expected tuples contradict the declared metamorphic relation")
    return tuple(cases)


def summarize_robustness(cases: Sequence[Case], records: dict[str, dict], fixture: dict) -> dict:
    result = {}
    for arm in ARMS:
        values = [records.get(case.id, {}).get(arm) for case in cases]
        scores = [value["score"] if value else {
            "correct": False, "answered": False, "outcome": "not_attempted"} for value in values]
        pair_stats = {"planned": 12, "completed": 0, "both_correct": 0,
                      "relation_violations": 0, "invalid_or_unattempted": 0}
        for pair in fixture["pairs"]:
            rows = [records.get(row["id"], {}).get(arm) for row in pair["cases"]]
            if any(row is None for row in rows):
                pair_stats["invalid_or_unattempted"] += 1
                continue
            pair_stats["completed"] += 1
            pair_stats["both_correct"] += all(row["score"]["correct"] for row in rows)
            if any(row.get("answer") is None for row in rows):
                pair_stats["invalid_or_unattempted"] += 1
                continue
            tuples = [None if row["answer"]["abstain"] else (
                Decimal(row["answer"]["value"]), normalize(row["answer"]["unit"]),
                row["answer"]["period"]) for row in rows]
            pair_stats["relation_violations"] += (
                (tuples[0] == tuples[1]) != (pair["relation"] == "same"))
        result[arm] = {
            "planned": len(cases), "recorded": sum(value is not None for value in values),
            "correct": sum(item["correct"] for item in scores),
            "answered": sum(item["answered"] for item in scores),
            "wrong_answers": sum(item["answered"] and not item["correct"] for item in scores),
            "outcomes": {name: sum(item["outcome"] == name for item in scores)
                         for name in sorted({item["outcome"] for item in scores})},
            "pairs": pair_stats,
            "known_latency_seconds": sum(value["latency_seconds"] for value in values
                                         if value and value.get("latency_seconds") is not None),
            "latency_measured_records": sum(
                value is not None and value.get("latency_seconds") is not None for value in values),
        }
    corrected = regressed = 0
    for case in cases:
        row = records.get(case.id, {})
        if "single_pass" in row and "verified" in row:
            old, new = (row[arm]["score"]["correct"] for arm in ("single_pass", "verified"))
            corrected += not old and new
            regressed += old and not new
    return {"arms": result, "paired_corrections": corrected, "paired_regressions": regressed,
            "promote": False, "independent_gold": False,
            "interpretation": "visible authored grammar cases, not real financial validation"}
