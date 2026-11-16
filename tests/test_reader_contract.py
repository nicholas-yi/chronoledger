import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from asof.reader_contract import ContractAnswer, Control, passed, request_body, resolve


def controls():
    path = Path(__file__).parent / "fixtures" / "reader_contract_controls.json"
    return [Control.model_validate(row) for row in json.loads(path.read_text())]


def response(case, locations, operation=None, dimension=None, scale=None):
    operands = [{"row_label": case.report.rows[r].label, "period": p,
                 "unit": case.report.rows[r].unit, "value": case.report.rows[r].values[p]}
                for r, p in locations]
    op = operation or case.expected_operation
    return ContractAnswer.model_validate({
        "values": [o["value"] for o in operands] if op == "lookup" else [],
        "operation": op, "operands": operands,
        "answer_dimension": dimension or case.expected_dimension,
        "answer_scale": case.expected_scale if scale is None else scale,
    })


def test_separate_multivalues_and_prompt_never_include_expected_answers():
    case = controls()[0]
    answer = response(case, [(0, "North"), (0, "South")])
    assert resolve(answer, case.report) == (case.expected, False)
    invalid = answer.model_dump()
    invalid["values"] = ["Orchid Quay and Cobalt Dock"]
    with pytest.raises(ValidationError):
        ContractAnswer.model_validate(invalid)
    sent = json.loads(request_body(case.report, "toy", {})["messages"][1]["content"])
    assert set(sent) == {"question", "monetary_banner", "rows"}
    assert "expected" not in sent


@pytest.mark.parametrize(("index", "locations", "expected"), [
    (6, [(0, "Cycle Q"), (0, "Cycle P")], ["23.00"]),
    (7, [(0, "Cycle Q"), (0, "Cycle P")], ["-23.00"]),
    (8, [(0, "Cycle Q"), (0, "Cycle P")], ["25.00"]),
    (10, [(0, "Cycle P"), (0, "Cycle Q")], ["45.00"]),
    (12, [(0, "Cycle Q"), (1, "Cycle Q")], ["2.50"]),
])
def test_code_computes_from_two_checked_operands(index, locations, expected):
    case = controls()[index]
    answer = response(case, locations)
    assert resolve(answer, case.report) == (expected, True)
    bad = answer.model_dump()
    bad["values"] = expected
    with pytest.raises(ValidationError):
        ContractAnswer.model_validate(bad)


def test_wrong_cell_value_period_unit_and_answer_dimension_fail_explicitly():
    case = controls()[18]
    answer = response(case, [(0, "Cycle Q")])
    assert resolve(answer, case.report) == (["73"], False)
    for field, value in (("value", "74"), ("period", "Cycle P"), ("unit", "million")):
        raw = answer.model_dump()
        raw["operands"][0][field] = value
        with pytest.raises(ValueError):
            resolve(ContractAnswer.model_validate(raw), case.report)
    with pytest.raises(ValueError, match="dimension/scale"):
        resolve(response(case, [(0, "Cycle Q")], dimension="money", scale="million"), case.report)


def test_zero_denominator_is_not_success_shaped_abstention():
    case = controls()[23]
    with pytest.raises(ValueError, match="zero denominator"):
        resolve(response(case, [(0, "Cycle Q"), (0, "Cycle P")],
                         operation="ratio", dimension="ratio"), case.report)
    assert resolve(response(case, []), case.report) == ([], False)
    assert passed(20, 3, 24)
    assert not passed(19, 3, 24)
    assert not passed(21, 2, 24)
