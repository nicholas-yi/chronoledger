"""Frozen symbolic table baseline; no learned parameters, gold fields or external access."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

STOPWORDS = frozenset(
    ["what", "is", "are", "was", "were", "the", "a", "an", "of", "for", "in", "from", "to", "and", "or", "how", "much", "many", "did", "does", "do", "by", "at", "as", "on", "year", "years", "ended", "amount"])
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
SCALE = re.compile(r"\b(thousand|million|billion)s?\b", re.IGNORECASE)


@dataclass(frozen=True)
class TableInput:
    question: str
    table: tuple[tuple[str, ...], ...]
    paragraphs: tuple[str, ...]


@dataclass(frozen=True)
class BaselineAnswer:
    answer: str | None
    scale: str
    reason: str


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower())) - STOPWORDS


def _cell(text: str) -> tuple[float, str] | None:
    clean = text.strip().replace(",", "").replace("$", "").strip()
    scale = ""
    inline = SCALE.search(clean)
    if inline:
        scale = inline.group(1).lower()
        clean = SCALE.sub("", clean).strip()
    if clean.endswith("%"):
        if scale:
            return None
        scale, clean = "percent", clean[:-1].strip()
    negative = clean.startswith("(") and clean.endswith(")")
    if negative:
        clean = clean[1:-1].strip()
    if NUMBER.fullmatch(clean) is None:
        return None
    value = float(clean) * (-1 if negative else 1)
    return (value, scale) if math.isfinite(value) else None


def predict_table(item: TableInput) -> BaselineAnswer:
    """Unique row token overlap + unique requested year columns; simple symbolic operators.

    Unsupported text/multi-row relations, tied mappings, units and zero denominators
    abstain with reasons. Unmarked scale emits blank; that is a baseline assumption
    whose errors are measured, not a claim of source correctness.
    """
    if (not isinstance(item.question, str) or not item.question.strip()
            or any(not isinstance(cell, str) for row in item.table for cell in row)
            or any(not isinstance(p, str) for p in item.paragraphs)):
        raise ValueError("table baseline needs string question/cells/paragraphs")
    question = item.question.lower()
    years = sorted(set(YEAR.findall(question)))
    if not 1 <= len(years) <= 2:
        return BaselineAnswer(None, "", "requires_one_or_two_explicit_years")
    keywords = _tokens(question)
    ranked = [(len(keywords & _tokens(row[0])), row)
              for row in item.table if len(row) > 1 and _cell(row[0]) is None]
    if not ranked or max(score for score, _ in ranked) == 0:
        return BaselineAnswer(None, "", "no_supported_table_row")
    best = max(score for score, _ in ranked)
    rows = [row for score, row in ranked if score == best]
    if len(rows) != 1:
        return BaselineAnswer(None, "", "ambiguous_row_mapping")
    row = rows[0]
    columns = {}
    for year in years:
        possible = {i for header in item.table[:3] for i, text in enumerate(header)
                    if i > 0 and year in YEAR.findall(text)}
        if len(possible) != 1:
            return BaselineAnswer(None, "", "ambiguous_or_missing_year_column")
        index = possible.pop()
        if index >= len(row):
            return BaselineAnswer(None, "", "missing_table_cell")
        parsed = _cell(row[index])
        if parsed is None:
            return BaselineAnswer(None, "", "unsupported_numeric_cell")
        columns[year] = parsed
    inline_scales = {scale for _, scale in columns.values() if scale}
    context = " ".join([" ".join(r) for r in item.table[:3]] + list(item.paragraphs))
    context_scales = {s.lower() for s in SCALE.findall(context)}
    if len(inline_scales) > 1:
        return BaselineAnswer(None, "", "mixed_inline_units")
    if re.search(r"\bper\s+(?:common\s+)?share\b", question):
        scale = ""
    elif inline_scales:
        scale = next(iter(inline_scales))
    elif len(context_scales) > 1:
        return BaselineAnswer(None, "", "ambiguous_context_units")
    else:
        scale = next(iter(context_scales), "")
    if len(years) == 1:
        if any(term in question for term in ("change", "difference", "average", "sum")):
            return BaselineAnswer(None, "", "arithmetic_requires_two_years")
        if ("percent" in question or "ratio" in question) and scale != "percent":
            return BaselineAnswer(None, "", "requires_multi_row_ratio")
        value, reason = columns[years[0]][0], "unique_row_year_lookup"
    else:
        old, new = (columns[year][0] for year in years)
        direction = re.search(r"from\s+((?:19|20)\d{2})\s+to\s+((?:19|20)\d{2})", question)
        if direction:
            old, new = (columns[y][0] for y in direction.groups())
        if "average" in question:
            if re.search(r"\brespectively\b|\bweighted[\s-]+average\b", question):
                return BaselineAnswer(None, "", "average_metric_or_ordered_lookup")
            range_query = re.search(
                r"\b(?:between|from)\s+(?:the\s+years?\s+)?((?:19|20)\d{2})"
                r"\s*(?:-|to|and|\u2013|\u2014)\s*((?:19|20)\d{2})", question)
            if range_query is None:
                range_query = re.search(
                    r"\b((?:19|20)\d{2})\s*[-\u2013\u2014]\s*((?:19|20)\d{2})\b", question)
            average_years = years
            if range_query:
                first, last = sorted(int(y) for y in range_query.groups())
                average_years = [str(y) for y in range(first, last + 1)]
            average_values = []
            average_scales = set()
            for year in average_years:
                possible = {i for header in item.table[:3] for i, text in enumerate(header)
                            if i > 0 and year in YEAR.findall(text)}
                if len(possible) != 1:
                    return BaselineAnswer(None, "", "average_range_year_not_observed")
                index = possible.pop()
                parsed = _cell(row[index]) if index < len(row) else None
                if parsed is None:
                    return BaselineAnswer(None, "", "average_range_value_unavailable")
                average_values.append(parsed[0])
                if parsed[1]:
                    average_scales.add(parsed[1])
            if len(average_scales) > 1:
                return BaselineAnswer(None, "", "average_mixed_inline_units")
            prefix = " ".join(" ".join(r) for r in item.table[:item.table.index(row)])
            banners = set(re.findall(r"\bin\s+(thousand|million|billion)s?\b", prefix.lower()))
            if not re.search(r"\bper\s+(?:common\s+)?share\b", question):
                if len(banners) > 1:
                    return BaselineAnswer(None, "", "average_unit_evidence_conflict")
                if not average_scales and banners:
                    scale = next(iter(banners))
            if any(v < 0 for v in average_values) and re.search(
                r"\b(?:expense|expenses|cost|costs)\b", question
            ):
                if re.search(r"\b(?:absolute|magnitude)\b", question):
                    average_values = [abs(v) for v in average_values]
                elif not re.search(r"\b(?:signed|net)\b", question):
                    return BaselineAnswer(None, "", "average_expense_sign_ambiguous")
            value = sum(average_values) / len(average_values)
            reason = "year_range_average" if range_query else "two_year_average"
        elif "sum" in question:
            value, reason = old + new, "two_year_sum"
        elif "change" in question or "difference" in question:
            if "percent" in question:
                if old == 0:
                    return BaselineAnswer(None, "", "zero_percentage_denominator")
                value, scale, reason = (new - old) / old * 100, "percent", "percentage_change"
            else:
                value, reason = new - old, "two_year_difference"
        else:
            return BaselineAnswer(None, "", "unsupported_two_year_operation")
    if not math.isfinite(value):
        return BaselineAnswer(None, "", "nonfinite_arithmetic")
    return BaselineAnswer(format(value, ".10g"), scale, reason)
