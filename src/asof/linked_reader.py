"""Versioned exact-offset evidence completion for a bounded prose/Markdown-table grammar.

Construction and validation share deterministic source rules, not independent human
adjudication. They use no gold, I/O, judge or model call. Scoring/replay is separate.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import pairwise

from pydantic import ValidationError

from asof.extraction import normalize
from asof.focused_reader import Answer, Case, abstention
from asof.verified_reader import WireFields, load_robustness_cases

UNIT = r"(?:[A-Z]{3}\s+(?:thousand|million|billion)s?|%|percent|subscribers)"
NUMBER = r"\(?[+-]?\d[\d,]*(?:\.\d+)?\)?"
HEADER = rf"(?P<year>(?:19|20)\d{{2}})(?:\s*\((?P<unit>{UNIT})\))?"
FLAGS = re.IGNORECASE


def _phrase(text: str) -> str:
    return r"\s+".join(re.escape(word) for word in text.split())


def _unit(text: str) -> str:
    text = normalize(text)
    if text == "percent":
        return "%"
    return re.sub(r"\b(thousand|million|billion)s\b", r"\1", text)


@dataclass(frozen=True)
class EvidenceSpan:
    role: str
    start: int
    end: int


@dataclass(frozen=True)
class EvidenceBundle:
    contract: str
    source_sha256: str
    issuer: str
    metric: str
    value: str
    unit: str
    period: str
    method: str
    priority: str
    spans: tuple[EvidenceSpan, ...]


@dataclass(frozen=True)
class LinkedResult:
    answer: Answer | None
    bundle: EvidenceBundle | None
    status: str
    reasons: tuple[str, ...] = ()


def _span(role: str, match: re.Match, group: str | int = 0, offset: int = 0) -> EvidenceSpan:
    left, right = match.span(group)
    return EvidenceSpan(role, left+offset, right+offset)


def _excluded(source: str) -> list[tuple[int, int]]:
    regions = []
    for match in re.finditer(
        r"(?:rejected\s+fictional\s+example|rejected\s+example|hypothetical\s+example)"
        r"[^'\"]{0,80}['\"](?P<quote>.*?)['\"]", source, FLAGS | re.DOTALL,
    ):
        regions.append(match.span("quote"))
    instruction = re.search(r"\bSYSTEM\s+OVERRIDE\s*:", source, FLAGS)
    if instruction:
        regions.append((instruction.start(), len(source)))
    return regions


def _amount(source: str, raw: str, *, table: bool) -> tuple[str | None, EvidenceSpan | None]:
    parenthesized = raw.startswith("(") and raw.endswith(")")
    excluded = _excluded(source)
    convention = next((match for match in re.finditer(
        r"parentheses\s+(?:denote|indicate|mean)\s+(?:a\s+)?negative"
        r"|negative\s+amounts\s+(?:are\s+)?shown\s+in\s+parentheses", source, FLAGS)
                       if not any(left <= match.start() < right for left, right in excluded)), None)
    if parenthesized and re.search(
            r"parentheses[^.]{0,100}(?:annotation|not\s+(?:a\s+)?(?:financial\s+)?sign"
            r"|not\s+negative)", source, FLAGS):
        return None, None
    if parenthesized and not table and convention is None:
        return None, None
    try:
        clean = raw.replace(",", "")
        inside = raw[1:-1] if parenthesized else raw
        if parenthesized and inside.startswith(("+", "-")):
            return None, None
        if "," in inside and re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", inside) is None:
            return None, None
        number = Decimal(clean[1:-1]).copy_negate() if parenthesized else Decimal(clean)
    except InvalidOperation:
        return None, None
    if not number.is_finite():
        return None, None
    return format(number, "f"), _span("sign_convention", convention) if convention else None


def _context(case: Case, prefix: str, offset: int = 0) -> dict[str, EvidenceSpan]:
    """Only explicit entity/topic headings establish inherited context."""
    issuer = _phrase(case.issuer)
    declarations = list(re.finditer(
        r"(?:reporting\s+company|company)\s*:\s*(?P<entity>[^\n.,]+)", prefix, FLAGS))
    entity = declarations[-1] if declarations else None
    if entity is not None and normalize(entity["entity"]) != normalize(case.issuer):
        return {}
    if entity is None:
        entity = re.search(rf"^(?P<entity>{issuer})(?!\w)\s*[:,]", prefix, FLAGS)
    result = {"entity": _span("entity", entity, "entity", offset)} if entity else {}
    years = list(re.finditer(r"\b(?:19|20)\d{2}\b", prefix))
    if years and len({m[0] for m in years}) == 1:
        result["period"] = _span("period", years[0], offset=offset)
    units = list(re.finditer(
        rf"(?:amounts?\s+(?:below\s+)?(?:are\s+)?in|default\s+units\s*:|units\s*:)"
        rf"\s*(?P<unit>{UNIT})", prefix, FLAGS))
    if units and len({_unit(m["unit"]) for m in units}) == 1:
        result["unit"] = _span("unit", units[0], "unit", offset)
    return result


def _bundle(
    case: Case, value: str, unit: str, period: str, method: str,
    spans: list[EvidenceSpan], priority: str = "current",
) -> EvidenceBundle:
    unique = tuple(sorted(set(spans), key=lambda span: (span.role, span.start, span.end)))
    return EvidenceBundle(
        "linked-evidence-v1", hashlib.sha256(case.source.encode()).hexdigest(),
        case.issuer, case.metric, value, _unit(unit), period, method, priority, unique)


def _prose(case: Case, excluded: list[tuple[int, int]]) -> list[EvidenceBundle]:
    source, metric = case.source, _phrase(case.metric)
    tail = (r"(?=\s*(?:,\s*not\s+(?:(?:the|a)\s+)?"
            r"(?:customer|supplier|competitor|counterparty)(?:'s)?\s+"
            r"(?:figure|amount|total|value))?[.!?]?\s*$)")
    patterns = (
        (rf"(?P<metric>{metric})(?:\s*\([^)]{{1,60}}\))?\s+of\s+"
         rf"(?P<value>{NUMBER})\s+(?P<unit>{UNIT})\s+for\s+(?P<year>\d{{4}}){tail}"),
        (rf"(?P<metric>{metric})\s+for\s+(?:fiscal\s+)?(?P<year>\d{{4}})\s+"
         rf"(?:was|were|:)\s*(?P<value>{NUMBER})\s+(?P<unit>{UNIT}){tail}"),
        (rf"(?P<metric>{metric})(?:\s*\([^)]{{1,60}}\))?\s*(?:was|were|:|of)\s*"
         rf"(?P<value>{NUMBER})\s+(?P<unit>{UNIT}){tail}"),
    )
    results = []
    # Clause boundaries preserve decimal points; semicolons start a new subject/scope clause.
    for clause in re.finditer(r".+?(?=(?:[.!?;]\s+(?=[A-Z'\"(]))|\n|\Z)",
                              source, re.DOTALL):
        text, base = clause[0], clause.start()
        if "|" in text:
            continue
        prefix_context = _context(case, source[:base])
        named = re.search(rf"(?<!\w)(?P<entity>{_phrase(case.issuer)})(?!\w)", text, FLAGS)
        first_person = re.search(r"(?:\bwe\b|\bour\s+own\s+reporting-company\b)", text, FLAGS)
        # A customer/segment mention does not inherit the issuer merely from a document heading.
        subject_named = named is not None and re.fullmatch(
            r"[.\s]*(?:(?:Original|Correction)\s*:\s*)?"
            r"(?:(?:For|In)\s+\d{4},?\s*)?", text[:named.start()], FLAGS) is not None
        topic_metric = re.match(rf"[.\s]*{metric}(?!\w)", text, FLAGS)
        if subject_named:
            entity_span = _span("entity", named, "entity", base)
        elif (first_person is not None or topic_metric is not None) and "entity" in prefix_context:
            entity_span = prefix_context["entity"]
        else:
            continue
        for pattern in patterns:
            for match in re.finditer(pattern, text, FLAGS):
                position = base+match.start()
                if any(left <= position < right for left, right in excluded):
                    continue
                if re.search(r"\b(?:did\s+not|never)\s+(?:report|disclose|state)\b",
                             text[:match.start()], FLAGS):
                    continue
                # Without an explicit name before the metric, require unambiguous first person.
                if subject_named and named.start() > match.start() and first_person is None:
                    continue
                if "year" in match.groupdict() and match["year"] is not None:
                    year, year_span = match["year"], _span("period", match, "year", base)
                else:
                    years = list(re.finditer(r"\b(?:19|20)\d{2}\b", text))
                    if len({m[0] for m in years}) != 1:
                        continue
                    year, year_span = years[0][0], _span("period", years[0], offset=base)
                if year != case.requested_period:
                    continue
                value, sign = _amount(source, match["value"], table=False)
                if value is None:
                    continue
                spans = [entity_span, _span("metric", match, "metric", base),
                         _span("value", match, "value", base), _span("unit", match, "unit", base),
                         year_span]
                if sign:
                    spans.append(sign)
                if normalize(case.metric).startswith("consolidated "):
                    spans.append(_span("scope", match, "metric", base))
                lead = text[:match.start()]
                priority = "correction" if re.search(r"\bCorrection\s*:", lead, FLAGS) else (
                    "original" if re.search(r"\bOriginal\s*:", lead, FLAGS) else "current")
                if priority != "current":
                    label = re.search(r"\b(?:Original|Correction)\s*:", lead, FLAGS)
                    spans.append(_span("status", label, offset=base))
                results.append(_bundle(case, value, match["unit"], year, "prose", spans, priority))
    return results


def _tables(case: Case, excluded: list[tuple[int, int]]) -> tuple[list[EvidenceBundle], list[str]]:
    source = case.source
    lines = list(re.finditer(r"[^\n]+", source))
    results, issues = [], []
    context: dict[str, EvidenceSpan] = {}
    header: list[tuple[str, int, int]] | None = None
    in_table = False
    for line in lines:
        if not line[0].lstrip().startswith("|"):
            in_table = False
            continue
        if any(left <= line.start() < right for left, right in excluded):
            continue
        if not in_table:
            context, header = _context(case, source[:line.start()]), None
            in_table = True
        cells = []
        bars = [m.start() for m in re.finditer(r"\|", line[0])]
        for left, right in pairwise(bars):
            raw = line[0][left+1:right]
            start = line.start()+left+1+len(raw)-len(raw.lstrip())
            text = raw.strip()
            cells.append((text, start, start+len(text)))
        if len(cells) < 2:
            continue
        if (normalize(cells[0][0]) in ("metric", "item", "year", "fiscal year", "")
                and any(re.fullmatch(HEADER, cell[0], FLAGS) for cell in cells[1:])):
            header = cells
            continue
        label = re.sub(r"\s*\([a-z]\)", "", cells[0][0], flags=FLAGS).strip()
        row_unit = re.search(rf"\(\s*(?P<unit>{UNIT})\s*\)", label, FLAGS)
        if row_unit:
            label = (label[:row_unit.start()]+label[row_unit.end():]).strip()
        if normalize(label) != normalize(case.metric):
            continue
        if "entity" not in context:
            issues.append("table_entity_context_unavailable")
            continue
        if header is not None:
            columns = [(i, match) for i, cell in enumerate(header)
                       if (match := re.fullmatch(HEADER, cell[0], FLAGS)) is not None
                       and match["year"] == case.requested_period]
            if len(columns) != 1 or columns[0][0] >= len(cells):
                issues.append("table_requested_year_column_unavailable")
                continue
            column, year_match = columns[0]
            period_span = _span("period", year_match, "year", header[column][1])
            header_unit = (_span("unit", year_match, "unit", header[column][1])
                           if year_match["unit"] is not None else None)
        elif len(cells) == 2 and "period" in context:
            column, period_span = 1, context["period"]
            header_unit = None
            if source[period_span.start:period_span.end] != case.requested_period:
                continue
        else:
            issues.append("table_period_context_unavailable")
            continue
        raw_value, start, end = cells[column]
        if raw_value in ("-", "\u2014", ""):
            continue
        value, sign = _amount(source, raw_value, table=True)
        if value is None:
            issues.append("unsupported_table_value")
            continue
        # Offsets for row units must refer to the unmodified label, not a stripped copy.
        original_row_unit = re.search(rf"\(\s*(?P<unit>{UNIT})\s*\)", cells[0][0], FLAGS)
        row_unit_span = (_span("unit", original_row_unit, "unit", cells[0][1])
                         if original_row_unit else None)
        if (row_unit_span is not None and header_unit is not None and _unit(source[
                row_unit_span.start:row_unit_span.end]) != _unit(source[header_unit.start:header_unit.end])):
            issues.append("row_column_unit_conflict")
            continue
        unit_span = row_unit_span or header_unit or context.get("unit")
        marker = re.search(r"\(([a-z])\)", cells[0][0], FLAGS)
        extras = []
        if marker:
            notes = list(re.finditer(
                rf"(?m)^\({re.escape(marker[1])}\)\s*(?P<note>[^\n]+)", source, FLAGS))
            notes = [match for match in notes
                     if not any(left <= match.start() < right for left, right in excluded)]
            if len(notes) != 1 or re.search(_phrase(case.metric), notes[0]["note"], FLAGS) is None:
                issues.append("footnote_row_binding_unavailable")
                continue
            units = list(re.finditer(UNIT, notes[0]["note"], FLAGS))
            # A note mentioning other unit defaults still needs an explicit target-metric override.
            override = re.search(
                rf"{_phrase(case.metric)}\s+(?:alone\s+|only\s+)?(?:is\s+)?"
                rf"(?:stated|presented|reported)\s+in\s+(?P<unit>{UNIT})", notes[0]["note"], FLAGS)
            if override is None or not units:
                issues.append("footnote_unit_override_unavailable")
                continue
            unit_span = _span("unit", override, "unit", notes[0].start("note"))
            if row_unit_span is not None and _unit(source[row_unit_span.start:row_unit_span.end]) != _unit(
                    source[unit_span.start:unit_span.end]):
                issues.append("row_footnote_unit_conflict")
                continue
            extras = [EvidenceSpan("footnote_reference", cells[0][1]+marker.start(),
                                   cells[0][1]+marker.end()), _span("unit_applicability", notes[0])]
        if unit_span is None:
            issues.append("table_unit_context_unavailable")
            continue
        spans = [context["entity"], period_span, unit_span,
                 EvidenceSpan("metric", cells[0][1], cells[0][2]),
                 EvidenceSpan("value", start, end), *extras]
        if normalize(case.metric).startswith("consolidated "):
            spans.append(EvidenceSpan("scope", cells[0][1], cells[0][2]))
        if sign:
            spans.append(sign)
        results.append(_bundle(case, value, source[unit_span.start:unit_span.end],
                               case.requested_period, "table", spans))
    return results, issues


def resolve(case: Case) -> tuple[EvidenceBundle | None, tuple[str, ...]]:
    """Resolve one compatible query fact; do not choose a convenient value from a conflict."""
    if not case.source or len(case.source) > 8192:
        return None, ("source_empty_or_outside_8192_character_contract",)
    excluded = _excluded(case.source)
    candidates = _prose(case, excluded)
    table_facts, issues = _tables(case, excluded)
    candidates.extend(table_facts)
    if issues:
        return None, tuple(sorted(set(issues)))
    correction = [fact for fact in candidates if fact.priority == "correction"]
    if correction:
        supersedes = next((match for match in re.finditer(
            r"\bsupersedes\s+(?:the\s+)?original\b", case.source, FLAGS)
                           if not any(left <= match.start() < right for left, right in excluded)), None)
        if supersedes is None or any(fact.priority == "current" for fact in candidates):
            return None, ("correction_priority_unqualified",)
        candidates = [
            EvidenceBundle(**{**fact.__dict__, "spans": (
                *fact.spans, _span("supersession", supersedes))}) for fact in correction]
    identities = {(Decimal(fact.value), fact.unit, fact.period) for fact in candidates}
    if len(identities) != 1:
        return None, ("no_unique_supported_query_fact",)
    return min(candidates, key=lambda fact: (len(fact.spans), str(fact.spans))), ()


def validate_bundle(case: Case, bundle: EvidenceBundle) -> tuple[str, ...]:
    """Exact source binding, not arbitrary co-occurring role tokens or independent adjudication."""
    if bundle.contract != "linked-evidence-v1":
        return ("unknown_evidence_contract",)
    if bundle.source_sha256 != hashlib.sha256(case.source.encode()).hexdigest():
        return ("source_hash_mismatch",)
    if (bundle.issuer, bundle.metric, bundle.period) != (
            case.issuer, case.metric, case.requested_period):
        return ("query_identity_mismatch",)
    if not {"value", "unit", "period", "entity", "metric"} <= {span.role for span in bundle.spans}:
        return ("missing_required_evidence_roles",)
    if any(type(span.start) is not int or type(span.end) is not int
           or not 0 <= span.start < span.end <= len(case.source) for span in bundle.spans):
        return ("invalid_source_offsets",)
    selected, issues = resolve(case)
    if selected is None or selected != bundle:
        return ("bundle_does_not_match_bound_source_relation", *issues)
    return ()


def linked_parser(case: Case) -> LinkedResult:
    bundle, issues = resolve(case)
    if bundle is None:
        return LinkedResult(abstention("linked_source_unavailable"), None, "unavailable", issues)
    value_span = next(span for span in bundle.spans if span.role == "value")
    answer = Answer(value=bundle.value, unit=bundle.unit, period=bundle.period,
                    evidence=case.source[value_span.start:value_span.end], abstain=False, reason="")
    return LinkedResult(answer, bundle, "linked_source_fact")


def complete_evidence(case: Case, content: str) -> LinkedResult:
    try:
        original = Answer.model_validate_json(content)
    except ValidationError:
        original = None
    if original is not None and original.abstain:
        return LinkedResult(original, None, "preserved_abstention")
    try:
        wire = WireFields.model_validate_json(content)
        Answer(**{**wire.model_dump(), "unit": wire.unit or "pending-source-binding"})
    except ValidationError:
        return LinkedResult(None, None, "invalid_response", ("not_a_valid_or_blank_unit_only_answer",))
    if not wire.evidence or normalize(wire.evidence) not in normalize(case.source):
        return LinkedResult(abstention("linked_quote_unsupported"), None, "rejected", ("quote_unsupported",))
    bundle, issues = resolve(case)
    if bundle is None:
        return LinkedResult(abstention("linked_source_unavailable"), None, "unavailable", issues)
    if (wire.value is None or Decimal(wire.value) != Decimal(bundle.value)
            or wire.period != bundle.period or (wire.unit and _unit(wire.unit) != bundle.unit)):
        return LinkedResult(abstention("linked_explicit_tuple_mismatch"), None, "rejected",
                            ("explicit_tuple_not_repaired",))
    quote = normalize(wire.evidence)
    if not any(normalize(case.source[span.start:span.end]) in quote for span in bundle.spans):
        return LinkedResult(abstention("linked_quote_not_a_seed"), None, "rejected",
                            ("quote_has_no_linked_evidence_component",))
    answer = Answer(**{**wire.model_dump(), "unit": wire.unit or bundle.unit})
    return LinkedResult(answer, bundle, "completed_blank_unit" if not wire.unit else "completed_evidence")


def linked_score(case: Case, result: LinkedResult) -> dict:
    answer = result.answer
    if answer is None:
        return {"correct": False, "outcome": "invalid_response", "answered": False}
    if answer.abstain:
        correct = case.expected is None
        return {"correct": correct, "outcome": "correct_abstention" if correct else "missed_answer",
                "answered": False}
    if answer.value is None:
        return {"correct": False, "outcome": "invalid_response", "answered": False}
    errors = ("missing_bundle",) if result.bundle is None else validate_bundle(case, result.bundle)
    if result.bundle is not None and (Decimal(answer.value) != Decimal(result.bundle.value)
                                     or _unit(answer.unit) != result.bundle.unit
                                     or answer.period != result.bundle.period):
        errors = (*errors, "answer_bundle_mismatch")
    expected = case.expected
    correct = (expected is not None and Decimal(answer.value) == Decimal(expected[0])
               and _unit(answer.unit) == _unit(expected[1]) and answer.period == expected[2]
               and not errors)
    return {"correct": correct, "outcome": "correct_answer" if correct else "wrong_answer",
            "answered": True, "bundle_errors": list(errors)}


def challenge_cases(payload: dict) -> tuple[Case, ...]:
    return load_robustness_cases(payload)
