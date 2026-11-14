import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest

from asof.benchmark_adapters import finqa_input, finqa_program
from asof.benchmark_baseline import BaselineAnswer, TableInput
from asof.benchmark_reporting import wilson95


def test_finqa_adapter_only_reads_raw_inputs_not_gold_or_retrieved_fields():
    class NoGold(dict):
        def __getitem__(self, key):
            assert key == "question"
            return super().__getitem__(key)

    record = {"qa": NoGold(question="What is the change in sales from 2018 to 2019?"),
              "table": [["Metric", "2019", "2018"], ["sales", "20", "10"]],
              "pre_text": [], "post_text": [], "model_input": "not_used"}
    item = finqa_input(record)
    result = finqa_program(item, BaselineAnswer("10", "", "two_year_difference"))
    assert result.tokens == ("subtract(", "20", "10", ")", "EOF")
    assert result.expected_answer == 10
    result = finqa_program(item, BaselineAnswer("100", "percent", "percentage_change"))
    assert result.tokens == ("subtract(", "20", "10", ")", "divide(", "#0", "10", ")", "EOF")
    assert result.expected_answer == 1


def test_finqa_v1_average_keeps_two_explicit_endpoints_even_if_a_middle_year_exists():
    item = TableInput("What is average sales from 2017 to 2019?",
                      (("Metric", "2019", "2018", "2017"), ("sales", "30", "12", "10")), ())
    result = finqa_program(item, BaselineAnswer("20", "", "two_year_average"))
    assert result.tokens == ("add(", "10", "30", ")", "divide(", "#0", "const_2", ")", "EOF")
    assert finqa_program(item, BaselineAnswer(None, "", "unsupported")).tokens is None
    percent = replace(item, question="What were sales in 2019?",
                      table=(("Metric", "2019"), ("sales", "15%")))
    result = finqa_program(percent, BaselineAnswer("15", "percent", "unique_row_year_lookup"))
    assert result.tokens == ("add(", "15%", "const_0", ")", "EOF")
    assert result.expected_answer == 0.15


def test_wilson_descriptive_interval_handles_small_support_and_invalid_denominators():
    lo, hi = wilson95(5, 30)
    assert lo == pytest.approx(0.0734, abs=0.0001)
    assert hi == pytest.approx(0.3356, abs=0.0001)
    assert wilson95(0, 0) is None
    assert wilson95(0, 10)[1] > 0.25
    with pytest.raises(ValueError):
        wilson95(11, 10)


def test_paired_scope_guard_rejects_changes_outside_average_rule(monkeypatch, tmp_path):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "run_tatqa_average_comparison", scripts / "run_tatqa_average_comparison.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old, new = tmp_path / "old.py", tmp_path / "new.py"
    old.write_text('x=1\nif "average" in question:\n    value=2\nelse:\n    value=3\n')
    new.write_text('x=1\nif "average" in question:\n    value=4\nelse:\n    value=3\n')
    module.assert_average_only(old, new)
    new.write_text('x=9\nif "average" in question:\n    value=4\nelse:\n    value=3\n')
    with pytest.raises(ValueError, match="outside"):
        module.assert_average_only(old, new)
