import json

from asof.reader_diagnostic import ReaderAnswer
from asof.reader_positive_control import (
    cases,
    classify_response,
    control_body,
    pass_criterion,
    score_answer,
)


def answer(value, scale=""):
    return ReaderAnswer.model_validate({
        "answer": value, "scale": scale, "abstain": value is None, "evidence": [],
    })


def test_exact_numeric_scale_and_text_normalization():
    lookup, percent, text, missing = cases()[0], cases()[6], cases()[8], cases()[10]
    assert score_answer(lookup, answer("$17.0", "million"))["correct"]
    assert not score_answer(lookup, answer("17000000"))["correct"]
    assert score_answer(percent, answer("25%"))["correct"]
    assert not score_answer(percent, answer("0.25", "percent"))["correct"]
    assert score_answer(text, answer("  COPPER   LADDER. "))["correct"]
    assert not score_answer(text, answer("Copper"))["correct"]
    assert score_answer(missing, answer(None))["correct"]
    assert not score_answer(missing, answer("6", "million"))["correct"]


def test_prompt_schema_bundle_preserves_input_runtime_and_never_sends_expected_label():
    item = cases()[4]
    old = control_body(item, "old_prompt_schema", model="toy", options={"num_thread": 4})
    new = control_body(item, "answer_first", model="toy", options={"num_thread": 4})
    assert old["messages"][1] == new["messages"][1]
    assert old["options"] == new["options"]
    assert old["think"] is new["think"] is False
    assert next(iter(old["format"]["properties"])) == "abstain"
    assert next(iter(new["format"]["properties"])) == "answer"
    assert old["messages"][0] != new["messages"][0]
    assert "expected" not in json.loads(new["messages"][1]["content"])


def test_raw_inspection_never_maps_bad_output_or_token_limit_to_abstention():
    valid = {"done_reason": "stop", "eval_count": 23, "message": {
        "content": '{"abstain":true,"answer":null,"scale":"","evidence":[]}',
    }}
    assert classify_response(valid, 256)["explicit_abstain"] is True
    bad = classify_response({"done_reason": "length", "eval_count": 256, "message": {
        "thinking": "synthetic reasoning marker", "content": "",
    }}, 256)
    assert bad["parse_rule"] == "invalid" and bad["explicit_abstain"] is None
    assert bad["token_limit_hit"] and bad["nonempty_thinking_field"] and bad["empty_visible_text"]


def test_pass_threshold_includes_unanswerable_controls_and_all_items():
    assert pass_criterion(9, 2, 12)
    assert not pass_criterion(8, 2, 12)
    assert not pass_criterion(10, 1, 12)
    assert not pass_criterion(9, 2, 11)


