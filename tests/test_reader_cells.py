import json
from dataclasses import replace

from asof.focused_reader import Answer, Case
from asof.linked_reader import LinkedResult
from asof.reader_cells import catalog, cell_messages, diagnostic, select_cell, selection_schema
from asof.reader_field_challenge import build_coverage, evaluate_coverage
from asof.reader_fields import field_record

EMPTY = dict.fromkeys(("scope", "accounting_basis", "period_kind", "revision_status"))


def item():
    return Case("S", "evaluation", "test", "FictionSycamore", "revenue", "2018",
                "Company: FictionSycamore.\n"
                "| Item | 2017 (USD million) | 2018 (GBP thousand) |\n"
                "| Revenue | 63 | 28.5 |", ("28.5", "GBP thousand", "2018"))


def test_catalog_is_gold_independent_and_cell_choice_binds_tuple_and_header():
    case = item()
    cells = catalog(case)
    assert len(cells) == 2 and catalog(replace(case, expected=None)) == cells
    requested = next(cell for cell in cells if cell.result.bundle.period == "2018")
    choice = json.dumps({"cell_id": requested.cell_id, "reason": ""})
    result = select_cell(case, choice)
    assert field_record(case, result, EMPTY)["score"]["correct"]
    assert result.answer.value == "28.5" and result.answer.unit == "gbp thousand"
    assert {s.role for s in result.bundle.spans} >= {"period", "unit", "value", "entity", "metric"}
    wrong = next(cell for cell in cells if cell != requested)
    rejected = select_cell(case, json.dumps({"cell_id": wrong.cell_id, "reason": ""}))
    assert rejected.answer.abstain and rejected.reasons == ("wrong_reporting_year",)
    payload = json.loads(cell_messages(case)[1]["content"])
    assert "expected" not in payload and "expected_context" not in payload
    assert len(payload["cells"]) == 2 and "anyOf" in selection_schema(case)


def test_selection_rejects_foreign_ids_invented_tuple_or_invalid_refusal():
    case = item()
    for content in (
        '{"cell_id":"foreign","reason":""}',
        '{"cell_id":null,"reason":""}',
        '{"cell_id":null,"reason":"ambiguous","value":"28.5"}',
    ):
        assert select_cell(case, content).answer is None
    unknown = replace(case, source=case.source.replace("| Revenue |", "| Unrelated metric |"))
    assert catalog(unknown) == ()
    assert "anyOf" not in selection_schema(unknown)
    missed = select_cell(case, '{"cell_id":null,"reason":"unsupported"}')
    assert not field_record(case, missed, EMPTY)["score"]["correct"]
    assert select_cell(unknown, '{"cell_id":null,"reason":"not_disclosed"}').answer.abstain
    changed = replace(case, source=case.source.replace("28.5", "29.5"))
    assert {cell.cell_id for cell in catalog(case)}.isdisjoint(
        {cell.cell_id for cell in catalog(changed)})


def test_diagnostics_do_not_count_one_record_rejection_as_thirteen_numeric_errors():
    case = item()
    wrong = Answer(value="63", unit="USD million", period="2017", evidence="| Revenue | 63 | 28.5 |",
                   abstain=False, reason="")
    info = diagnostic(case, LinkedResult(None, None, "invalid"), wrong,
                      response_valid=True, model_fields=True)
    assert info["primary"] == "wrong_field"
    assert set(info["raw_tuple_mismatches"]) == {"value", "currency", "scale", "reporting_year"}
    assert "sign" not in info["raw_tuple_mismatches"]
    invalid = diagnostic(case, LinkedResult(None, None, "invalid"), None,
                         response_valid=False, model_fields=True)
    assert invalid["primary"] == "invalid_response" and invalid["raw_tuple_mismatches"] == []


def test_known_dimension_coverage_has_24_positive_cases_and_separate_negative_pairs():
    cases, labels = build_coverage()
    assert len(cases) == len(labels) == 192
    report = evaluate_coverage()
    for dimension in ("scope", "accounting_basis", "period_kind", "revision_status"):
        assert report["known_targets"][dimension] == 24
    assert report["known_targets"]["currency"] == report["known_targets"]["scale"] == 96
    assert report["negative_cases"] == 96
    assert not report["independent_gold"] and report["model_calls"] == 0
    assert report["summary"]["correct"] == 192, report["failures"]
