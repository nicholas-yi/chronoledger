"""Author-visible known-context coverage, not independently sampled financial gold."""

from __future__ import annotations

from collections import Counter

from asof.focused_reader import Case
from asof.reader_fields import (
    CONTEXT_FIELDS,
    expected_fields,
    field_record,
    guarded_parser,
    summarize_fields,
)

GROUPS = ("scope", "accounting_basis", "period_kind", "revision_status")


def build_coverage() -> tuple[tuple[Case, ...], dict[str, dict]]:
    cases, labels = [], {}
    for group in GROUPS:
        for i in range(24):
            year = str(2012+i % 7)
            issuer = f"FictionCoverage{group.replace('_', '').title()}{i:02d}"
            currency = ("USD", "EUR", "GBP")[i % 3]
            scale = ("thousand", "million", "billion")[(i//3) % 3]
            unit = f"{currency} {scale}"
            value = str(0 if i % 6 == 0 else -(i+7) if i % 3 == 0 else i+7)
            raw_value = f"({value[1:]})" if value.startswith("-") else value
            metric = "operating income" if group == "accounting_basis" else "revenue"
            context = dict.fromkeys(CONTEXT_FIELDS)
            prefix = f"Company: {issuer}. Amounts in {unit}."
            table = f"\n| Item | {year} |\n| {metric.title()} | {raw_value} |"
            negative = None
            if group == "scope":
                scope = "consolidated" if i % 2 == 0 else f"segment: {('north', 'south', 'east')[i % 3]}"
                positive = f"{prefix} Scope: {scope}."+table
                negative = f"{prefix} Scope: consolidated. Scope: segment: disputed."+table
                context[group] = scope
            elif group == "accounting_basis":
                basis = "GAAP" if i % 2 == 0 else "non-GAAP"
                positive = f"{prefix} Accounting basis: {basis}."+table
                negative = f"{prefix} Accounting basis: GAAP. Accounting basis: non-GAAP."+table
                context[group] = basis.lower()
            elif group == "period_kind":
                kind = "fiscal" if i % 2 == 0 else "calendar"
                positive = f"{prefix} Reporting period: {kind} year {year}."+table
                interval = ("three months", "six months", "nine months", "quarter")[i % 4]
                negative = f"{prefix} Reporting period: {interval} ended {year}."+table
                context[group] = f"{kind}_year"
            else:
                # Prose negatives require the existing explicit parentheses convention.
                sign_note = " Negative amounts are shown in parentheses." if value.startswith("-") else ""
                original = f"Original: {issuer} reported {metric} of {raw_value} {unit} for {year}."
                if i % 2 == 0:
                    positive = original+sign_note
                    context[group] = "original"
                else:
                    positive = (f"Original: {issuer} reported {metric} of {i+100} {unit} for {year}. "
                                f"Correction: {issuer} reported {metric} of {raw_value} {unit} for {year}. "
                                "This correction supersedes the original amount."+sign_note)
                    context[group] = "correction"
                negative = (f"{original} Correction: {issuer} reported {metric} of {i+100} "
                            f"{unit} for {year}. No supersession priority is supplied."+sign_note)
            for member, source in enumerate((positive, negative)):
                uid = f"COV-{group}-{i:02d}-{member}"
                cases.append(Case(uid, "evaluation", group, issuer, metric, year, source,
                                  (value, unit, year) if member == 0 else None))
                labels[uid] = context.copy() if member == 0 else dict.fromkeys(CONTEXT_FIELDS)
    return tuple(cases), labels


def evaluate_coverage() -> dict:
    cases, labels = build_coverage()
    records = {case.id: {"source_control": field_record(
        case, guarded_parser(case), labels[case.id])} for case in cases}
    expected = {case.id: expected_fields(case, labels[case.id]) for case in cases}
    actual = summarize_fields(cases, records, labels, arm_names=("source_control",))["arms"]["source_control"]
    known = {name: sum(row is not None and row[name] is not None for row in expected.values())
             for name in actual["fields"]}
    if any(known[group] < 24 for group in GROUPS):
        raise ValueError("coverage design lacks24known-valued cases per supported weakdimension")
    return {
        "status": "complete_deterministic_authored_coverage",
        "cases": len(cases), "positive_cases": 96, "negative_cases": 96,
        "known_targets": known, "summary": actual,
        "categories": dict(Counter(case.category for case in cases)),
        "failures": [{"case_id": case.id, "score": records[case.id]["source_control"]["score"],
                      "reasons": records[case.id]["source_control"]["reasons"]}
                     for case in cases if not records[case.id]["source_control"]["score"]["correct"]],
        "independent_gold": False, "model_calls": 0, "promote": False,
        "exposure": "All templates and labels author-visible;24variants per dimension are not24independentsemanticformats.",
        "not_supported": [
            "arbitrary quarter/YTD extraction", "exact start/end dates", "52/53-week calendars",
            "partial line-item restatement semantics", "independent entity/concept discovery",
            "unknown GAAP/IFRS reconciliation mappings", "real-financial-source accuracy"],
    }
