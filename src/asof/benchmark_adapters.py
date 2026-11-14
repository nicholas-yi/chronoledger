"""FinQA representation adapters for the frozen two-explicit-year table baseline."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from asof.benchmark_baseline import YEAR, BaselineAnswer, TableInput, _cell, _tokens


@dataclass(frozen=True)
class FinQAProgram:
    tokens: tuple[str, ...] | None
    expected_answer: float | None
    reason: str


def finqa_input(record: dict) -> TableInput:
    """Only documented raw inputs; never retrieved/model_input/gold/program/answer fields."""
    return TableInput(
        record["qa"]["question"], tuple(tuple(row) for row in record["table"]),
        (*record["pre_text"], *record["post_text"]))


def finqa_program(item: TableInput, prediction: BaselineAnswer) -> FinQAProgram:
    """Encode the successful v1 operation, not a computed-answer constant.

    FinQA operates on reported table magnitudes; context millions are not added as
    multipliers. Percentage output is represented as a ratio, using native percent
    operand syntax where applicable. These are frozen adapter conventions, not
    choices made after comparison with reference answers.
    """
    if prediction.answer is None:
        return FinQAProgram(None, None, prediction.reason)
    question = item.question.lower()
    years = sorted(set(YEAR.findall(question)))
    ranked = [(len(_tokens(question) & _tokens(row[0])), row)
              for row in item.table if len(row) > 1 and _cell(row[0]) is None]
    best = max(score for score, _ in ranked)
    rows = [row for score, row in ranked if score == best]
    if len(rows) != 1 or not 1 <= len(years) <= 2:
        raise ValueError("adapter cannot reconstruct the emitted frozen mapping")
    values = {}
    for year in years:
        indices = {i for header in item.table[:3] for i, text in enumerate(header)
                   if i > 0 and year in YEAR.findall(text)}
        if len(indices) != 1:
            raise ValueError("adapter year mapping differs from emitted baseline")
        parsed = _cell(rows[0][indices.pop()])
        if parsed is None:
            raise ValueError("adapter cannot encode an emitted nonnumeric cell")
        values[year] = parsed
    direction = re.search(r"from\s+((?:19|20)\d{2})\s+to\s+((?:19|20)\d{2})", question)
    ordered = list(direction.groups()) if direction and len(years) == 2 else years
    percent_operands = (
        prediction.scale == "percent" and prediction.reason != "percentage_change"
        or prediction.reason == "percentage_change" and any(s == "percent" for _, s in values.values()))

    def atom(year: str) -> str:
        return format(values[year][0], ".15g") + ("%" if percent_operands else "")

    def step(operator: str, a: str, b: str) -> list[str]:
        return [operator + "(", a, b, ")"]

    reason = prediction.reason
    if reason == "unique_row_year_lookup":
        tokens = step("add", atom(ordered[0]), "const_0")
    elif reason == "two_year_average":
        tokens = step("add", atom(ordered[0]), atom(ordered[1]))
        tokens += step("divide", "#0", "const_2")
    elif reason == "two_year_sum":
        tokens = step("add", atom(ordered[0]), atom(ordered[1]))
    elif reason == "two_year_difference":
        tokens = step("subtract", atom(ordered[1]), atom(ordered[0]))
    elif reason == "percentage_change":
        tokens = step("subtract", atom(ordered[1]), atom(ordered[0]))
        tokens += step("divide", "#0", atom(ordered[0]))
    else:
        raise ValueError("unsupported frozen baseline operation")
    expected = float(prediction.answer) / (100 if prediction.scale == "percent" else 1)
    if not math.isfinite(expected):
        raise ValueError("adapter output must be finite")
    return FinQAProgram((*tokens, "EOF"), expected, reason)
