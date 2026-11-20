import json

from asof.focused_reader import Answer, Case, abstention
from asof.reader_ai_review import ReviewTask
from asof.reader_ai_review_v3 import Probe
from asof.review_pipeline import evaluate, route, rule_decision

TABLE = "Company: FictionTest.\n| Item | 2017 (USD million) | 2018 (EUR thousand) |\n| Revenue | 74 | 39.5 |"
PROSE = "FictionTest said revenue for 2018 was corrected and now supersedes earlier figures."


def _probe(identifier, source, candidate, expected, status="stated"):
    case = Case(identifier, "evaluation", "unit", "FictionTest", "revenue", "2018", source, None, None)
    return Probe(ReviewTask(case, candidate, expected), status, None, "unit")


def _answer(value, unit, source=TABLE):
    return Answer(value=value, unit=unit, period="2018", evidence=source, abstain=False, reason="")


def test_rules_decide_header_bound_tables_and_refute_unnecessary_abstentions_without_the_model():
    assert rule_decision(_probe("A", TABLE, _answer("39.5", "EUR thousand"), "supported"))["verdict"] == "supported"
    assert rule_decision(_probe("B", TABLE, _answer("39.5", "USD thousand"), "unsupported"))["verdict"] == "unsupported"
    assert rule_decision(_probe("C", TABLE, abstention("no_answer_given"), "unsupported"))["verdict"] == "unsupported"
    assert rule_decision(_probe("D", PROSE, abstention("no_answer_given"), "supported"))["verdict"] == "uncertain"


def test_ai_is_consulted_only_when_rules_defer_and_invalid_ai_output_stays_uncertain():
    assert route({"verdict": "unsupported"}, {"valid": True, "verdict": "supported"}) == ("unsupported", "rules")
    assert route({"verdict": "uncertain"}, {"valid": True, "verdict": "supported"}) == ("supported", "ai_fallback")
    assert route({"verdict": "uncertain"}, {"valid": False, "verdict": None}) == ("uncertain", "no_valid_ai_fallback")
    assert route({"verdict": "uncertain"}, None) == ("uncertain", "no_valid_ai_fallback")


def test_pipeline_summary_keeps_every_denominator_and_component_score():
    probes = (_probe("A", TABLE, _answer("39.5", "USD thousand"), "unsupported"),
              _probe("D", PROSE, abstention("no_answer_given"), "supported", "not_stated"))
    ai = {"A": {"ai_review_v3": {"valid": True, "verdict": "supported"}},
          "D": {"ai_review_v3": {"valid": True, "verdict": "supported"}}}
    report = evaluate(probes, ai)
    assert report["pipeline"]["correct_verdicts"] == 2 and report["ai_only"]["false_support"] == 1
    assert report["rules_only"]["uncertain_or_invalid"] == 1
    assert report["decided_by"] == {"rules": 1, "ai_fallback": 1, "no_valid_ai_fallback": 0}
    assert not report["promote"] and not report["independent_human_gold"]
    json.dumps(report)
