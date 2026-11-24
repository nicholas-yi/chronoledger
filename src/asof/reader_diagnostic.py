"""Strict, evidence-limited QA adapter for an existing local model; not historical inference."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asof.benchmark_baseline import TableInput
from asof.extraction import normalize

SYSTEM = (
    "Answer this financial report question using only the supplied report, not prior knowledge. "
    "If the supplied evidence is insufficient, abstain with answer=null, scale='', evidence=[]. "
    "Return only the requested JSON. Do not provide reasoning. "
    "Keep answers in the report's stated units and put the unit in scale. "
    "For a multi-part answer return a list of strings. "
    "For every non-abstention cite zero-based table row/column coordinates or a paragraph "
    "index and a short verbatim quote. A citation is not a substitute for answering."
)


class TableCitation(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    source: Literal["table"]
    row: int = Field(ge=0)
    column: int = Field(ge=0)


class ParagraphCitation(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    source: Literal["paragraph"]
    paragraph: int = Field(ge=0)
    quote: str = Field(min_length=1, max_length=1000)


class ReaderAnswer(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)
    abstain: bool
    answer: str | int | float | list[str] | None
    scale: Literal["", "thousand", "million", "billion", "percent"]
    evidence: list[Annotated[TableCitation | ParagraphCitation, Field(discriminator="source")]]

    @model_validator(mode="after")
    def consistent_answer(self) -> ReaderAnswer:
        if self.abstain:
            if self.answer is not None or self.scale or self.evidence:
                raise ValueError("abstention must have null answer and no scale/evidence")
        elif self.answer is None or (
            isinstance(self.answer, str) and not self.answer.strip()
        ) or (
            isinstance(self.answer, list)
            and (not self.answer or any(not text.strip() for text in self.answer))
        ):
            raise ValueError("non-abstention needs a nonempty answer")
        return self


def request_body(
    item: TableInput, *, model: str, supplied_context: bool, options: dict,
) -> dict:
    visible: dict[str, object] = {"question": item.question}
    if supplied_context:
        visible.update(table=item.table, paragraphs=[
            {"index": i, "text": text} for i, text in enumerate(item.paragraphs)
        ])
    else:
        visible["report"] = "No report evidence was supplied."
    return {
        "model": model, "stream": False, "think": False, "keep_alive": "5m",
        "format": ReaderAnswer.model_json_schema(), "options": options,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(visible, ensure_ascii=True)},
        ],
    }


def references_locally_valid(
    answer: ReaderAnswer, item: TableInput, *, supplied_context: bool,
) -> bool | None:
    """Check locations/normalized quote copying, NOT relevance or arithmetic/claim support."""
    if answer.abstain:
        return None
    if not supplied_context or not answer.evidence:
        return False
    for ref in answer.evidence:
        if isinstance(ref, TableCitation):
            if ref.row >= len(item.table) or ref.column >= len(item.table[ref.row]):
                return False
        elif (
            ref.paragraph >= len(item.paragraphs)
            or not normalize(ref.quote)
            or normalize(ref.quote) not in normalize(item.paragraphs[ref.paragraph])
        ):
            return False
    return True
