from decimal import Decimal

import pytest

from asof.reader_contract import Report, Row
from asof.reader_roles import ADAPTER, answer_body, resolve_roles


def report():
    return Report(question="invented", monetary_banner="money in million",
                  rows=[Row(label="Amount", unit="million",
                            values={"Before": "-40", "After": "-20", "Zero": "0"})])


def operand(period, value):
    return {"row_label": "Amount", "period": period, "unit": "million", "value": value}


@pytest.mark.parametrize(("op", "dimension", "expected", "scale"), [
    ("difference", "money", ["20.00"], "million"),
    ("percent_change", "percent", ["50.00"], "percent"),
])
def test_named_start_end_and_absolute_start_percent_denominator(op, dimension, expected, scale):
    answer = ADAPTER.validate_python({
        "mode": "arithmetic", "operation": op,
        "start_value": operand("Before", "-40"), "end_value": operand("After", "-20"),
        "answer_dimension": dimension,
    })
    result = resolve_roles(answer, report())
    assert result.values == expected and result.scale == scale and result.computed_by_code


def test_named_ratio_does_not_swap_zero_denominator_with_valid_zero_numerator():
    r = report()
    answer = {"mode": "arithmetic", "operation": "ratio",
              "numerator": operand("After", "-20"), "denominator": operand("Zero", "0"),
              "answer_dimension": "ratio"}
    result = resolve_roles(ADAPTER.validate_python(answer), r)
    assert result.abstention_source == "system" and result.decline_reason == "zero_denominator"
    answer["numerator"], answer["denominator"] = answer["denominator"], answer["numerator"]
    valid = resolve_roles(ADAPTER.validate_python(answer), r)
    assert valid.abstention_source is None and Decimal(valid.values[0]) == 0
    change = ADAPTER.validate_python({
        "mode": "arithmetic", "operation": "percent_change",
        "start_value": operand("Zero", "0"), "end_value": operand("After", "-20"),
        "answer_dimension": "percent",
    })
    assert resolve_roles(change, r).decline_reason == "zero_denominator"


def test_average_values_and_mixed_missing_multivalue_are_not_cleaned_up():
    r = report()
    result = resolve_roles(ADAPTER.validate_python({
        "mode": "arithmetic", "operation": "average",
        "values": [operand("Before", "-40"), operand("After", "-20"), operand("Zero", "0")],
        "answer_dimension": "money",
    }), r)
    assert result.values == ["-20.00"]
    missing = {field: "NOT_PRESENT" for field in ("row_label", "period", "unit", "value")}
    result = resolve_roles(ADAPTER.validate_python({
        "mode": "multi_value", "values": [operand("After", "-20"), missing],
        "answer_dimension": "money",
    }), r)
    assert result.abstention_source == "system" and result.decline_reason == "mixed_NOT_PRESENT_values"
    schema = answer_body(r, "arithmetic", "toy", {})["format"]
    assert schema["discriminator"]["propertyName"] == "operation"
    assert "start_value" in schema["$defs"]["Change"]["properties"]
    assert "operands" not in schema["$defs"]["Change"]["properties"]
