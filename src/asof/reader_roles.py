"""Named arithmetic roles, checked against source cells before deterministic calculation."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from asof.reader_contract import Operand, Report, StrictModel, number, unit_dimension
from asof.reader_modes import AnsweredDimension, Mode
from asof.reader_presence import (
    NOT_PRESENT,
    Abstain,
    Lookup,
    MultiValue,
    PresenceOperand,
    Resolution,
    decline,
    mode_body,
    resolve_answer,
)

SYSTEM = (
    "Use only the supplied fictional source and selected mode. Row label and period "
    "must identify each role's actual source cell. Source rows[].values has period KEYS "
    "and cell-value VALUES. Copy row_label, period, unit and value literally. "
    "For difference and percent_change use start_value (FROM/earlier/reference) and "
    "end_value (TO/later/comparison). Code computes end-start; fractional change is "
    "(end-start)/abs(start), displayed as100times that fraction with percent scale. "
    "A fall from a positive start must be negative. For ratio, identify numerator and "
    "denominator exactly as requested: A divided by B has numerator A, denominator B. "
    "For average, provide the list values. Never calculate an answer yourself. "
    "NOT_PRESENT is available in every source field. Do not substitute nearby cells. "
    "If any requested component is missing, decline instead of mixing NOT_PRESENT "
    "with real values. Multi_value is a list of separate sourced values, never a sentence "
    "and never padding entries; include only requested cells. Code rejects mixed lists. "
    "Keep answer_dimension independent of the monetary banner; code derives scale and "
    "declines incompatible dimensions, missing roles, sentinel selections or zero denominators. "
    "Return only the selected mode-specific JSON, no extra fields or explanation."
)


class Change(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["difference", "percent_change"]
    start_value: PresenceOperand | None
    end_value: PresenceOperand | None
    answer_dimension: AnsweredDimension


class Ratio(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["ratio"]
    numerator: PresenceOperand | None
    denominator: PresenceOperand | None
    answer_dimension: AnsweredDimension


class Average(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["average"]
    values: list[PresenceOperand] = Field(max_length=6)
    answer_dimension: AnsweredDimension


Arithmetic = Annotated[Change | Ratio | Average, Field(discriminator="operation")]
ARITHMETIC = TypeAdapter(Arithmetic)
ADAPTER = TypeAdapter(Lookup | MultiValue | Change | Ratio | Average | Abstain)


def has_sentinel(operand: PresenceOperand) -> bool:
    return NOT_PRESENT in operand.model_dump().values()


def resolve_roles(
    answer: Lookup | MultiValue | Change | Ratio | Average | Abstain, report: Report,
) -> Resolution:
    if isinstance(answer, MultiValue):
        marked = [has_sentinel(o) for o in answer.values]
        if any(marked) and not all(marked):
            return decline("system", "mixed_NOT_PRESENT_values")
    if isinstance(answer, (Lookup, MultiValue, Abstain)):
        return resolve_answer(answer, report)
    if isinstance(answer, Change):
        selected = [answer.start_value, answer.end_value]
    elif isinstance(answer, Ratio):
        selected = [answer.numerator, answer.denominator]
    else:
        selected = answer.values
    if len(selected) < 2 or any(o is None for o in selected):
        return decline("system", "missing_named_roles")
    operands = [o for o in selected if o is not None]
    if any(has_sentinel(o) for o in operands):
        return decline("system", "NOT_PRESENT")
    source_operands = [Operand.model_validate(o.model_dump()) for o in operands]
    natural, _ = unit_dimension(source_operands[0].unit)
    checked = resolve_answer(MultiValue(
        mode="multi_value", values=operands, answer_dimension=natural,
    ), report)
    if checked.abstention_source:
        return checked
    if natural == "text":
        return decline("system", "incompatible_dimensions_or_units")
    try:
        values = [number(o.value) for o in operands]
    except ValueError:
        return decline("system", "missing_numeric_operands")
    dimension, scale = unit_dimension(source_operands[0].unit)
    with localcontext() as context:
        context.prec = 40
        if isinstance(answer, Change):
            start, end = values
            if answer.operation == "percent_change":
                if start == 0:
                    return decline("system", "zero_denominator")
                result, dimension, scale = 100 * (end - start) / abs(start), "percent", "percent"
            else:
                result = end - start
                if dimension == "percent":
                    dimension = "percentage_points"
        elif isinstance(answer, Ratio):
            numerator, denominator = values
            if denominator == 0:
                return decline("system", "zero_denominator")
            result, dimension, scale = numerator / denominator, "ratio", ""
        else:
            result = sum(values) / len(values)
        if answer.answer_dimension != dimension:
            return decline("system", "incompatible_answer_dimension")
        rendered = format(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
    return Resolution([rendered], scale, dimension, answer.operation, True)


def resolve_content(content: str, report: Report) -> tuple[Mode, Resolution]:
    answer = ADAPTER.validate_json(content)
    return answer.mode, resolve_roles(answer, report)


def answer_body(report: Report, mode: Mode, model: str, options: dict) -> dict:
    schema = (ARITHMETIC.json_schema() if mode == "arithmetic" else
              {"lookup": Lookup, "multi_value": MultiValue, "abstain": Abstain}[mode].model_json_schema())
    if "PresenceOperand" in schema.get("$defs", {}):
        props = schema["$defs"]["PresenceOperand"]["properties"]
        vocab = {
            "row_label": {r.label for r in report.rows},
            "period": {p for r in report.rows for p in r.values},
            "value": {v for r in report.rows for v in r.values.values()},
            "unit": {r.unit for r in report.rows},
        }
        for field, values in vocab.items():
            props[field]["enum"] = sorted(values | {NOT_PRESENT})
        dimensions = {unit_dimension(r.unit)[0] for r in report.rows}
        if mode == "arithmetic":
            dimensions |= {"percent", "ratio"}
            if any(r.unit == "percent" for r in report.rows):
                dimensions.add("percentage_points")
            for kind in ("Change", "Ratio", "Average"):
                schema["$defs"][kind]["properties"]["answer_dimension"]["enum"] = sorted(dimensions)
        elif mode != "abstain":
            schema["properties"]["answer_dimension"]["enum"] = sorted(dimensions)
        capacity = max(2, min(6, sum(len(r.values) for r in report.rows)))
        if mode == "multi_value":
            schema["properties"]["values"]["maxItems"] = capacity
        elif mode == "arithmetic":
            schema["$defs"]["Average"]["properties"]["values"]["maxItems"] = capacity
    body = mode_body(report, model, options)
    body["format"] = schema
    body["messages"][0]["content"] = SYSTEM + f" Selected mode={mode}. Exact schema: " + json.dumps(schema)
    return body
