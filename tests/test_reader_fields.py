import json
from dataclasses import replace
from pathlib import Path

import pytest

from asof.focused_reader import Answer, Case, abstention
from asof.linked_reader import LinkedResult, linked_parser
from asof.reader_fields import (
    contexts,
    field_messages,
    field_record,
    guarded_parser,
    load_field_cases,
    parser_first,
    summarize_fields,
    validate_source,
)


def item(source, *, metric="revenue", expected=("18", "EUR million", "2017")):
    return Case("F", "evaluation", "test", "FictionGrove", metric, "2017", source, expected)


EMPTY = dict.fromkeys(("scope", "accounting_basis", "period_kind", "revision_status"))


def test_parser_first_is_a_distinct_route_not_a_rewrite_or_use_of_gold():
    case = item("FictionGrove reported revenue of 18 EUR million for 2017.")
    raw = abstention("Model incorrectly demands USD").model_dump_json()
    result = parser_first(case, raw)
    assert result.route == "parser" and not result.model_required
    assert result.result.answer.value == "18"
    assert parser_first(replace(case, expected=None), raw) == result
    assert json.loads(raw)["abstain"] is True
    assert field_record(case, result.result, EMPTY)["score"]["correct"]
    public = json.loads(field_messages(case)[1]["content"])
    assert "annual" in public["period_requirement"]
    assert not {"expected", "expected_context", "split", "probe", "category"} & public.keys()


def test_context_guards_reject_quarters_and_gaap_substring_without_changing_old_parser():
    quarter = item("Company: FictionGrove. Reporting period: three months ended 2017.\n"
                   "| Item | 2017 (EUR million) |\n| Revenue | 18 |", expected=None)
    assert not linked_parser(quarter).answer.abstain
    result = parser_first(quarter, "{}")
    assert result.route == "source_refusal" and not result.model_required
    assert result.result.answer.abstain
    wrong_definition = item("FictionGrove reported non-GAAP operating income of 18 EUR million "
                           "for 2017.", metric="GAAP operating income", expected=None)
    assert not linked_parser(wrong_definition).answer.abstain
    assert guarded_parser(wrong_definition).answer.abstain
    assert not field_record(wrong_definition, linked_parser(wrong_definition), EMPTY)["score"]["correct"]


def test_field_records_bind_caption_context_and_preserve_unknown_dimensions():
    case = item("Company: FictionGrove. Reporting period: fiscal year 2017. "
                "Scope: consolidated. Accounting basis: GAAP.\n"
                "| Item | 2017 (EUR million) |\n| Revenue | 18 |")
    context = {**EMPTY, "period_kind": "fiscal_year", "scope": "consolidated",
               "accounting_basis": "gaap"}
    record = field_record(case, guarded_parser(case), context)
    assert record["score"]["correct"]
    assert record["fields"]["currency"] == "EUR" and record["fields"]["scale"] == "million"
    assert record["fields"]["sign"] == "positive"
    assert {span["role"] for span in record["context_spans"]} >= {
        "scope", "accounting_basis", "period_kind"}
    simple = item("FictionGrove reported revenue of 18 EUR million for 2017.")
    assert field_record(simple, guarded_parser(simple), EMPTY)["fields"]["scope"] is None
    conflict = replace(case, metric="non-GAAP operating income", source=case.source.replace(
        "| Revenue |", "| Non-GAAP operating income |"))
    assert guarded_parser(conflict).answer.abstain


def test_wrong_single_field_fails_whole_record_and_misses_remain_in_denominators():
    case = item("FictionGrove reported revenue of 18 EUR million for 2017.")
    good = linked_parser(case)
    wrong = replace(good, answer=good.answer.model_copy(update={"unit": "USD million"}))
    record = field_record(case, wrong, EMPTY)
    assert not record["score"]["correct"]
    assert record["field_correct"]["value"] is True and record["field_correct"]["currency"] is False
    missed = field_record(case, LinkedResult(abstention("unavailable"), None, "unavailable"), EMPTY)
    assert not any(missed["field_correct"].values())
    summary = summarize_fields((case,), {case.id: {"parser_first": missed}}, {case.id: EMPTY})
    assert summary["arms"]["parser_first"]["fields"]["value"]["planned_answerable"] == 1
    assert summary["arms"]["parser_first"]["answerable_coverage"] == 0
    assert summary["arms"]["parser_first"]["answer_precision"] is None


