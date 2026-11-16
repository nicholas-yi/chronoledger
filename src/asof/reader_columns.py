"""Generic source column labels and independently verified paragraph spans."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from asof import reader_roles as roles
from asof.reader_contract import Report, StrictModel, unit_dimension
from asof.reader_modes import AnsweredDimension
from asof.reader_presence import NOT_PRESENT, Abstain, PresenceOperand, Resolution, decline

Mode = Literal["lookup", "multi_value", "arithmetic", "text_span", "abstain"]


class ColumnReport(Report):
    paragraphs: list[str] = Field(default_factory=list)


class ModeChoice(StrictModel):
    mode: Mode


class ColumnOperand(PresenceOperand):
    period: str = Field(alias="column_label")


class Lookup(StrictModel):
    mode: Literal["lookup"]
    operand: ColumnOperand | None
    answer_dimension: AnsweredDimension


class MultiValue(StrictModel):
    mode: Literal["multi_value"]
    values: list[ColumnOperand] = Field(max_length=6)
    answer_dimension: AnsweredDimension


class Change(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["difference", "percent_change"]
    start_value: ColumnOperand | None
    end_value: ColumnOperand | None
    answer_dimension: AnsweredDimension


class Ratio(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["ratio"]
    numerator: ColumnOperand | None
    denominator: ColumnOperand | None
    answer_dimension: AnsweredDimension


class Average(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["average"]
    values: list[ColumnOperand] = Field(max_length=6)
    answer_dimension: AnsweredDimension


class Span(StrictModel):
    paragraph_id: int | Literal["NOT_PRESENT"]
    span: str = Field(min_length=1, max_length=1000)


class TextSpan(StrictModel):
    mode: Literal["text_span"]
    spans: list[Span] = Field(max_length=6)
    answer_dimension: Literal["text"]


ARITHMETIC = TypeAdapter(Annotated[Change | Ratio | Average, Field(discriminator="operation")])
ADAPTER = TypeAdapter(Lookup | MultiValue | Change | Ratio | Average | TextSpan | Abstain)

MODE_SYSTEM = (
    "Choose mode from the supplied source. A column label locates a cell and may be a region, "
    "segment, product or year, not necessarily a date. Never replace a missing requested label "
    "with another column or row. Choose lookup for one table cell, multi_value for several "
    "table cells, arithmetic for a calculation, text_span for words stated in the supplied "
    "paragraphs, abstain for a missing fact or undefined division. Return only mode JSON."
)
SYSTEM = (
    "Use only the supplied source. For table operands copy row_label and column_label "
    "literally. The KEYS in each row's values dictionary are actual column labels, including "
    "non-year names such as regions, segments and products; the VALUES are cell contents. "
    "There is no period field. Never mark a present column missing just because it is not "
    "a date. NOT_PRESENT is only for a genuinely absent requested source field. "
    "For difference/percent_change, start_value is the FROM/reference column and end_value "
    "the TO/comparison column; column labels locate cells, named roles define direction. "
    "Code computes end-start and100*(end-start)/abs(start). Ratio uses numerator/denominator; "
    "average uses values. Never compute the result yourself. "
    "Multi_value lists contain separate requested table values, no padding and no mixing "
    "NOT_PRESENT with present cells. Code declines any sentinel or incompatible dimension. "
    "For text_span, quote only the requested words verbatim from supplied paragraphs and "
    "give their zero-based paragraph_id. No table metadata is needed for spans. Code checks "
    "each span is a nonempty exact substring of its cited paragraph. "
    "Keep answer_dimension separate from a monetary banner; code derives scale. "
    "Return only the selected mode-specific JSON, no extra fields or explanation."
)
TABLE_GUIDANCE = (
    "Copy table cells, not guessed metadata. A source row "
    '{"label":"<row>","unit":"<unit>","values":{"<column>":"<cell>"}} '
    "maps to an operand "
    '{"row_label":"<row>","column_label":"<column>","unit":"<unit>","value":"<cell>"}. '
    "The column label is a literal dictionary KEY, not a date requirement. Regions, "
    "segments, products and years all work. If the requested cell exists, its row label, "
    "column key and unit are explicitly supplied: copy them, do not mark them NOT_PRESENT. "
    "Use NOT_PRESENT only for an actually absent requested fact. "
    "Set answer_dimension from the source unit, not a monetary banner on unrelated rows. "
)


def _legacy(value: ColumnOperand | None) -> PresenceOperand | None:
    if value is None:
        return None
    return PresenceOperand(row_label=value.row_label, period=value.period,
                           unit=value.unit, value=value.value)


def resolve_content(content: str, report: ColumnReport) -> tuple[Mode, Resolution]:
    answer = ADAPTER.validate_json(content)
    if isinstance(answer, TextSpan):
        if not answer.spans:
            return answer.mode, decline("system", "missing_text_spans")
        for ref in answer.spans:
            if ref.paragraph_id == NOT_PRESENT or ref.span == NOT_PRESENT:
                return answer.mode, decline("system", "NOT_PRESENT")
            if not isinstance(ref.paragraph_id, int) or not 0 <= ref.paragraph_id < len(report.paragraphs):
                return answer.mode, decline("system", "missing_paragraph")
            if not ref.span.strip() or ref.span not in report.paragraphs[ref.paragraph_id]:
                return answer.mode, decline("system", "span_not_in_source")
        return answer.mode, Resolution([s.span for s in answer.spans], "", "text", "lookup", False)
    if isinstance(answer, Abstain):
        converted = answer
    elif isinstance(answer, Lookup):
        converted = roles.Lookup(mode="lookup", operand=_legacy(answer.operand),
                                 answer_dimension=answer.answer_dimension)
    elif isinstance(answer, MultiValue):
        converted = roles.MultiValue(mode="multi_value", values=[
            PresenceOperand.model_validate(v.model_dump()) for v in answer.values],
            answer_dimension=answer.answer_dimension)
    elif isinstance(answer, Change):
        converted = roles.Change(mode="arithmetic", operation=answer.operation,
            start_value=_legacy(answer.start_value), end_value=_legacy(answer.end_value),
            answer_dimension=answer.answer_dimension)
    elif isinstance(answer, Ratio):
        converted = roles.Ratio(mode="arithmetic", operation="ratio",
            numerator=_legacy(answer.numerator), denominator=_legacy(answer.denominator),
            answer_dimension=answer.answer_dimension)
    else:
        converted = roles.Average(mode="arithmetic", operation="average", values=[
            PresenceOperand.model_validate(v.model_dump()) for v in answer.values],
            answer_dimension=answer.answer_dimension)
    return answer.mode, roles.resolve_roles(converted, report)


def mode_body(report: ColumnReport, model: str, options: dict) -> dict:
    return {"model": model, "stream": False, "think": False, "keep_alive": "5m",
        "options": options, "format": ModeChoice.model_json_schema(),
        "messages": [{"role": "system", "content": MODE_SYSTEM},
                     {"role": "user", "content": report.model_dump_json()}]}


def answer_body(report: ColumnReport, mode: Mode, model: str, options: dict) -> dict:
    schema = (ARITHMETIC.json_schema() if mode == "arithmetic" else {
        "lookup": Lookup, "multi_value": MultiValue, "text_span": TextSpan,
        "abstain": Abstain}[mode].model_json_schema())
    if "ColumnOperand" in schema.get("$defs", {}):
        props = schema["$defs"]["ColumnOperand"]["properties"]
        vocab = {
            "row_label": {r.label for r in report.rows},
            "column_label": {c for r in report.rows for c in r.values},
            "value": {v for r in report.rows for v in r.values.values()},
            "unit": {r.unit for r in report.rows},
        }
        for field, values in vocab.items():
            props[field]["enum"] = sorted(values | {NOT_PRESENT})
        for field, description in {
            "row_label": "Copy source row.label exactly.",
            "column_label": "Copy the matching source row.values dictionary KEY exactly.",
            "value": "Copy that row.values[column_label] cell string exactly.",
            "unit": "Copy that source row.unit exactly.",
        }.items():
            props[field]["description"] = description
        dimensions = {unit_dimension(r.unit)[0] for r in report.rows}
        if mode == "arithmetic":
            dimensions |= {"percent", "ratio"}
            if any(r.unit == "percent" for r in report.rows):
                dimensions.add("percentage_points")
            for name in ("Change", "Ratio", "Average"):
                schema["$defs"][name]["properties"]["answer_dimension"]["enum"] = sorted(dimensions)
        else:
            schema["properties"]["answer_dimension"]["enum"] = sorted(dimensions)
        capacity = max(2, min(6, sum(len(r.values) for r in report.rows)))
        if mode == "multi_value":
            schema["properties"]["values"]["maxItems"] = capacity
        elif mode == "arithmetic":
            schema["$defs"]["Average"]["properties"]["values"]["maxItems"] = capacity
    if mode == "text_span":
        schema["$defs"]["Span"]["properties"]["paragraph_id"]["enum"] = [
            *range(len(report.paragraphs)), NOT_PRESENT]
    body = mode_body(report, model, options)
    body["format"] = schema
    if mode in ("lookup", "multi_value"):
        instruction = TABLE_GUIDANCE + (
            "Return one operand for the requested cell." if mode == "lookup" else
            "Return one operand per requested cell in values, each separately. "
            "No padding entries and no mixing NOT_PRESENT with real cells; code declines such lists.")
    elif mode == "text_span":
        instruction = (
            "Copy only the requested words VERBATIM from supplied paragraphs. Return spans "
            "with zero-based paragraph_id; no row or column fields. Code checks exact substring "
            "membership. Use NOT_PRESENT only when the requested fact is absent. "
            "Return separate spans, not an explanatory sentence.")
    else:
        instruction = SYSTEM
    body["messages"][0]["content"] = (
        instruction + f" Selected mode={mode}. Return only JSON. Exact schema: " + json.dumps(schema))
    return body
