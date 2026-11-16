import pytest
from pydantic import ValidationError

from asof.reader_contract import Report, Row
from asof.reader_modes import ADAPTER, request_body, resolve_mode


def operand(value="15", period="P"):
    return {"row_label": "Units", "period": period, "unit": "count", "value": value}


def test_union_rejects_cross_mode_fields_and_contradictory_abstentions():
    for raw in (
        {"mode": "abstain", "values": ["15"]},
        {"mode": "unsupported_mode"},
        {"mode": "lookup", "values": [operand()], "answer_dimension": "count", "answer_scale": ""},
        {"mode": "arithmetic", "operation": "difference", "operands": [operand()],
         "answer_dimension": "count", "answer_scale": ""},
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
        "answer_dimension": "count", "answer_scale": "",
    })
    assert resolve_mode(multi, report) == (["15", "33"], False)
    arithmetic = ADAPTER.validate_python({
        "mode": "arithmetic", "operation": "difference",
        "operands": [operand("33", "Q"), operand()],
        "answer_dimension": "count", "answer_scale": "",
    })
    assert resolve_mode(arithmetic, report) == (["18.00"], True)
    bad = arithmetic.model_copy(update={"answer_scale": "million"})
    with pytest.raises(ValueError, match="dimension/scale"):
        resolve_mode(bad, report)
    assert "expected" not in request_body(report, "toy", {})["messages"][1]["content"]
