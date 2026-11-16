"""Mode-discriminated reader interface, adapted to the existing checked calculator."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from asof.reader_contract import (
    ContractAnswer,
    Operand,
    Report,
    StrictModel,
    resolve,
    unit_dimension,
)

AnsweredDimension = Literal[
    "money", "count", "years", "percent", "percentage_points", "ratio", "text",
]

SYSTEM = (
    "Read only this fictional report. Pick mode FIRST. "
    "For one source value use lookup with one operand; for several requested values use "
    "multi_value with a list of sourced values, one object per separate cell. Copy row_label, "
    "period, value and unit exactly from each selected cell and its row metadata. "
    "For arithmetic, provide exactly two source operands plus operation; do NOT supply a result. "
    "Code computes: difference=first-second; percent_change=100*(first-second)/second "
    "(first=new, second=old); average=(first+second)/2; ratio=first/second. "
    "Use the requested row and periods, not a header or another row. "
    "Choose answer_dimension independently of the monetary banner: count, years and ratio "
    "are not money. Do not output an answer_scale field: code derives scale from the "
    "source unit and selected operation. Like-unit division gives ratio; "
    "percent change gives percent; difference of percent-valued cells gives percentage_points. "
    "For a missing fact, incompatible operand units or zero denominator, use ONLY "
    "{'mode':'abstain'}. Never invent facts or operands. Return only the mode-specific JSON, "
    "no explanation or extra fields."
)
PROBE_SYSTEM = (
    'This is an unscored grammar challenge. Output exactly '
    '{"mode":"unsupported_mode","debug":true}. '
    "Do not replace unsupported_mode with a supported mode. No explanation."
)


class Lookup(StrictModel):
    mode: Literal["lookup"]
    operand: Operand
    answer_dimension: AnsweredDimension


class MultiValue(StrictModel):
    mode: Literal["multi_value"]
    values: list[Operand] = Field(min_length=2, max_length=6)
    answer_dimension: AnsweredDimension


class Arithmetic(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["difference", "percent_change", "average", "ratio"]
    operands: list[Operand] = Field(min_length=2, max_length=2)
    answer_dimension: AnsweredDimension


class Abstain(StrictModel):
    mode: Literal["abstain"]


ModeAnswer = Annotated[Lookup | MultiValue | Arithmetic | Abstain, Field(discriminator="mode")]
ADAPTER = TypeAdapter(ModeAnswer)
Mode = Literal["lookup", "multi_value", "arithmetic", "abstain"]


class ModeChoice(StrictModel):
    mode: Mode


MODE_SYSTEM = (
    "Choose the task mode from this fictional report. Return only {\"mode\":\"...\"}. "
    "arithmetic: question asks to calculate a difference, percent change, average or ratio "
    "from two cells. multi_value: question asks to LIST several existing cells, not calculate. "
    "lookup: question asks for ONE existing value or name. "
    "abstain: requested row/period/fact is absent, units incompatible, or denominator zero. "
    "Check the question and table before choosing. Do not output an answer or operands."
)


def mode_choice_body(report: Report, model: str, options: dict, *, probe: bool = False) -> dict:
    body = request_body(report, model, options, probe=probe)
    body["format"] = ModeChoice.model_json_schema()
    body["messages"][0]["content"] = PROBE_SYSTEM if probe else MODE_SYSTEM
    return body


def mode_specific_body(report: Report, mode: Mode, model: str, options: dict, *,
                       probe: bool = False) -> dict:
    model_type = {"lookup": Lookup, "multi_value": MultiValue,
                  "arithmetic": Arithmetic, "abstain": Abstain}[mode]
    schema = model_type.model_json_schema()
    if report.rows and "Operand" in schema.get("$defs", {}):
        properties = schema["$defs"]["Operand"]["properties"]
        properties["row_label"]["enum"] = sorted({row.label for row in report.rows})
        properties["period"]["enum"] = sorted({p for row in report.rows for p in row.values})
        properties["value"]["enum"] = sorted({v for row in report.rows for v in row.values.values()})
        properties["unit"]["enum"] = sorted({row.unit for row in report.rows})
    body = request_body(report, model, options, probe=probe)
    body["format"] = schema
    body["messages"][0]["content"] = PROBE_SYSTEM if probe else (
        SYSTEM + f" The mode has already been selected as {mode}; do not change it. "
        "Each operand.value is ONLY the cell's plain string (for example a numeric string), "
        "not serialized JSON, a formula, object, sentence or punctuation. "
        "Row labels, periods and units are separate fields. "
        "Input rows[].values is a dictionary: its KEYS are period labels; its VALUES are "
        "cell answers. Copy period from the key and value from the value, never the reverse. "
        "Only source field vocabularies are allowed by this schema; matching a whole cell "
        "is still checked by code. Do not output answer_scale: code derives it. "
        "Use row unit, not the monetary banner, for count/years/ratio. "
        "The exact output schema is: " + json.dumps(schema)
    )
    return body


def to_contract(answer: ModeAnswer) -> ContractAnswer:
    if isinstance(answer, Abstain):
        return ContractAnswer(values=[], operation="abstain", operands=[],
                              answer_dimension="none", answer_scale="")
    if isinstance(answer, Lookup):
        operands = [answer.operand]
    elif isinstance(answer, MultiValue):
        operands = answer.values
    else:
        scale = ("percent" if answer.operation == "percent_change" else
                 "" if answer.operation == "ratio" else unit_dimension(answer.operands[0].unit)[1])
        return ContractAnswer(values=[], operation=answer.operation, operands=answer.operands,
                              answer_dimension=answer.answer_dimension,
                              answer_scale=scale)
    return ContractAnswer(values=[o.value for o in operands], operation="lookup",
                          operands=operands, answer_dimension=answer.answer_dimension,
                          answer_scale=unit_dimension(operands[0].unit)[1])


def resolve_mode(answer: ModeAnswer, report: Report) -> tuple[list[str], bool]:
    return resolve(to_contract(answer), report)


def request_body(report: Report, model: str, options: dict, *, probe: bool = False,
                 constrained: bool = True) -> dict:
    result = {
        "model": model, "stream": False, "think": False, "keep_alive": "5m",
        "options": options,
        "messages": [{"role": "system", "content": PROBE_SYSTEM if probe else SYSTEM},
                     {"role": "user", "content": report.model_dump_json()}],
    }
    if constrained:
        result["format"] = ADAPTER.json_schema()
    return result
