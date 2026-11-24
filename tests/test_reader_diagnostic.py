import json

import pytest
from pydantic import ValidationError

from asof.benchmark_baseline import TableInput
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid, request_body

ITEM = TableInput("What is the toy amount?", (("label", "value"), ("toy", "7")),
                  ("The toy value is seven.",))


def test_context_withholding_uses_same_question_without_report_or_gold():
    options = {"num_thread": 1, "num_gpu": 0}
    grounded = request_body(ITEM, model="toy", supplied_context=True, options=options)
    empty = request_body(ITEM, model="toy", supplied_context=False, options=options)
    assert grounded["messages"][0] == empty["messages"][0]
    visible = json.loads(empty["messages"][1]["content"])
    assert visible["question"] == ITEM.question
    assert "table" not in visible and "paragraphs" not in visible
    assert "The toy value" not in json.dumps(empty["messages"])
    assert grounded["options"] == options and grounded["think"] is False


def test_strict_answers_do_not_turn_malformed_output_into_abstention():
    for raw in (
        {"abstain": False, "answer": None, "scale": "", "evidence": []},
        {"abstain": True, "answer": 7, "scale": "", "evidence": []},
        {"abstain": False, "answer": True, "scale": "", "evidence": []},
    ):
        with pytest.raises(ValidationError):
            ReaderAnswer.model_validate(raw)


def test_citation_locations_and_quotes_are_checked_but_not_claimed_as_answer_proof():
    good = ReaderAnswer.model_validate({
        "abstain": False, "answer": 999, "scale": "",
        "evidence": [{"source": "table", "row": 1, "column": 1}],
    })
    # A real location can still fail to support the asserted answer.
    assert references_locally_valid(good, ITEM, supplied_context=True) is True
    assert references_locally_valid(good, ITEM, supplied_context=False) is False
    bad = good.model_copy(update={"evidence": [
        good.evidence[0].model_copy(update={"row": 99}),
    ]})
    assert references_locally_valid(bad, ITEM, supplied_context=True) is False
    quote = ReaderAnswer.model_validate({
        "abstain": False, "answer": "seven", "scale": "",
        "evidence": [{"source": "paragraph", "paragraph": 0, "quote": "value is seven"}],
    })
    assert references_locally_valid(quote, ITEM, supplied_context=True) is True
    abstain = ReaderAnswer.model_validate({
        "abstain": True, "answer": None, "scale": "", "evidence": [],
    })
    assert references_locally_valid(abstain, ITEM, supplied_context=True) is None


