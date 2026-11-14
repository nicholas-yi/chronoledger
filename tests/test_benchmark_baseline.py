from dataclasses import replace

from asof.benchmark_baseline import TableInput, predict_table


def _input(question):
    return TableInput(question, (("Metric", "2019", "2018"), ("sales", "20", "10")),
                      ("All amounts in millions.",))


def test_lookup_difference_percentage_and_units_are_question_based():
    result = predict_table(_input("What were sales in 2019?"))
    assert result.answer == "20" and result.scale == "million"
    assert predict_table(_input("What is the change in sales from 2018 to 2019?")).answer == "10"
    result = predict_table(_input("What is the percentage change in sales from 2018 to 2019?"))
    assert result.answer == "100" and result.scale == "percent"
    assert predict_table(_input("What is the average sales in 2018 and 2019?")).answer == "15"


def test_ambiguity_unsupported_text_and_zero_division_abstain_not_guess():
    assert predict_table(_input("What is the business outlook?")).answer is None
    tied = replace(_input("What were sales in 2019?"),
                   table=(("Metric", "2019", "2018"), ("sales", "20", "10"),
                          ("sales", "30", "20")))
    assert predict_table(tied).reason == "ambiguous_row_mapping"
    zero = replace(_input("What is the percentage change in sales from 2018 to 2019?"),
                   table=(("Metric", "2019", "2018"), ("sales", "20", "0")))
    assert predict_table(zero).reason == "zero_percentage_denominator"
    mixed = replace(_input("What were sales in 2019?"),
                    paragraphs=("Amounts in millions; other values in billions.",))
    assert predict_table(mixed).reason == "ambiguous_context_units"


def test_zero_and_negative_cells_are_explicit_answers_not_false_abstentions():
    item = replace(_input("What were sales in 2019?"),
                   table=(("Metric", "2019", "2018"), ("sales", "(2)", "0")))
    assert predict_table(item).answer == "-2"
    item = replace(item, question="What were sales in 2018?")
    assert predict_table(item).answer == "0"


def test_average_explicit_range_includes_middle_year_but_listed_endpoints_do_not():
    item = TableInput(
        "What was the average sales between 2017-2019?",
        (("Metric", "2019", "2018", "2017"), ("sales", "30", "15", "0")), ())
    assert predict_table(item).answer == "15"
    assert predict_table(replace(item, question="What was average sales for 2017 and 2019?")).answer == "15"
    item = replace(item, table=(("Metric", "2019", "2018", "2017"), ("sales", "30", "6", "0")))
    assert predict_table(item).answer == "12"
    assert predict_table(replace(item, question="What was average sales for 2017 and 2019?")).answer == "15"
    assert predict_table(replace(item, table=(("Metric", "2019", "2017"), ("sales", "30", "0")))).reason == (
        "average_range_year_not_observed")


def test_weighted_average_metric_and_respectively_are_not_scalar_means():
    item = _input("What was the weighted-average sales in 2018 and 2019, respectively?")
    assert predict_table(item).reason == "average_metric_or_ordered_lookup"


def test_average_signed_expense_ambiguity_abstains_and_table_unit_banner_is_local():
    item = TableInput(
        "What were average service costs for 2008 and 2009?",
        (("Metric", "2009", "2008"), ("Amount", "Amount", "Amount"), ("", "", ""),
         ("", "In thousands", ""), ("service costs", "(30)", "(10)")),
        ("Unrelated amounts in millions.",))
    assert predict_table(item).reason == "average_expense_sign_ambiguous"
    explicit = replace(item, question="What were the average absolute service costs for 2008 and 2009?")
    result = predict_table(explicit)
    assert result.answer == "20" and result.scale == "thousand"
    nonaverage = replace(item, question="What were service costs in 2009?")
    result = predict_table(nonaverage)
    assert result.answer == "-30" and result.scale == "million"  # unchanged non-average behavior
