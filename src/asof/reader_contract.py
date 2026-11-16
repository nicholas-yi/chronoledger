"""Invented-control contract: source-checked operands and code, not model arithmetic."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Unit = Literal["USD", "thousand", "million", "billion", "count", "years", "percent", "ratio", "text"]
Dimension = Literal["money", "count", "years", "percent", "percentage_points", "ratio", "text", "none"]
Operation = Literal["lookup", "difference", "percent_change", "average", "ratio", "abstain"]
Scale = Literal["", "thousand", "million", "billion", "percent"]

SYSTEM = (
    "Solve only from this fictional report. Return JSON with values as a LIST of separate "
    "strings, never a joined sentence, including for one value. Copy each lookup value and "
    "its source operand exactly; use one operand per value. Each operand has row_label, "
    "period, unit, value, copied from the same table cell and its row metadata. Do not select "
    "a header or a different period. For calculations select exactly TWO numeric operands "
    "and the operation, and leave values=[]: code computes the answer, not you. "
    "difference means first minus second; percent_change means 100*(first-second)/second "
    "(first=new, second=old); average means (first+second)/2; ratio means first/second. "
    "Operands must have the same unit. Do not invent a result cell or include a computed "
    "result as an operand. Choose answer_dimension separately from source unit and the "
    "monetary banner: money/count/years/percent/percentage_points/ratio/text. "
    "Set answer_scale to thousand/million/billion only for money in those units; "
    "percent for percent or percentage_points; otherwise ''. A ratio of like units is "
    "dimensionless, not money; percent change is percent, not the operands' unit. "
    "For difference of percent-valued cells use percentage_points, not relative change. "
    "For missing facts, incompatible units or a zero denominator, use operation='abstain', "
    "values=[], operands=[], answer_dimension='none', answer_scale=''. "
    "Never guess, use outside knowledge, emit reasoning or compute the arithmetic yourself."
)


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class Row(StrictModel):
    label: str
    unit: Unit
    values: dict[str, str]


class Report(StrictModel):
    question: str
    monetary_banner: str
    rows: list[Row]


class Operand(StrictModel):
    row_label: str
    period: str
    unit: Unit
    value: str = Field(min_length=1, max_length=100)


class ContractAnswer(StrictModel):
    values: list[str] = Field(max_length=6)
    operation: Operation
    operands: list[Operand] = Field(max_length=6)
    answer_dimension: Dimension
    answer_scale: Scale

    @model_validator(mode="after")
    def shape(self) -> ContractAnswer:
        if self.operation == "abstain":
            if self.values or self.operands or self.answer_dimension != "none" or self.answer_scale:
                raise ValueError("abstention must be empty and dimension none")
        elif self.operation == "lookup":
            if not self.values or len(self.values) != len(self.operands):
                raise ValueError("lookup needs separate values and one operand per value")
        elif self.values or len(self.operands) != 2:
            raise ValueError("arithmetic needs two operands and no model-computed values")
        return self


class Control(StrictModel):
    id: str
    category: Literal["multi_value", "arithmetic", "lookup", "unit_trap", "unanswerable"]
    report: Report
    expected: list[str]
    expected_dimension: Dimension
    expected_scale: Scale
    expected_operation: Operation


def number(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("operand is not a plain decimal") from exc
    if not result.is_finite() or abs(result) > Decimal("1e15"):
        raise ValueError("nonfinite or out-of-scope operand magnitude")
    return result


def unit_dimension(unit: Unit) -> tuple[Dimension, Scale]:
    if unit in ("thousand", "million", "billion"):
        return "money", unit
    if unit == "USD":
        return "money", ""
    if unit == "percent":
        return "percent", "percent"
    return unit, ""


def resolve(answer: ContractAnswer, report: Report) -> tuple[list[str], bool]:
    if answer.operation == "abstain":
        return [], False
    rows = {r.label: r for r in report.rows}
    if len(rows) != len(report.rows):
        raise ValueError("source row labels must be unique")
    seen = set()
    for operand in answer.operands:
        location = operand.row_label, operand.period
        if location in seen:
            raise ValueError("duplicate source operand")
        seen.add(location)
        row = rows.get(operand.row_label)
        if row is None or operand.period not in row.values or row.unit != operand.unit:
            raise ValueError("operand row/period/unit does not match source")
        source = row.values[operand.period]
        if row.unit == "text":
            matches = source == operand.value
        else:
            matches = number(source) == number(operand.value)
        if not matches:
            raise ValueError("operand value does not match its source cell")
    units = {o.unit for o in answer.operands}
    if len(units) != 1:
        raise ValueError("mixed-unit operands are unsupported; do not silently rescale")
    dimension, scale = unit_dimension(answer.operands[0].unit)
    computed = answer.operation != "lookup"
    if not computed:
        if answer.values != [o.value for o in answer.operands]:
            raise ValueError("lookup values differ from selected source operands")
        values = answer.values
    else:
        if dimension == "text":
            raise ValueError("cannot calculate on text")
        left, right = (number(o.value) for o in answer.operands)
        with localcontext() as context:
            context.prec = 40
            if answer.operation in ("percent_change", "ratio") and right == 0:
                raise ValueError("zero denominator; explicit abstention required")
            if answer.operation == "difference":
                result = left - right
                if dimension == "percent":
                    dimension = "percentage_points"
            elif answer.operation == "average":
                result = (left + right) / 2
            elif answer.operation == "percent_change":
                result, dimension, scale = 100 * (left - right) / right, "percent", "percent"
            elif answer.operation == "ratio":
                result, dimension, scale = left / right, "ratio", ""
            else:
                raise ValueError("unsupported operation")
            values = [format(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")]
    if (answer.answer_dimension, answer.answer_scale) != (dimension, scale):
        raise ValueError("answer dimension/scale conflicts with selected operation and source units")
    return values, computed


def request_body(report: Report, model: str, options: dict) -> dict:
    return {
        "model": model, "stream": False, "think": False, "keep_alive": "5m",
        "format": ContractAnswer.model_json_schema(), "options": options,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": report.model_dump_json()}],
    }


def passed(answerable_correct: int, abstentions_correct: int, attempted: int) -> bool:
    return attempted == 24 and answerable_correct >= 20 and abstentions_correct == 3
