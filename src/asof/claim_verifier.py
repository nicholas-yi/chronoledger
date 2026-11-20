"""Bounded source-proved claim decisions; raw model scores never substitute for missing proofs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from decimal import Decimal

from asof.extraction import normalize
from asof.focused_reader import Case
from asof.linked_reader import EvidenceBundle, EvidenceSpan, _amount
from asof.reader_fields import (
    _unit_fields,
    guarded_parser,
    source_admission_issues,
    validate_source,
)
from asof.reader_reliability import canonical_unit

UNIT = r"(?:[A-Z]{3}\s+(?:thousand|million|billion|per share)|percent|%|subscribers)"
NUMBER = r"[+-]?\d[\d,]*(?:\.\d+)?"


@dataclass(frozen=True)
class Claim:
    issuer: str
    metric: str
    value: str
    unit: str
    year: str
    corrected: bool


def parse_claim(text: str) -> Claim | None:
    if not text or len(text) > 1024:
        return None
    entity = r"(?P<issuer>[A-Za-z][A-Za-z0-9 ]{0,80}?)"
    metric = r"(?P<metric>[A-Za-z][A-Za-z -]{0,100}?)"
    amount = rf"(?:(?P<sign>negative|positive)\s+)?(?P<value>{NUMBER})\s+(?P<unit>{UNIT})"
    patterns = (
        (rf"{entity}'s\s+(?P<corrected_prefix>corrected\s+)?(?P<year>\d{{4}})\s+"
         rf"(?P<corrected>corrected\s+)?{metric}\s+was\s+{amount}\."),
        rf"{entity}\s+reported\s+{metric}\s+of\s+{amount}\s+for\s+(?P<year>\d{{4}})\.",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text, re.IGNORECASE)
        if match is None:
            continue
        value, _ = _amount(text, match["value"], table=False)
        if value is None:
            return None
        if match["sign"]:
            if match["value"].startswith(("+", "-")):
                return None
            value = format(Decimal(value).copy_negate() if match["sign"].lower() == "negative"
                           else Decimal(value), "f")
        unit = canonical_unit(match["unit"])
        if unit is None:
            return None
        return Claim(match["issuer"], match["metric"], value, unit, match["year"],
                     bool(match.groupdict().get("corrected") or match.groupdict().get("corrected_prefix")))
    return None


def _compound_fact(source: str, claim: Claim) -> EvidenceBundle | None:
    """Two complete compound disclosures; no arbitrary sentence slicing or inherited third parties."""
    issuer = r"\s+".join(re.escape(word) for word in claim.issuer.split())
    metric = r"[A-Za-z][A-Za-z -]{0,100}?"
    eps = r"(?:basic|diluted) earnings per share"
    patterns = (
        (rf"For\s+(?P<year>\d{{4}}),\s+(?P<entity>{issuer})\s+reported\s+"
         rf"(?P<metric1>{metric})\s+of\s+(?P<value1>{NUMBER})\s+(?P<unit1>{UNIT})\s+and\s+"
         rf"(?P<metric2>{metric})\s+of\s+(?P<value2>{NUMBER})\s+(?P<unit2>{UNIT})\."),
        (rf"(?P<entity>{issuer})\s+reported\s+(?P<metric1>{eps})\s+of\s+"
         rf"(?P<value1>{NUMBER})\s+(?P<unit1>[A-Z]{{3}} per share)\s+for\s+(?P<year>\d{{4}})\.\s+"
         rf"(?P<metric2>{eps})\s+was\s+(?P<value2>{NUMBER})\s+(?P<unit2>[A-Z]{{3}} per share)\."),
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, source, re.IGNORECASE)
        if match is None or match["year"] != claim.year:
            continue
        candidates = []
        for i in (1, 2):
            if normalize(match[f"metric{i}"]) != normalize(claim.metric):
                continue
            value, _ = _amount(source, match[f"value{i}"], table=False)
            unit = canonical_unit(match[f"unit{i}"])
            if value is None or unit is None:
                return None
            spans = tuple(EvidenceSpan(role, *match.span(group)) for role, group in (
                ("entity", "entity"), ("period", "year"), ("metric", f"metric{i}"),
                ("value", f"value{i}"), ("unit", f"unit{i}")))
            candidates.append(EvidenceBundle(
                "compound-claim-source-v1", hashlib.sha256(source.encode()).hexdigest(),
                claim.issuer, claim.metric, value, unit, claim.year,
                "bounded_compound_disclosure", "current", spans))
        if len({(Decimal(row.value), row.unit) for row in candidates}) == 1:
            return candidates[0]
    return None


def _compact_eps_fact(source: str, claim: Claim) -> EvidenceBundle | None:
    issuer = r"\s+".join(re.escape(word) for word in claim.issuer.split())
    cell1 = rf"(?P<metric1>EPS\((?P<kind1>basic|diluted)\))\s*=\s*(?P<currency1>[A-Z]{{3}})(?P<value1>{NUMBER})"
    cell2 = rf"(?P<metric2>EPS\((?P<kind2>basic|diluted)\))\s*=\s*(?P<currency2>[A-Z]{{3}})(?P<value2>{NUMBER})"
    match = re.fullmatch(
        rf"(?P<entity>{issuer}):\s*fiscal\s*(?P<year>\d{{4}})\s+{cell1};\s*{cell2}\.",
        source, re.IGNORECASE)
    if match is None or match["year"] != claim.year:
        return None
    candidates = []
    for i in (1, 2):
        if normalize(claim.metric) != f"{match[f'kind{i}'].lower()} earnings per share":
            continue
        value, _ = _amount(source, match[f"value{i}"], table=False)
        if value is None:
            return None
        spans = tuple(EvidenceSpan(role, *match.span(group)) for role, group in (
            ("entity", "entity"), ("period", "year"), ("metric", f"metric{i}"),
            ("measure_definition", f"metric{i}"), ("unit", f"currency{i}"), ("value", f"value{i}")))
        candidates.append(EvidenceBundle(
            "compact-eps-claim-v1", hashlib.sha256(source.encode()).hexdigest(),
            claim.issuer, claim.metric, value, f"{match[f'currency{i}'].lower()} per share",
            claim.year, "explicit_basic_diluted_eps_notation", "current", spans))
    identities = {(Decimal(row.value), row.unit) for row in candidates}
    return candidates[0] if len(identities) == 1 else None


def resolve_fact(source: str, claim: Claim) -> EvidenceBundle | None:
    if not source or len(source) > 8192:
        return None
    compound = _compound_fact(source, claim) or _compact_eps_fact(source, claim)
    if compound is not None:
        return None if source_admission_issues(source, compound.spans) else compound
    query = Case("claim-source", "evaluation", "claim", claim.issuer, claim.metric,
                 claim.year, source, None)
    parsed = guarded_parser(query)
    if parsed.bundle is not None and not validate_source(query, parsed.bundle):
        return parsed.bundle
    return None


def validate_fact(source: str, claim_text: str, fact: EvidenceBundle) -> bool:
    parsed = parse_claim(claim_text)
    return parsed is not None and fact == resolve_fact(source, parsed)


def _quantity_key(value: str, scale: str) -> tuple:
    """Exact decimal exponent shifts, independent of the ambient Decimal precision."""
    amount = Decimal(value)
    sign, digits, exponent = amount.as_tuple()
    if amount.is_zero():
        return 0, (0,), 0
    exponent += {"thousand": 3, "million": 6, "billion": 9}[scale]
    while digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    return sign, digits, exponent


def verify_claim(source: str, claim_text: str) -> dict:
    """Return supported/contradicted/review from source alone, never fixture truth or HHEM score."""
    claim = parse_claim(claim_text)
    result = {
        "contract": "source-claim-v2",
        "verdict": "review", "reason": "claim_outside_supported_grammar",
        "claim": asdict(claim) if claim else None, "source_fact": None,
        "mismatches": [], "proof_valid": False, "decision_origin": "source_rules_not_model",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "no_claim_is_not_a_supported_nondisclosure": True,
        "representation_equivalent": False,
        "claim_and_source_values_unchanged": True, "no_FX_conversion": True,
    }
    if claim is None:
        return result
    fact = resolve_fact(source, claim)
    if fact is None:
        result["reason"] = "no_unique_source_proof_requires_review"
        return result
    if claim.corrected and fact.priority != "correction":
        result["reason"] = "correction_status_unestablished_requires_review"
        return result
    mismatch = []
    if Decimal(claim.value) != Decimal(fact.value):
        mismatch.append("value")
    claim_unit, fact_unit = _unit_fields(claim.unit), _unit_fields(fact.unit)
    for dimension in ("currency", "scale", "measure"):
        if claim_unit[dimension] != fact_unit[dimension]:
            mismatch.append(dimension)
    equivalent = (
        bool(mismatch) and claim_unit["measure"] == fact_unit["measure"] == "currency"
        and claim_unit["currency"] == fact_unit["currency"]
        and _quantity_key(claim.value, claim_unit["scale"]) == _quantity_key(fact.value, fact_unit["scale"]))
    result.update(
        verdict="contradicted" if mismatch and not equivalent else "supported",
        reason="exact_same_currency_quantity_equivalence" if equivalent else
               "source_fact_differs" if mismatch else "exact_claim_matches_bound_source",
        mismatches=mismatch, source_fact=asdict(fact),
        proof_valid=validate_fact(source, claim_text, fact),
        representation_equivalent=equivalent,
        claim_and_source_values_unchanged=True, no_FX_conversion=True)
    if not result["proof_valid"]:
        result.update(verdict="review", reason="source_proof_revalidation_failed")
    return result


def summarize_structured(cases: tuple[dict, ...], raw_rows: list[dict]) -> dict:
    raw = {row["id"]: row for row in raw_rows}
    if len(raw) != len(raw_rows) or not set(raw) <= {case["id"] for case in cases}:
        raise ValueError("unexpected or duplicate structured-verifier case IDs")
    decisions = {case["id"]: verify_claim(case["source"], case["claim"]) for case in cases}
    return {
        "planned": len(cases), "resolved": sum(row["verdict"] != "review" for row in decisions.values()),
        "correct": sum(decisions[case["id"]]["verdict"] == (
            "supported" if case["expected_supported"] else "contradicted") for case in cases),
        "false_support": sum(decisions[case["id"]]["verdict"] == "supported"
                             and not case["expected_supported"] for case in cases),
        "false_rejection": sum(decisions[case["id"]]["verdict"] == "contradicted"
                               and case["expected_supported"] for case in cases),
        "requires_review": sum(row["verdict"] == "review" for row in decisions.values()),
        "model_increment_established": False, "model_weights_or_threshold_changed": False,
        "decisions": decisions, "raw_model_records": len(raw), "independent_gold": False,
        "scope": "A new source-rule verifier, not repaired raw HHEM predictions or a general financial judge.",
    }
