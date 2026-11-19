import json
from dataclasses import replace

from asof.focused_reader import Answer, Case
from asof.linked_reader import (
    complete_evidence,
    linked_parser,
    linked_score,
    resolve,
    validate_bundle,
)


def case(source, *, metric="revenue", period="2017", expected=("18", "EUR million", "2017")):
    return Case("L", "evaluation", "test", "FictionAster", metric, period, source, expected)


def test_table_headers_row_and_column_units_are_bound_to_the_selected_cell():
    item = case("Reporting company: FictionAster. Amounts in USD million.\n"
                "| Item | 2016 (USD million) | 2017 (EUR million) |\n"
                "| Revenue | 91 | 18 |")
    result = linked_parser(item)
    assert linked_score(item, result)["correct"]
    assert validate_bundle(item, result.bundle) == ()
    roles = {span.role for span in result.bundle.spans}
    assert {"entity", "period", "unit", "value", "metric"} <= roles
    for changed in (
        replace(result.bundle, unit="usd million"),
        replace(result.bundle, period="2016"),
        replace(result.bundle, issuer="Other"),
        replace(result.bundle, source_sha256="0"*64),
        replace(result.bundle, spans=tuple(s for s in result.bundle.spans if s.role != "unit")),
    ):
        assert validate_bundle(item, changed)
    # A row unit does not borrow a conflicting selected-column unit.
    conflict = replace(item, source=item.source.replace("| Revenue |", "| Revenue (USD million) |"))
    assert linked_parser(conflict).answer.abstain


def test_footnote_override_requires_the_same_row_marker_and_metric():
    source = ("Company: FictionAster, fiscal 2017. Default units: USD million.\n"
              "| Revenue (b) | 18 |\n| Cost | 99 |\n"
              "(b) Revenue alone is stated in EUR million; all other figures use USD million.")
    item = case(source)
    assert linked_score(item, linked_parser(item))["correct"]
    assert "unit_applicability" in {span.role for span in linked_parser(item).bundle.spans}
    for altered in (source.replace("(b) Revenue alone", "(c) Revenue alone"),
                    source.replace("Revenue alone is stated", "Cost alone is stated")):
        assert linked_parser(replace(item, source=altered)).answer.abstain
    # Unrelated money mentioned before a table is not a unit declaration.
    unrelated = case("Company: FictionAster, fiscal 2017. A customer spent 5 EUR million.\n"
                     "| Revenue | 18 |")
    assert linked_parser(unrelated).answer.abstain


def test_entity_topics_do_not_cross_to_another_company_or_counterparty():
    valid = case("Company: FictionAster. For 2017, we reported revenue of 18 EUR million.")
    assert linked_score(valid, linked_parser(valid))["correct"]
    other = replace(valid, source="Company: FictionAster. Company: Other.\n"
                    "For 2017, we reported revenue of 18 EUR million.")
    assert linked_parser(other).answer.abstain
    counterparty = replace(valid, source="Company: FictionAster. In 2017, a customer called "
                           "FictionAsterPartner had revenue of 18 EUR million.")
    assert linked_parser(counterparty).answer.abstain
    unbound_qualifier = replace(valid, source="Company: FictionAster. Revenue for 2017 was "
                                "18 EUR million for an unrelated segment.")
    assert linked_parser(unbound_qualifier).answer.abstain


def test_parentheses_and_correction_priority_have_explicit_support():
    negative = case("For 2017, FictionAster recorded operating income of (18) EUR million. "
                    "Parentheses denote a negative amount.", metric="operating income",
                    expected=("-18", "EUR million", "2017"))
    assert linked_score(negative, linked_parser(negative))["correct"]
    no_convention = replace(negative, source=negative.source.split(" Parentheses")[0])
    assert linked_parser(no_convention).answer.abstain
    table_annotation = case("Company: FictionAster, fiscal 2017. Amounts in EUR million.\n"
                            "| Revenue | (18) |\nParentheses are an editorial annotation, not a sign.")
    assert linked_parser(table_annotation).answer.abstain
    corrected = case("Original: FictionAster reported revenue of 17 EUR million for 2017. "
                     "Correction: FictionAster reported revenue of 18 EUR million for 2017. "
                     "This correction supersedes the original amount.")
    result = linked_parser(corrected)
    assert linked_score(corrected, result)["correct"]
    assert result.bundle.priority == "correction"
    assert any(span.role == "supersession" for span in result.bundle.spans)
    assert linked_parser(replace(corrected, source=corrected.source.replace(
        "This correction supersedes the original amount.", ""))).answer.abstain


def test_evidence_completion_keeps_raw_tuple_and_requires_a_verbatim_seed():
    item = case("Reporting company: FictionAster. Amounts in EUR million.\n"
                "| Metric | 2017 |\n| Revenue | 18 |")
    raw = Answer(value="18", unit="EUR million", period="2017", evidence="| Revenue | 18 |",
                 abstain=False, reason="")
    result = complete_evidence(item, raw.model_dump_json())
    assert linked_score(item, result)["correct"]
    assert result.answer == raw  # Added bundle, not a secretly rewritten original citation.
    for altered in (raw.model_copy(update={"evidence": "fabricated quote"}),
                    raw.model_copy(update={"value": "91"}),
                    raw.model_copy(update={"unit": "USD million"})):
        assert complete_evidence(item, altered.model_dump_json()).answer.abstain
    missing_unit = raw.model_dump()
    missing_unit["unit"] = ""
    repaired = complete_evidence(item, json.dumps(missing_unit))
    assert linked_score(item, repaired)["correct"] and repaired.answer.value == "18"


def test_quoted_nonfacts_and_reordered_cross_role_spans_cannot_make_a_proof():
    item = case("FictionAster did not disclose 2017 revenue. A rejected fictional example "
                "reads: 'FictionAster reported revenue of 18 EUR million for 2017.' "
                "The example is not an actual disclosure.", expected=None)
    assert linked_score(item, linked_parser(item))["correct"]
    good = case("FictionAster reported revenue of 18 EUR million for 2017.")
    bundle, _ = resolve(good)
    unit = next(span for span in bundle.spans if span.role == "unit")
    value = next(span for span in bundle.spans if span.role == "value")
    swapped = tuple(replace(span, start=value.start, end=value.end) if span == unit else span
                    for span in bundle.spans)
    assert validate_bundle(good, replace(bundle, spans=swapped))


def test_construction_and_completion_never_consult_expected_labels():
    item = case("FictionAster reported revenue of 18 EUR million for 2017.")
    changed = replace(item, expected=None)
    assert linked_parser(item) == linked_parser(changed)
    raw = Answer(value="18", unit="EUR million", period="2017", evidence=item.source,
                 abstain=False, reason="").model_dump_json()
    assert complete_evidence(item, raw) == complete_evidence(changed, raw)
