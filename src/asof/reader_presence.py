"""Explicit missing-source selections and auditable model/system abstentions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from asof.reader_contract import (
    ContractAnswer,
    Dimension,
    Operand,
    Report,
    Scale,
    StrictModel,
    Unit,
    number,
    resolve,
    unit_dimension,
)
from asof.reader_modes import AnsweredDimension, Mode, ModeChoice

NOT_PRESENT = "NOT_PRESENT"
MODE_SYSTEM = (
    "Choose mode from this fictional source. Check whether the requested row and period "
    "exist BEFORE choosing. Never substitute a nearby row/period. If a requested fact is "
    "missing, units incompatible or denominator zero, choose abstain. Otherwise choose "
    "lookup for one existing cell, multi_value for listing several existing cells, arithmetic "
    "for a calculation from two cells. Return only {\"mode\":\"...\"}."
)
SYSTEM = (
    "Use only the supplied fictional source and the selected mode. Copy operands with "
    "row_label, period, unit and value as written. Source rows[].values has period KEYS "
    "and cell-value VALUES. NOT_PRESENT is an allowed option in every source field: use "
    "it for a missing requested label, period or fact. Never replace a missing request "
    "with the nearest existing cell. Code will explicitly decline missing selections. "
    "For arithmetic, supply operands and operation, never a computed answer. "
    "difference=first-second; percent_change=100*(first-second)/second with first=TO/new "
    "and second=FROM/old (a fall gives a negative result); average=(first+second)/2; "
    "ratio=first/second. Keep the requested direction. "
    "answer_dimension is separate from the table banner: money/count/years/percent/"
    "percentage_points/ratio/text. Code derives answer scale from source unit+operation. "
    "Like-unit division is ratio; percent change is percent. "
    "Return only the selected mode's JSON. No extra fields or explanation."
)


class PresenceOperand(StrictModel):
    row_label: str
    period: str
    unit: Unit | Literal["NOT_PRESENT"]
    value: str


class Lookup(StrictModel):
    mode: Literal["lookup"]
    operand: PresenceOperand | None
    answer_dimension: AnsweredDimension


class MultiValue(StrictModel):
    mode: Literal["multi_value"]
    values: list[PresenceOperand] = Field(max_length=6)
    answer_dimension: AnsweredDimension


class Arithmetic(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["difference", "percent_change", "average", "ratio"]
    operands: list[PresenceOperand] = Field(max_length=2)
    answer_dimension: AnsweredDimension


class Abstain(StrictModel):
    mode: Literal["abstain"]


Answer = Annotated[Lookup | MultiValue | Arithmetic | Abstain, Field(discriminator="mode")]
ADAPTER = TypeAdapter(Answer)


@dataclass(frozen=True)
class Resolution:
    values: list[str]
    scale: Scale
    dimension: Dimension
    operation: str
    computed_by_code: bool
    abstention_source: Literal["model", "system"] | None = None
    decline_reason: str | None = None


def decline(source: Literal["model", "system"], reason: str) -> Resolution:
    return Resolution([], "", "none", "abstain", False, source, reason)


def resolve_answer(answer: Answer, report: Report) -> Resolution:
    if isinstance(answer, Abstain):
        return decline("model", "explicit_model_abstention")
    if isinstance(answer, Lookup):
        selected = [] if answer.operand is None else [answer.operand]
        operation = "lookup"
    elif isinstance(answer, MultiValue):
        selected, operation = answer.values, "lookup"
    else:
        selected, operation = answer.operands, answer.operation
    required = 2 if isinstance(answer, (Arithmetic, MultiValue)) else 1
    if len(selected) < required:
        return decline("system", "missing_operands")
    if any(NOT_PRESENT in o.model_dump().values() for o in selected):
        return decline("system", "NOT_PRESENT")
    operands = [Operand.model_validate(o.model_dump()) for o in selected]
    units = {o.unit for o in operands}
    if len(units) != 1:
        return decline("system", "incompatible_dimensions_or_units")
    dimension, scale = unit_dimension(operands[0].unit)
    if isinstance(answer, Arithmetic):
        if dimension == "text":
            return decline("system", "incompatible_dimensions_or_units")
        try:
            numbers = [number(o.value) for o in operands]
        except ValueError:
            return decline("system", "missing_numeric_operands")
        if operation in ("ratio", "percent_change") and numbers[1] == 0:
            return decline("system", "zero_denominator")
        if operation == "percent_change":
            dimension, scale = "percent", "percent"
        elif operation == "ratio":
            dimension, scale = "ratio", ""
        elif operation == "difference" and dimension == "percent":
            dimension = "percentage_points"
    if answer.answer_dimension != dimension:
        return decline("system", "incompatible_answer_dimension")
    contract = ContractAnswer(
        values=[o.value for o in operands] if operation == "lookup" else [],
        operation=operation, operands=operands, answer_dimension=dimension, answer_scale=scale,
    )
    values, computed = resolve(contract, report)
    return Resolution(values, scale, dimension, operation, computed)


def mode_body(report: Report, model: str, options: dict) -> dict:
    return {"model": model, "stream": False, "think": False, "keep_alive": "5m",
            "options": options, "format": ModeChoice.model_json_schema(),
            "messages": [{"role": "system", "content": MODE_SYSTEM},
                         {"role": "user", "content": report.model_dump_json()}]}


def answer_body(report: Report, mode: Mode, model: str, options: dict) -> dict:
    schema = {"lookup": Lookup, "multi_value": MultiValue,
              "arithmetic": Arithmetic, "abstain": Abstain}[mode].model_json_schema()
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
        if dimensions:
            schema["properties"]["answer_dimension"]["enum"] = sorted(dimensions)
    body = mode_body(report, model, options)
    body["format"] = schema
    body["messages"][0]["content"] = (
        SYSTEM + f" Selected mode={mode}. Exact schema: " + json.dumps(schema))
    return body
