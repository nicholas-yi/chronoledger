from asof.claim_verifier import verify_claim
from asof.financial_notation import cardinal_value, notation_fact


def test_cardinals_are_exact_and_bounded():
    assert cardinal_value("one hundred and twenty-five") == 125
    assert cardinal_value("forty two") == 42
    assert cardinal_value("nineteen") == 19
    assert cardinal_value("nine hundred") == 900
    for words in ("hundred", "twenty nineteen", "one one", "ten hundred", "forty-two hundred"):
        assert cardinal_value(words) is None


def test_proof_spans_bind_the_exact_source_tokens():
    source = "Intro. FictionQuill said its top line totalled one hundred and five million U.S. dollars in FY 2016."
    fact = notation_fact(source, "FictionQuill", "revenue", "2016")
    assert (fact.value, fact.unit, fact.method) == ("105", "usd million", "declared_revenue_alias")
    text = {span.role: source[span.start:span.end] for span in fact.spans}
    assert text == {"entity": "FictionQuill", "metric": "top line", "value": "one hundred and five",
                    "unit": "U.S. dollars", "scale": "million", "period": "2016"}


def test_ambiguous_or_unlisted_notation_stays_in_review():
    claim = "FictionQuill's 2016 revenue was 26 GBP million."
    for amount in ("GBP26M", "gbp26m", "\u00a326m", "$26m", "SEK26m", "GBP2,60m", "twenty-six million pounds"):
        assert verify_claim(f"FictionQuill's turnover reached {amount} during FY2016.", claim)["verdict"] == "review"


def test_other_years_are_allowed_but_unparsed_revenue_text_blocks():
    claim = "FictionQuill's 2016 revenue was 26 GBP million."
    years = "FictionQuill's turnover reached GBP26m during FY2016. FictionQuill's turnover was GBP24m in 2015."
    assert verify_claim(years, claim)["verdict"] == "supported"
    for extra in ("Sales were restated.", "FictionQuill's turnover rose in 2017.", "Figures cover nine months."):
        assert verify_claim(f"FictionQuill's turnover reached GBP26m during FY2016. {extra}", claim)["verdict"] == "review"


def test_alias_conflict_with_standard_reader_is_review_not_first_parser_wins():
    claim = "FictionQuill's 2016 revenue was 26 GBP million."
    standard = "FictionQuill reported revenue of 26 GBP million for 2016."
    assert verify_claim(standard, claim)["verdict"] == "supported"
    assert verify_claim(f"{standard} FictionQuill's turnover reached GBP28m during FY2016.", claim)["verdict"] == "review"
    assert verify_claim(f"{standard} FictionQuill's turnover reached GBP26,000k during FY2016.", claim)["verdict"] == "supported"


def test_frozen_notation_challenge_and_metamorphic_grid_stay_exact():
    from asof.notation_challenge import evaluate

    report = evaluate()
    for name, planned in (("challenge", 24), ("grid", 780)):
        block = report[name]
        assert block["planned"] == block["correct"] == planned
        assert block["false_support"] == block["false_contradiction"] == 0
        assert block["resolved_without_valid_proof"] == 0
