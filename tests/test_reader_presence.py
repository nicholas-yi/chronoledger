import pytest

from asof.reader_contract import Report, Row
from asof.reader_presence import ADAPTER, NOT_PRESENT, answer_body, resolve_answer


def report():
    return Report(question="invented", monetary_banner="money in million; counts unscaled",
                  rows=[Row(label="Units", unit="count", values={"P": "0", "Q": "48"})])


def operand(value="48", period="Q"):
    return {"row_label": "Units", "period": period, "unit": "count", "value": value}


@pytest.mark.parametrize("field", ["row_label", "period", "unit", "value"])
def test_each_source_field_offers_not_present_and_yields_explicit_system_decline(field):
    r = report()
    schema = answer_body(r, "lookup", "toy", {})["format"]
    assert NOT_PRESENT in schema["$defs"]["PresenceOperand"]["properties"][field]["enum"]
    o = operand()
    o[field] = NOT_PRESENT
    answer = ADAPTER.validate_python({"mode": "lookup", "operand": o, "answer_dimension": "count"})
    result = resolve_answer(answer, r)
    assert result.abstention_source == "system" and result.decline_reason == "NOT_PRESENT"


def test_system_zero_dimension_missing_and_model_declines_are_distinct():
    r = report()
    rows = [
        ({"mode": "arithmetic", "operation": "ratio", "operands": [operand(), operand("0", "P")],
          "answer_dimension": "ratio"}, "zero_denominator"),
        ({"mode": "lookup", "operand": None, "answer_dimension": "count"}, "missing_operands"),
        ({"mode": "arithmetic", "operation": "average", "operands": [],
          "answer_dimension": "count"}, "missing_operands"),
        ({"mode": "lookup", "operand": operand(), "answer_dimension": "money"},
         "incompatible_answer_dimension"),
    ]
    for raw, reason in rows:
        result = resolve_answer(ADAPTER.validate_python(raw), r)
        assert result.abstention_source == "system" and result.decline_reason == reason
    result = resolve_answer(ADAPTER.validate_python({"mode": "abstain"}), r)
    assert result.abstention_source == "model"
    value = resolve_answer(ADAPTER.validate_python({
        "mode": "arithmetic", "operation": "difference",
        "operands": [operand(), operand("0", "P")], "answer_dimension": "count",
    }), r)
    assert value.values == ["48.00"] and value.computed_by_code and value.abstention_source is None


def test_call_budget_does_not_read_current_partial_receipt_as_completed_history(monkeypatch):
    import importlib.util
    from pathlib import Path
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("presence_runner_budget",
                                                scripts / "run_presence_control.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "history", lambda: [{"iteration": 1, "calls": 16}, {"iteration": 2}])
    assert module.prior_practice_calls(2) == 16
