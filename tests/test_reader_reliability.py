import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from asof.focused_reader import Answer, Case, abstention
from asof.reader_fields import field_record
from asof.reader_reliability import (
    WIRE,
    canonical_unit,
    conforms_to_wire,
    generation_orders,
    normalized_completion,
    reliability_messages,
    source_gated,
    summarize_reliability,
)

CONTEXT = dict.fromkeys(("scope", "accounting_basis", "period_kind", "revision_status"))


def item():
    return Case("U", "evaluation", "test", "FictionPoppy", "revenue", "2018",
                "FictionPoppy reported revenue of 8.5 USD billion for 2018.",
                ("8.5", "USD billion", "2018"))


def test_wire_schema_enforces_disjoint_answer_and_refusal_shapes():
    valid = abstention("No disclosed fact").model_dump()
    assert WIRE.validate_python(valid).abstain
    assert conforms_to_wire(json.dumps(valid))
    answer = Answer(value="8.5", unit="USD billion", period="2018", evidence=item().source,
                    abstain=False, reason="").model_dump()
    assert not WIRE.validate_python(answer).abstain
    for bad in ({**valid, "unit": None}, {**valid, "value": "8.5"},
                {**answer, "value": "NaN"}, {**answer, "period": "Q1"},
                {**answer, "reason": "extra reasoning"}, {**answer, "extra": 1}):
        with pytest.raises(ValidationError):
            WIRE.validate_python(bad)
        assert not conforms_to_wire(json.dumps(bad))


def test_unit_alias_repair_is_semantic_identity_not_conversion_or_gold_use():
    case = item()
    raw = Answer(value="8.5", unit="billions of USD", period="2018",
                 evidence=case.source, abstain=False, reason="").model_dump_json()
    completion = normalized_completion(case, raw)
    assert field_record(case, completion.result, CONTEXT)["score"]["correct"]
    assert completion.original.unit == "billions of USD"
    assert completion.result.answer.unit == "usd billion"
    assert completion.normalization["value_unchanged"]
    assert normalized_completion(replace(case, expected=None), raw) == completion
    for wrong in ("billion EUR", "million USD", "USD per share", "8.5 USD billion"):
        assert normalized_completion(case, raw.replace("billions of USD", wrong)).result.answer.abstain
    assert canonical_unit("billion USD") == canonical_unit("USD billion")


def test_invalid_or_abstained_model_outputs_remain_invalid_or_abstained():
    case = item()
    assert normalized_completion(case, '{"abstain":true}').result.answer is None
    raw = abstention("Incorrectly demanded an FX rate").model_dump_json()
    assert normalized_completion(case, raw).result.answer.abstain
    answered = Answer(value="8.5", unit="USD billion", period="2018",
                      evidence="fabricated quote", abstain=False, reason="").model_dump_json()
    assert normalized_completion(case, answered).result.answer.abstain


def test_source_gate_precedes_generation_and_does_not_claim_missing_positive_is_correct():
    case = item()
    assert not source_gated(case).model_required
    outside = replace(case, source="Revenue totaled 8.5 USD billion in fiscal 2018.")
    result = source_gated(outside)
    assert not result.model_required and result.result.answer.abstain
    assert result.result.status == "unresolved_requires_review"
    assert not field_record(outside, result.result, CONTEXT)["score"]["correct"]


def test_requests_exclude_gold_and_paired_generation_order_is_balanced():
    case = item()
    public = json.loads(reliability_messages(case)[1]["content"])
    assert public["target_currency"] is None and public["target_scale"] is None
    assert not {"expected", "expected_context", "split", "probe"} & public.keys()
    cases = tuple(replace(case, id=f"U{i}") for i in range(12))
    orders = generation_orders(cases)
    assert sum(order[0] == "structured" for order in orders.values()) == 6
    assert all(set(order) == {"free", "structured"} for order in orders.values())


def test_stopped_paired_runs_keep_unattempted_and_missing_latency_in_denominators():
    case = item()
    result = summarize_reliability((case,), {}, {case.id: CONTEXT}, [
        {"wire_contract": "structured", "latency_seconds": None}])
    assert result["wire_comparison"]["structured"]["attempted"] == 1
    assert result["wire_comparison"]["structured"]["missing_latency_attempts"] == 1
    assert result["wire_comparison"]["structured"]["schema_valid"] == 0
    assert result["arms"]["normalized_structured"]["correct"] == 0
    assert result["arms"]["normalized_structured"]["fields"]["value"]["planned_answerable"] == 1
    assert result["arms"]["normalized_structured"]["outcomes"] == {"not_attempted": 1}
