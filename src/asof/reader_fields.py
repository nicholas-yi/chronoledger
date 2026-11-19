"""Parser-first routing and shared field-record scoring; no transport, labels in inference or I/O."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal

from asof.extraction import normalize
from asof.focused_reader import Answer, Case, abstention, messages
from asof.linked_reader import (
    EvidenceBundle,
    EvidenceSpan,
    LinkedResult,
    challenge_cases,
    complete_evidence,
    linked_parser,
    linked_score,
    validate_bundle,
)

CONTRACT = "field-record-v1"
FIELDS = ("value", "sign", "currency", "scale", "measure", "reporting_year",
          "issuer_binding", "metric_binding", "scope", "accounting_basis",
          "period_kind", "revision_status", "source_evidence")
CONTEXT_FIELDS = ("scope", "accounting_basis", "period_kind", "revision_status")
ARMS = ("linked_parser", "linked", "guarded_parser", "parser_first")


@dataclass(frozen=True)
class Decision:
    result: LinkedResult
    route: str
    model_required: bool


def _per_share_bundle(case: Case) -> EvidenceBundle | None:
    # This additional grammar is deliberately one whole source sentence, not token search.
    if not case.source or len(case.source) > 8192:
        return None
    entity = r"\s+".join(re.escape(part) for part in case.issuer.split())
    metric = r"\s+".join(re.escape(part) for part in case.metric.split())
    match = re.fullmatch(
        rf"(?P<entity>{entity}) reported (?P<metric>{metric}) of "
        rf"(?P<value>[+-]?\d+(?:\.\d+)?) (?P<unit>[A-Z]{{3}} per share) "
        rf"for (?P<period>{re.escape(case.requested_period)})\.", case.source, re.IGNORECASE)
    if match is None:
        return None
    return EvidenceBundle(
        "field-source-v1", hashlib.sha256(case.source.encode()).hexdigest(),
        case.issuer, case.metric, match["value"], normalize(match["unit"]),
        case.requested_period, "prose", "current",
        tuple(EvidenceSpan(role, *match.span(role))
              for role in ("entity", "metric", "value", "unit", "period")))


def validate_source(case: Case, bundle: EvidenceBundle) -> tuple[str, ...]:
    if bundle.contract == "linked-evidence-v1":
        return validate_bundle(case, bundle)
    if bundle.contract != "field-source-v1":
        return ("unknown_source_proof_contract",)
    return () if bundle == _per_share_bundle(case) else ("per_share_source_binding_mismatch",)


def _context(case: Case, bundle: EvidenceBundle) -> tuple[str, int]:
    metric = next(span for span in bundle.spans if span.role == "metric")
    left = case.source.rfind("\n", 0, metric.start)+1
    right = case.source.find("\n", metric.end)
    if right < 0:
        right = len(case.source)
    if bundle.method == "table":
        while left > 0:
            previous = case.source.rfind("\n", 0, left-1)+1
            if not case.source[previous:left].lstrip().startswith("|"):
                break
            left = previous
        entity = next(span for span in bundle.spans if span.role == "entity")
        return case.source[entity.end:left], entity.end
    return case.source[left:right], left


def context_fields(case: Case, bundle: EvidenceBundle) -> tuple[dict, tuple[EvidenceSpan, ...], tuple[str, ...]]:
    """Only explicit applicable captions or bound metric labels establish extra dimensions."""
    metric = next(span for span in bundle.spans if span.role == "metric")
    label = normalize(case.source[metric.start:metric.end])
    basis = "non-gaap" if re.search(r"\bnon-gaap\b", label) else (
        "gaap" if re.search(r"\bgaap\b", label) else None)
    scope = "consolidated" if re.search(r"\bconsolidated\b", label) else (
        "segment" if re.search(r"\bsegment\b", label) else None)
    values = {"scope": scope, "accounting_basis": basis, "period_kind": None,
              "revision_status": bundle.priority if bundle.priority != "current" else None}
    spans = [EvidenceSpan(name, metric.start, metric.end)
             for name in ("scope", "accounting_basis") if values[name] is not None]
    issues = []
    if metric.start and re.match(r"[\w-]", case.source[metric.start-1]):
        issues.append("metric_is_a_substring_of_another_definition")
    text, offset = _context(case, bundle)
    if re.search(r"\b(?:quarter(?:ly)?|year.to.date|ytd|(?:three|six|nine|3|6|9)\s+months)\b",
                 text, re.IGNORECASE):
        issues.append("subannual_period_not_supported_by_year_only_query")
    fiscal = list(re.finditer(
        rf"\bfiscal (?:year )?{re.escape(bundle.period)}\b", text, re.IGNORECASE))
    if fiscal:
        values["period_kind"] = "fiscal_year"
        spans.extend(EvidenceSpan("period_kind", offset+match.start(), offset+match.end())
                     for match in fiscal)
    for name, prefix in (("scope", "Scope"), ("accounting_basis", "Accounting basis"),
                         ("period_kind", "Reporting period")):
        declarations = list(re.finditer(
            rf"\b{prefix}:\s*(?P<value>[^\n.]+)", text, re.IGNORECASE))
        captured = []
        for match in declarations:
            value = normalize(match["value"])
            if name == "period_kind":
                period = re.fullmatch(r"(fiscal|calendar) year (\d{4})", value)
                if period is None or period[2] != bundle.period:
                    issues.append("period_declaration_incompatible_with_requested_year")
                    continue
                value = f"{period[1]}_year"
            elif name == "accounting_basis" and value not in ("gaap", "non-gaap"):
                issues.append("unsupported_accounting_basis_declaration")
                continue
            elif name == "scope" and value != "consolidated" and not re.fullmatch(
                    r"segment(?:: [a-z][a-z ]*)?", value):
                issues.append("unsupported_scope_declaration")
                continue
            captured.append(value)
            spans.append(EvidenceSpan(name, offset+match.start("value"), offset+match.end("value")))
        if len(set(captured)) > 1:
            issues.append(f"conflicting_{name}_declarations")
        elif captured:
            declared = captured[0]
            existing = values[name]
            compatible_segment = existing == "segment" and declared.startswith("segment")
            if existing is not None and existing != declared and not compatible_segment:
                issues.append(f"metric_caption_{name}_conflict")
            else:
                values[name] = declared
    return values, tuple(spans), tuple(sorted(set(issues)))


def _guard(case: Case, result: LinkedResult) -> LinkedResult:
    if result.bundle is None:
        return result
    errors = validate_source(case, result.bundle)
    if not errors:
        _, _, errors = context_fields(case, result.bundle)
    if errors:
        return LinkedResult(abstention("field_context_unavailable"), None, "context_rejected", errors)
    return result


def guarded_parser(case: Case) -> LinkedResult:
    result = linked_parser(case)
    if result.bundle is None:
        bundle = _per_share_bundle(case)
        if bundle is not None:
            answer = Answer(value=bundle.value, unit=bundle.unit, period=bundle.period,
                            evidence=case.source, abstain=False, reason="")
            result = LinkedResult(answer, bundle, "per_share_source_fact")
    return _guard(case, result)


def parser_first(case: Case, content: str | None = None) -> Decision:
    """Source result is a separate candidate, never a rewrite of the saved model response."""
    source = guarded_parser(case)
    if source.answer is not None and not source.answer.abstain:
        return Decision(source, "parser", False)
    if source.status == "context_rejected":
        return Decision(source, "source_refusal", False)
    if content is None:
        return Decision(source, "unresolved_requires_model_or_review", True)
    return Decision(_guard(case, complete_evidence(case, content)), "model_fallback", True)


def field_messages(case: Case) -> list[dict]:
    request = messages(case, "generate")
    payload = json.loads(request[1]["content"])
    payload["period_requirement"] = "annual reporting year; not a quarter or year-to-date substitute"
    request[1]["content"] = json.dumps(payload, sort_keys=True)
    return request


def _unit_fields(unit: str) -> dict:
    unit = normalize(unit)
    match = re.fullmatch(r"([a-z]{3}) (thousand|million|billion)s?", unit)
    if match:
        return {"currency": match[1].upper(), "scale": match[2], "measure": "currency"}
    per_share = re.fullmatch(r"([a-z]{3}) per share", unit)
    if per_share:
        return {"currency": per_share[1].upper(), "scale": "unit", "measure": "currency_per_share"}
    if unit in ("%", "percent"):
        return {"currency": None, "scale": None, "measure": "percent"}
    if unit == "subscribers":
        return {"currency": None, "scale": None, "measure": "subscribers"}
    return {"currency": None, "scale": None, "measure": "unsupported"}


def observed_fields(case: Case, result: LinkedResult) -> tuple[dict | None, tuple[EvidenceSpan, ...]]:
    answer = result.answer
    if answer is None or answer.abstain or answer.value is None:
        return None, ()
    number = Decimal(answer.value)
    fields = {
        "value": format(number, "f"), "sign": "zero" if number == 0 else (
            "negative" if number < 0 else "positive"),
        **_unit_fields(answer.unit), "reporting_year": answer.period,
        "issuer_binding": None, "metric_binding": None,
        **dict.fromkeys(CONTEXT_FIELDS), "source_evidence": False,
    }
    if result.bundle is None or validate_source(case, result.bundle):
        return fields, ()
    context, spans, issues = context_fields(case, result.bundle)
    identity = result.bundle
    tuple_matches = (number == Decimal(identity.value) and _unit_fields(answer.unit) == _unit_fields(
        identity.unit) and _unit_fields(identity.unit)["measure"] != "unsupported"
        and answer.period == identity.period)
    if not issues and tuple_matches:
        fields.update(context, issuer_binding=identity.issuer, metric_binding=identity.metric,
                      source_evidence=True)
    return fields, spans


def load_field_cases(payload: dict) -> tuple[Case, ...]:
    clean = {"pairs": [
        {**pair, "cases": [
            {key: value for key, value in row.items() if key != "expected_context"}
            for row in pair["cases"]]} for pair in payload["pairs"]]}
    cases = challenge_cases(clean)
    for row in (row for pair in payload["pairs"] for row in pair["cases"]):
        if set(row.get("expected_context", {})) != set(CONTEXT_FIELDS):
            raise ValueError("all context labels, including explicit unknowns, are required")
        if any(value is not None and not isinstance(value, str)
               for value in row["expected_context"].values()):
            raise ValueError("context labels must be strings or explicit unknowns")
        if row["expected"] is None and any(row["expected_context"].values()):
            raise ValueError("negative cases cannot carry a supported context record")
    return cases


def expected_fields(case: Case, context: dict) -> dict | None:
    if case.expected is None:
        return None
    number = Decimal(case.expected[0])
    return {
        "value": format(number, "f"), "sign": "zero" if number == 0 else (
            "negative" if number < 0 else "positive"),
        **_unit_fields(case.expected[1]), "reporting_year": case.expected[2],
        "issuer_binding": case.issuer, "metric_binding": case.metric,
        **context, "source_evidence": True,
    }


def field_states(fields: dict | None) -> dict[str, str]:
    if fields is None:
        return dict.fromkeys(FIELDS, "unanswered")
    return {
        name: "not_applicable" if name in ("currency", "scale") and fields["measure"] in (
            "percent", "subscribers") else "unknown" if fields[name] is None else "observed"
        for name in FIELDS
    }


def field_record(case: Case, result: LinkedResult, context: dict) -> dict:
    fields, spans = observed_fields(case, result)
    gold = expected_fields(case, context)
    per_field = {}
    for name in FIELDS:
        equal = fields is not None and gold is not None and fields[name] == gold[name]
        if name == "value" and fields is not None and gold is not None:
            equal = Decimal(fields[name]) == Decimal(gold[name])
        if name in (*CONTEXT_FIELDS, "issuer_binding", "metric_binding"):
            equal = equal and fields is not None and fields["source_evidence"]
        per_field[name] = None if gold is None else bool(equal)
    answered = result.answer is not None and not result.answer.abstain
    correct = (result.answer is not None and result.answer.abstain) if gold is None else all(
        per_field.values())
    outcome = ("invalid_response" if result.answer is None else "correct_answer" if correct and answered
               else "correct_abstention" if correct else "wrong_answer" if answered else "missed_answer")
    return {
        "answer": result.answer.model_dump() if result.answer is not None else None,
        "bundle": asdict(result.bundle) if result.bundle is not None else None,
        "context_spans": [asdict(span) for span in spans], "fields": fields,
        "field_states": field_states(fields),
        "score": {"correct": bool(correct), "answered": answered, "outcome": outcome},
        "field_correct": per_field, "status": result.status, "reasons": list(result.reasons),
        "legacy_linked_score": linked_score(case, result), "contract": CONTRACT,
    }


def contexts(payload: dict) -> dict[str, dict]:
    return {row["id"]: row["expected_context"] for pair in payload["pairs"] for row in pair["cases"]}


def summarize_fields(cases: tuple[Case, ...], records: dict[str, dict], labels: dict[str, dict]) -> dict:
    arms = {}
    positives = sum(case.expected is not None for case in cases)
    for arm in ARMS:
        pairs = [(case, records.get(case.id, {}).get(arm)) for case in cases]
        rows = [row for _, row in pairs if row is not None]
        answered = sum(row["score"]["answered"] for row in rows)
        correct_answers = sum(row["score"]["correct"] and row["score"]["answered"] for row in rows)
        arms[arm] = {
            "contract": CONTRACT, "planned": len(cases), "recorded": len(rows),
            "correct": sum(row["score"]["correct"] for row in rows), "answered": answered,
            "correct_answers": correct_answers, "wrong_answers": answered-correct_answers,
            "answer_precision": correct_answers/answered if answered else None,
            "answerable_coverage": correct_answers/positives if positives else None,
            "negative_correct": sum(row is not None and row["score"]["correct"]
                                    for case, row in pairs if case.expected is None),
            "outcomes": dict(Counter(row["score"]["outcome"] if row else "not_attempted"
                                     for _, row in pairs)),
            "fields": {name: {
                "correct": sum(row["field_correct"][name] is True for row in rows),
                "planned_answerable": positives,
                "known_value_planned": sum(
                    (gold := expected_fields(case, labels[case.id])) is not None and gold[name] is not None
                    for case in cases),
                "known_value_correct": sum(
                    row is not None and row["field_correct"][name] is True
                    and (gold := expected_fields(case, labels[case.id])) is not None and gold[name] is not None
                    for case, row in pairs),
            } for name in FIELDS},
            "selected_arm_seconds_excluding_unused_audit_generation_not_wall": sum(
                row.get("latency_seconds", 0) for row in rows),
        }
    route_counts = dict(Counter(records.get(case.id, {}).get("parser_first", {}).get("route", "not_attempted")
                               for case in cases))
    return {
        "contract": CONTRACT, "arms": arms, "routes": route_counts,
        "planned_positive": positives, "planned_negative": len(cases)-positives,
        "counterfactual_parser_first_model_calls": route_counts.get("model_fallback", 0),
        "paired_audit_calls_are_not_deployment_savings": True,
        "independent_gold": False, "promote": False,
        "scope": "Requested metric extraction; issuer, metric and year are supplied, not discovered.",
        "independent_review": {"status": "blocked_reviewers_unassigned", "gold_labels": 0,
                               "full_field_review_requires_additional_context_annotations": True},
    }