def test_nonmonetary_units_zero_and_invalid_fallback_are_not_fabricated_answers():
    zero = item("FictionGrove reported revenue of 0 EUR million for 2017.",
                expected=("0", "EUR million", "2017"))
    assert field_record(zero, guarded_parser(zero), EMPTY)["fields"]["sign"] == "zero"
    percent = item("FictionGrove reported gross margin of 12.5 percent for 2017.",
                   metric="gross margin", expected=("12.5", "%", "2017"))
    record = field_record(percent, guarded_parser(percent), EMPTY)
    assert record["score"]["correct"] and record["fields"]["currency"] is None
    assert record["field_states"]["currency"] == "not_applicable"
    assert record["field_states"]["scope"] == "unknown"
    missing = replace(zero, source="No revenue is supplied.", expected=None)
    bad = parser_first(missing, '{"abstain":true}')
    assert bad.model_required and bad.result.answer is None
    assert not field_record(missing, bad.result, EMPTY)["score"]["correct"]
    valid = Answer(value="18", unit="EUR million", period="2017", evidence="invented",
                   abstain=False, reason="").model_dump_json()
    assert parser_first(missing, valid).result.answer.abstain


def test_per_share_extension_requires_a_complete_source_relation_and_untampered_proof():
    case = item("FictionGrove reported diluted earnings per share of 1.25 USD per share for 2017.",
                metric="diluted earnings per share", expected=("1.25", "USD per share", "2017"))
    assert linked_parser(case).answer.abstain
    result = guarded_parser(case)
    assert validate_source(case, result.bundle) == ()
    assert field_record(case, result, EMPTY)["score"]["correct"]
    assert validate_source(case, replace(result.bundle, unit="eur per share"))
    quoted = replace(case, source=f'A fictional example says "{case.source}"', expected=None)
    assert guarded_parser(quoted).answer.abstain
    assert guarded_parser(replace(case, source=case.source.replace("per share for", "for"))).answer.abstain


def test_fresh_field_challenge_has_complete_annotation_contract():
    payload = json.loads((Path(__file__).parent / "fixtures" / "reader_fields.json").read_text())
    cases = load_field_cases(payload)
    assert len(cases) == 24 and sum(case.expected is not None for case in cases) == 12
    annotations = contexts(payload)
    assert set(annotations) == {case.id for case in cases}
    payload["pairs"][0]["cases"][0]["expected_context"].pop("scope")
    with pytest.raises(ValueError, match="all context labels"):
        load_field_cases(payload)


@pytest.mark.parametrize("source", [
    "For 2017, FictionGrove had 3700 subscribers.",
    "For 2017, FictionGrove had 3700 subscribers. Its previous 2016 subscriber count was 3900.",
    "FictionGrove had 3,700 subscribers in 2017.",
    "FICTIONGROVE reported\nrevenue of  18 EUR million for 2017.",
])
def test_natural_counts_and_wrapped_prose_preserve_source_offsets(source):
    count = "subscribers" in source
    case = item(source, metric="subscribers" if count else "revenue",
                expected=("3700", "subscribers", "2017") if count else ("18", "EUR million", "2017"))
    result = guarded_parser(case)
    assert field_record(case, result, EMPTY)["score"]["correct"]
    assert validate_source(case, result.bundle) == ()
    for span in result.bundle.spans:
        assert 0 <= span.start < span.end <= len(source)
    assert guarded_parser(replace(case, expected=None)) == result


@pytest.mark.parametrize("source", [
    "For 2016, FictionGrove had 3700 subscribers.",
    "For 2017, FictionGrovePartner had 3700 subscribers.",
    "For 2017, a customer of FictionGrove had 3700 subscribers.",
    "For 2017, FictionGrove did not have 3700 subscribers.",
    "For 2017, FictionGrove had 37,00 subscribers.",
    "For 2017, FictionGrove had 3700 subscribers for a competitor.",
    "For 2017, FictionGrove had 3700 subscribers. Its previous 2017 subscriber count was 3900.",
    "FictionGrove discussed the industry: manufacturers reported revenue of 18 EUR million for 2017.",
    ("FictionGrove reported subscribers of 110 subscribers for 2017. "
     "An equally authoritative, unreconciled table states FictionGrove reported "
     "subscribers of 130 subscribers for 2017."),
    "FictionGrove reported\n\nrevenue of 18 EUR million for 2017.",
    "FictionGrove reported\nCompany: Other.\nrevenue of 18 EUR million for 2017.",
    "FictionGrove reported\n| revenue | 18 EUR million for 2017 |",
    "'FictionGrove reported\nrevenue of 18 EUR million for 2017.'",
])
def test_new_prose_grammar_does_not_borrow_entity_context_across_boundaries(source):
    case = item(source, metric="subscribers" if "subscribers" in source else "revenue", expected=None)
    assert guarded_parser(case).answer.abstain
