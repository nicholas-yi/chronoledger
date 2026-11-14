"""Invented positive controls and a generic answer-first prompt/schema experiment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import ValidationError

from asof.benchmark_baseline import TableInput
from asof.reader_diagnostic import ReaderAnswer, request_body

Arm = Literal["old_prompt_schema", "answer_first"]
ARMS: tuple[Arm, ...] = ("old_prompt_schema", "answer_first")
ANSWER_FIRST_SYSTEM = (
    "Solve the question from the supplied small table and text. First locate the requested "
    "value or perform the requested arithmetic. When the evidence determines the answer, "
    "return that answer and set abstain=false. Do not ignore a value explicitly present. "
    "Only if the requested fact is missing or cannot be determined, return answer=null, "
    "scale='', evidence=[], abstain=true; do not guess or use outside knowledge. "
    "Return only JSON, no reasoning. Give a scalar number or short text span, not a sentence. "
    "Keep numeric answers in the stated report units and put the unit in scale. Percent "
    "change is 100*(new-old)/old, expressed in percent. Cite zero-based table row/column "
    "coordinates or a paragraph index with a short verbatim quote for an answered question."
)


@dataclass(frozen=True)
class SyntheticCase:
    id: str
    category: str
    item: TableInput
    expected: str | None
    scale: str = ""
    numeric: bool = True


def cases() -> tuple[SyntheticCase, ...]:
    return (
        SyntheticCase("PC01", "lookup", TableInput(
            "What is fictional FableWren Works' 2020 revenue in the table's units?",
            (("Revenue (million)", "2019", "2020"), ("Revenue", "12", "17")), (),
        ), "17", "million"),
        SyntheticCase("PC02", "lookup", TableInput(
            "How many staff did fictional AmberKite Demo have in 2020?",
            (("Staff", "2019", "2020"), ("Headcount", "8", "11")), (),
        ), "11"),
        SyntheticCase("PC03", "lookup", TableInput(
            "What is fictional CloudMica Toy's 2019 cost in the table's units?",
            (("Cost (thousand)", "2019", "2020"), ("Cost", "6", "9")), (),
        ), "6", "thousand"),
        SyntheticCase("PC04", "lookup", TableInput(
            "How many demo units did fictional TernPetal ship in 2020?",
            (("Units", "2019", "2020"), ("Shipments", "14", "19")), (),
        ), "19"),
        SyntheticCase("PC05", "arithmetic", TableInput(
            "For fictional MossLantern, what is 2020 revenue minus 2019 revenue, in table units?",
            (("Revenue (million)", "2019", "2020"), ("Revenue", "10", "18")), (),
        ), "8", "million"),
        SyntheticCase("PC06", "arithmetic", TableInput(
            "For fictional OpalFinch, what is 2020 cost minus 2019 cost? Keep the sign and table units.",
            (("Cost (thousand)", "2019", "2020"), ("Cost", "30", "21")), (),
        ), "-9", "thousand"),
        SyntheticCase("PC07", "arithmetic", TableInput(
            "What is fictional BrambleQuartz's percent change in demo units from 2019 to 2020?",
            (("Units", "2019", "2020"), ("Units", "20", "25")), (),
        ), "25", "percent"),
        SyntheticCase("PC08", "arithmetic", TableInput(
            "What is fictional WillowComet's percent change in demo units from 2019 to 2020?",
            (("Units", "2019", "2020"), ("Units", "80", "60")), (),
        ), "-25", "percent"),
        SyntheticCase("PC09", "text", TableInput(
            "What project name does fictional FernCompass use?", (),
            ("FernCompass uses the project name Copper Ladder.",),
        ), "Copper Ladder", numeric=False),
        SyntheticCase("PC10", "text", TableInput(
            "What material does fictional VelaAcorn use for its demo cases?", (),
            ("VelaAcorn makes its demo cases from recycled cork.",),
        ), "recycled cork", numeric=False),
        SyntheticCase("PC11", "unanswerable", TableInput(
            "What is fictional SlateWisp's 2021 revenue?",
            (("Revenue (million)", "2019", "2020"), ("Revenue", "4", "5")), (),
        ), None),
        SyntheticCase("PC12", "unanswerable", TableInput(
            "In which city is fictional LarkPrism headquartered?", (),
            ("LarkPrism uses biodegradable packaging for its demonstration products.",),
        ), None, numeric=False),
    )


def control_body(case: SyntheticCase, arm: Arm, *, model: str, options: dict) -> dict:
    body = request_body(case.item, model=model, supplied_context=True, options=options)
    if arm == "answer_first":
        body["messages"][0]["content"] = ANSWER_FIRST_SYSTEM
        schema = body["format"]
        keys = ("answer", "scale", "evidence", "abstain")
        schema["properties"] = {key: schema["properties"][key] for key in keys}
        schema["required"] = list(keys)
    elif arm != "old_prompt_schema":
        raise ValueError("unknown positive-control arm")
    return body


def classify_response(raw: dict, token_limit: int) -> dict:
    message = raw.get("message", {})
    content = message.get("content")
    result = {
        "done_reason": raw.get("done_reason"), "eval_count": raw.get("eval_count"),
        "token_limit_hit": isinstance(raw.get("eval_count"), int)
        and raw["eval_count"] >= token_limit,
        "thinking_field_present": "thinking" in message,
        "nonempty_thinking_field": bool(message.get("thinking")),
        "visible_think_markup": isinstance(content, str)
        and ("<think>" in content or "</think>" in content),
        "empty_visible_text": not isinstance(content, str) or not content.strip(),
        "parse_rule": "invalid", "explicit_abstain": None,
    }
    try:
        parsed = ReaderAnswer.model_validate_json(content)
    except ValidationError:
        return result
    result.update(parse_rule="valid", explicit_abstain=parsed.abstain,
                  answer_is_null=parsed.answer is None)
    return result


def score_answer(case: SyntheticCase, answer: ReaderAnswer) -> dict:
    if answer.abstain:
        correct = case.expected is None
        return {"correct": correct, "outcome": "correct_abstention" if correct else "abstained"}
    if case.expected is None:
        return {"correct": False, "outcome": "answered_unanswerable"}
    if isinstance(answer.answer, list):
        return {"correct": False, "outcome": "expected_single_scalar"}
    value, scale = str(answer.answer).strip(), answer.scale
    if case.numeric:
        if value.endswith("%"):
            if scale not in ("", "percent"):
                return {"correct": False, "outcome": "conflicting_percent_scale"}
            value, scale = value[:-1].strip(), "percent"
        try:
            number = Decimal(value.replace(",", "").replace("$", ""))
        except InvalidOperation:
            return {"correct": False, "outcome": "invalid_numeric_answer"}
        correct = number.is_finite() and number == Decimal(case.expected) and scale == case.scale
    else:
        def normalize(text: str) -> str:
            return re.sub(r"\s+", " ", text.strip().rstrip(".")).casefold()
        correct = normalize(value) == normalize(case.expected) and scale == case.scale
    return {"correct": correct, "outcome": "correct" if correct else "wrong"}


def pass_criterion(answerable_correct: int, unanswerable_correct: int, attempted: int) -> bool:
    return attempted == 12 and answerable_correct >= 9 and unanswerable_correct == 2
