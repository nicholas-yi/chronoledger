import pytest
from pydantic import ValidationError

from asof.reader_contract import Report, Row
from asof.reader_modes import ADAPTER, ModeChoice, mode_specific_body, request_body, resolve_mode


def operand(value="15", period="P"):
    return {"row_label": "Units", "period": period, "unit": "count", "value": value}


def test_union_rejects_cross_mode_fields_and_contradictory_abstentions():
    for raw in (
        {"mode": "abstain", "values": ["15"]},
        {"mode": "unsupported_mode"},
        {"mode": "lookup", "values": [operand()], "answer_dimension": "count"},
        {"mode": "arithmetic", "operation": "difference", "operands": [operand()],
         "answer_dimension": "count"},
    ):
        with pytest.raises(ValidationError):
            ADAPTER.validate_python(raw)
    assert ADAPTER.validate_python({"mode": "abstain"}).mode == "abstain"
    schema = ADAPTER.json_schema()
    assert len(schema["oneOf"]) == 4 and schema["discriminator"]["propertyName"] == "mode"


def test_mode_lists_adapt_to_native_values_and_checked_calculation():
    report = Report(question="invented", monetary_banner="money in million; units are counts",
                    rows=[Row(label="Units", unit="count", values={"P": "15", "Q": "33"})])
    multi = ADAPTER.validate_python({
        "mode": "multi_value", "values": [operand(), operand("33", "Q")],
        "answer_dimension": "count",
    })
    assert resolve_mode(multi, report) == (["15", "33"], False)
    arithmetic = ADAPTER.validate_python({
        "mode": "arithmetic", "operation": "difference",
        "operands": [operand("33", "Q"), operand()],
        "answer_dimension": "count",
    })
    assert resolve_mode(arithmetic, report) == (["18.00"], True)
    bad = arithmetic.model_copy(update={"answer_dimension": "money"})
    with pytest.raises(ValueError, match="dimension/scale"):
        resolve_mode(bad, report)
    assert "expected" not in request_body(report, "toy", {})["messages"][1]["content"]


def test_fallback_mode_choice_and_answer_schema_lock_mode_without_redundant_values():
    choice = ModeChoice.model_validate({"mode": "arithmetic"})
    with pytest.raises(ValidationError):
        ModeChoice.model_validate({"mode": "arithmetic", "values": ["18"]})
    report = Report(question="invented", monetary_banner="", rows=[])
    body = mode_specific_body(report, choice.mode, "toy", {})
    assert body["format"]["properties"]["mode"]["const"] == "arithmetic"
    assert "values" not in body["format"]["properties"]
    assert body["format"]["additionalProperties"] is False


def test_source_vocabularies_and_percent_scale_are_code_derived_not_redundant_fields():
    report = Report(question="invented", monetary_banner="money in million; units are counts",
                    rows=[Row(label="Units", unit="count", values={"P": "15", "Q": "33"})])
    schema = mode_specific_body(report, "arithmetic", "toy", {})["format"]
    fields = schema["$defs"]["Operand"]["properties"]
    assert fields["period"]["enum"] == ["P", "Q"]
    assert set(fields["value"]["enum"]) == {"15", "33"}
    assert "answer_scale" not in schema["properties"]
    answer = ADAPTER.validate_python({
        "mode": "arithmetic", "operation": "percent_change",
        "operands": [operand("33", "Q"), operand()], "answer_dimension": "percent",
    })
    assert resolve_mode(answer, report) == (["120.00"], True)
