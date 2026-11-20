import json

import pytest

from asof.focused_reader import Answer, Case, abstention
from asof.reader_ai_review import ReviewTask
from asof.reader_ai_review_v3 import (
    ARMS,
    Probe,
    account_attempts,
    decide,
    extraction_schema,
    load_probes,
    messages,
    parse,
    record,
    source_views,
    summarize,
)

TABLE = "Company: FictionTest.\n| Item | 2017 (USD million) | 2018 (EUR thousand) |\n| Revenue | 74 | 39.5 |"


def _task(candidate: Answer, verdict: str, source: str = TABLE) -> ReviewTask:
    case = Case("T1", "evaluation", "unit", "FictionTest", "revenue", "2018", source, None, None)
    return ReviewTask(case, candidate, verdict)


def _answer(value: str, unit: str, period: str = "2018") -> Answer:
    return Answer(value=value, unit=unit, period=period, evidence=TABLE, abstain=False, reason="")


def _stated(value="39.5", unit="EUR thousand", citations=("E3",)) -> str:
    return json.dumps({"answer": "stated", "value": value, "unit": unit, "citations": list(citations)})


def test_table_cells_are_shown_with_their_column_headers_but_citations_stay_verbatim():
    task = _task(_answer("39.5", "EUR thousand"), "supported")
    views = source_views(task.case)
    assert views["E3"]["view"] == "Revenue: 2017 (USD million) = 74; 2018 (EUR thousand) = 39.5"
    assert task.case.source[views["E3"]["start"]:views["E3"]["end"]] == views["E3"]["text"]
    payload = json.loads(messages(task)[1]["content"])
    assert "candidate" not in payload and "39.5" not in json.dumps(payload["issuer"])
    assert "expected" not in json.dumps(messages(task)) and "supported" not in messages(task)[1]["content"]


def test_candidate_is_compared_in_code_with_exact_same_currency_equivalence_and_no_fx():
    for candidate, verdict in ((_answer("39.5", "EUR thousand"), "supported"),
                               (_answer("0.0395", "EUR million"), "supported"),
                               (_answer("39.5", "USD thousand"), "unsupported"),
                               (_answer("39.5", "EUR million"), "unsupported"),
                               (_answer("39.5", "EUR thousand", period="2017"), "unsupported")):
        row = record(_task(candidate, verdict), _stated())
        assert row["valid"] and row["verdict"] == verdict, (candidate, row["reason"])
        assert not row["candidate_shown_to_model"] and not row["candidate_changed"]


def test_abstentions_and_unclear_extractions_map_through_a_fixed_table():
    justified = _task(abstention("no_answer_given"), "supported")
    for answer, verdict in (("not_stated", "supported"), ("conflicting", "supported"),
                            ("cannot_tell", "uncertain")):
        content = json.dumps({"answer": answer, "value": None, "unit": "",
                              "citations": ["E3"] if answer == "conflicting" else []})
        assert record(justified, content)["verdict"] == verdict
    assert record(justified, _stated())["verdict"] == "unsupported"
    answered = _task(_answer("39.5", "EUR thousand"), "supported")
    assert decide(answered, parse(answered, _stated(unit="euros")))[0] == "uncertain"


@pytest.mark.parametrize("content", [
    json.dumps({"answer": "stated", "value": "39.5", "unit": "EUR thousand", "citations": []}),
    json.dumps({"answer": "stated", "value": "39,5", "unit": "EUR thousand", "citations": ["E3"]}),
    json.dumps({"answer": "conflicting", "value": None, "unit": "", "citations": []}),
    json.dumps({"answer": "not_stated", "value": "1", "unit": "", "citations": []}),
    json.dumps({"answer": "stated", "value": "39.5", "unit": "EUR thousand", "citations": ["E9"]}),
    json.dumps({"answer": "stated", "value": "39.5", "unit": "EUR thousand", "citations": ["E3", "E3"]}),
    "not json",
])
def test_malformed_or_uncited_extractions_are_invalid_not_scored(content):
    assert not record(_task(_answer("39.5", "EUR thousand"), "supported"), content)["valid"]
    assert extraction_schema()


def _fixture_row(index: int, **overrides) -> dict:
    row = {"id": f"RV3-{index:02d}", "issuer": "FictionTest", "metric": "revenue", "year": "2018",
           "source": TABLE, "source_status": "stated", "source_fact": {"value": "39.5", "unit": "EUR thousand"},
           "candidate": {"value": "39.5", "unit": "EUR thousand", "period": "2018", "abstain": False, "reason": ""},
           "expected_verdict": "supported", "category": "unit", "rationale": "test"}
    return {**row, **overrides}


def test_loader_rejects_labels_inconsistent_with_the_authors_declared_rule(tmp_path):
    rows = [_fixture_row(i) for i in range(1, 25)]
    path = tmp_path / "probes.json"
    path.write_text(json.dumps(rows))
    probes = load_probes(path)
    assert len(probes) == 24 and probes[0].source_fact == ("39.5", "EUR thousand")
    rows[3] = _fixture_row(4, expected_verdict="unsupported")
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="RV3-04"):
        load_probes(path)


def test_summary_keeps_denominators_scores_extraction_and_accounts_missing_calls(tmp_path):
    rows = [_fixture_row(i) for i in range(1, 25)]
    path = tmp_path / "probes.json"
    path.write_text(json.dumps(rows))
    probes = load_probes(path)
    records = {p.task.case.id: {"ai_review_v3": record(p.task, _stated())} for p in probes[:23]}
    summary = summarize(probes, records, "blind_extraction_v3")
    assert summary["correct_verdicts"] == summary["model_extraction_correct"] == 23
    assert summary["invalid_or_missing"] == 1 and summary["human_gold_labels"] == 0 and not summary["promote"]
    calls = [{"call_id": 24, "case_id": probes[23].task.case.id, "status": "started",
              "wire_contract": ARMS["blind_extraction_v3"].wire_contract}]
    accounted = account_attempts(probes, records, calls, "blind_extraction_v3")
    assert summarize(probes, accounted, "blind_extraction_v3")["recorded"] == 24
    control = {p.task.case.id: {"ai_review_v3": ARMS["decomposed_v2_control"].record(p.task, json.dumps(
        {"verdict": "supported", "issues": [], "citations": ["E3"]}))} for p in probes}
    assert summarize(probes, control, "decomposed_v2_control")["correct_verdicts"] == 24
    assert isinstance(probes[0], Probe)
