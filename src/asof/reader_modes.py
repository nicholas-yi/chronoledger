"""Mode-discriminated reader interface, adapted to the existing checked calculator."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from asof.reader_contract import (
    ContractAnswer,
    Operand,
    Report,
    Scale,
    StrictModel,
    resolve,
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
    "are not money. answer_scale is thousand/million/billion only for money in those units; "
    "percent for percent/percentage_points, otherwise ''. Like-unit division gives ratio; "
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
    answer_scale: Scale


class MultiValue(StrictModel):
    mode: Literal["multi_value"]
    values: list[Operand] = Field(min_length=2, max_length=6)
    answer_dimension: AnsweredDimension
    answer_scale: Scale


class Arithmetic(StrictModel):
    mode: Literal["arithmetic"]
    operation: Literal["difference", "percent_change", "average", "ratio"]
    operands: list[Operand] = Field(min_length=2, max_length=2)
    answer_dimension: AnsweredDimension
    answer_scale: Scale


class Abstain(StrictModel):
    mode: Literal["abstain"]


ModeAnswer = Annotated[Lookup | MultiValue | Arithmetic | Abstain, Field(discriminator="mode")]
ADAPTER = TypeAdapter(ModeAnswer)


def to_contract(answer: ModeAnswer) -> ContractAnswer:
    if isinstance(answer, Abstain):
        return ContractAnswer(values=[], operation="abstain", operands=[],
                              answer_dimension="none", answer_scale="")
    if isinstance(answer, Lookup):
        operands = [answer.operand]
    elif isinstance(answer, MultiValue):
        operands = answer.values
    else:
        return ContractAnswer(values=[], operation=answer.operation, operands=answer.operands,
                              answer_dimension=answer.answer_dimension,
                              answer_scale=answer.answer_scale)
    return ContractAnswer(values=[o.value for o in operands], operation="lookup",
                          operands=operands, answer_dimension=answer.answer_dimension,
                          answer_scale=answer.answer_scale)


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
