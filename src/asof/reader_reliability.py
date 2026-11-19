"""Strict response shape, equivalent units and source-gated routing; no model transport or I/O."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from asof.extraction import normalize
from asof.focused_reader import Answer, Case, abstention
from asof.linked_reader import LinkedResult
from asof.reader_fields import (
    Decision,
    field_messages,
    guarded_parser,
    summarize_fields,
)

MODEL_PAIRS = ("U02", "U03", "U04", "U06", "U10", "U12")
ARMS = ("baseline_free", "normalized_free", "baseline_structured",
        "normalized_structured", "source_gated")


class _Supported(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str = Field(pattern=r"^[+-]?[0-9]+(?:\.[0-9]+)?$", max_length=64)
    unit: str = Field(min_length=1, max_length=80)
    period: str = Field(pattern=r"^[0-9]{4}$")
    evidence: str = Field(min_length=1, max_length=8192)
    abstain: Literal[False]
    reason: Literal[""]


class _Refused(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: None
    unit: Literal[""]
    period: Literal[""]
    evidence: Literal[""]
    abstain: Literal[True]
    reason: str = Field(min_length=1, max_length=240)


WIRE = TypeAdapter(_Supported | _Refused)


@dataclass(frozen=True)
class Completion:
    result: LinkedResult
    original: Answer | None
    normalization: dict | None


def conforms_to_wire(content: str) -> bool:
    try:
        WIRE.validate_json(content)
        Answer.model_validate_json(content)
    except ValidationError:
        return False
    return True


def canonical_unit(unit: str) -> str | None:
    text = normalize(unit)
    for pattern in (
        r"(?P<currency>[a-z]{3}) (?P<scale>thousand|million|billion)s?",
        r"(?P<scale>thousand|million|billion)s? (?:of )?(?P<currency>[a-z]{3})",
    ):
        match = re.fullmatch(pattern, text)
        if match:
            return f"{match['currency']} {match['scale']}"
    if text in ("%", "percent"):
        return "%"
    if text == "subscribers" or re.fullmatch(r"[a-z]{3} per share", text):
        return text
    return None


def normalized_completion(case: Case, content: str) -> Completion:
    try:
        original = Answer.model_validate_json(content)
    except ValidationError:
        return Completion(LinkedResult(None, None, "invalid_response", ("invalid_answer_schema",)), None, None)
    if original.abstain:
        return Completion(LinkedResult(original, None, "preserved_abstention"), original, None)
    source = guarded_parser(case)
    if source.bundle is None or source.answer is None or source.answer.abstain:
        result = LinkedResult(abstention("source_unresolved_requires_review"), None,
                              "source_refused", source.reasons)
        return Completion(result, original, None)
    unit = canonical_unit(original.unit)
    if (unit is None or unit != canonical_unit(source.bundle.unit)
            or original.value is None or Decimal(original.value) != Decimal(source.bundle.value)
            or original.period != source.bundle.period):
        result = LinkedResult(abstention("explicit_tuple_mismatch"), None, "rejected",
                              ("no_value_currency_scale_or_period_conversion",))
        return Completion(result, original, None)
    quote = normalize(original.evidence)
    seed = any(normalize(case.source[span.start:span.end]) in quote
               for span in source.bundle.spans if span.role in ("value", "metric"))
    if not quote or quote not in normalize(case.source) or not seed:
        result = LinkedResult(abstention("source_quote_unsupported"), None, "rejected",
                              ("verbatim_value_or_metric_seed_required",))
        return Completion(result, original, None)
    event = None if normalize(original.unit) == unit else {
        "original_unit": original.unit, "canonical_unit": unit,
        "operation": "equivalent_unit_alias_no_conversion",
        "value_unchanged": True, "period_unchanged": True, "original_response_preserved": True,
    }
    answer = original.model_copy(update={"unit": unit})
    return Completion(LinkedResult(answer, source.bundle, "source_verified_normalized_unit"
                                   if event else "source_verified"), original, event)


def source_gated(case: Case) -> Decision:
    """Make the admission decision before generation; missing proof still needs human review."""
    source = guarded_parser(case)
    if source.answer is not None and not source.answer.abstain:
        return Decision(source, "source_parser", False)
    refusal = LinkedResult(abstention("source_unresolved_requires_review"), None,
                           "unresolved_requires_review", source.reasons)
    return Decision(refusal, "source_refusal_before_generation", False)


def reliability_messages(case: Case) -> list[dict]:
    request = field_messages(case)
    payload = json.loads(request[1]["content"])
    payload.update(target_currency=None, target_scale=None,
                   unit_requirement="Preserve the selected fact's stated units. A different "
                                    "default/column currency is not a request for conversion.")
    request[1]["content"] = json.dumps(payload, sort_keys=True)
    return request


def audit_cases(cases: tuple[Case, ...]) -> tuple[Case, ...]:
    selected = tuple(case for case in cases if case.id.rsplit("-", 1)[0] in MODEL_PAIRS)
    if len(selected) != 12 or {case.id for case in selected} != {
            f"{pair}-{member}" for pair in MODEL_PAIRS for member in range(2)}:
        raise ValueError("the fixed paired-generation audit requires six complete source pairs")
    return selected


def generation_orders(cases: tuple[Case, ...]) -> dict[str, tuple[str, str]]:
    ordered = sorted(cases, key=lambda case: hashlib.sha256(
        f"202611191201:{case.id}".encode()).hexdigest())
    structured_first = {case.id for case in ordered[:len(ordered)//2]}
    return {case.id: ("structured", "free") if case.id in structured_first else ("free", "structured")
            for case in cases}


def summarize_reliability(cases: tuple[Case, ...], records: dict, labels: dict, calls: list[dict]) -> dict:
    common = summarize_fields(cases, records, labels, arm_names=ARMS)
    pair_changes = {}
    for version in ("free", "structured"):
        improved = regressed = 0
        for case in cases:
            before = records.get(case.id, {}).get(f"baseline_{version}")
            after = records.get(case.id, {}).get(f"normalized_{version}")
            if before is not None and after is not None:
                improved += not before["score"]["correct"] and after["score"]["correct"]
                regressed += before["score"]["correct"] and not after["score"]["correct"]
        pair_changes[version] = {"corrected": improved, "regressed": regressed}
    return {
        "contract": "field-record-v1", "arms": common["arms"],
        "normalization_same_output_changes": pair_changes,
        "wire_comparison": {
            version: {
                "recorded": sum(version in records.get(case.id, {}) for case in cases),
                "schema_valid": sum(records.get(case.id, {}).get(version, {}).get("schema_valid", False)
                                    for case in cases),
                "strict_wire_valid": sum(
                    records.get(case.id, {}).get(version, {}).get("strict_wire_valid", False)
                    for case in cases),
                "planned": len(cases),
                "attempted": sum(call.get("wire_contract") == version for call in calls),
                "known_call_seconds": sum(call["latency_seconds"] for call in calls
                                          if call.get("wire_contract") == version
                                          and call.get("latency_seconds") is not None),
                "missing_latency_attempts": sum(call.get("wire_contract") == version
                                                and call.get("latency_seconds") is None for call in calls),
            } for version in ("free", "structured")
        },
        "independent_gold": False, "promote": False,
        "actual_paired_calls_not_source_gated_deployment": True,
        "independent_review": common["independent_review"],
    }
