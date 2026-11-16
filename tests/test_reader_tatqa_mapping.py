import json

import pytest

from asof.benchmark_baseline import TableInput
from asof.reader_columns import resolve_content
from asof.reader_tatqa_mapping import MappingError, map_input, mapped_mode_body, numeric_cell


def test_source_banner_accounting_numbers_and_all_original_cells_preserved():
    item = TableInput("invented", (("(in thousands)", "East", "West"),
        ("Revenue", "$1,240", "(300)"), ("Revenue", "80", "90")),
        ("A fictional project is called Bronze Orchard.",))
    mapped = map_input(item)
    numeric = [r for r in mapped.report.rows if r.unit == "thousand"]
    assert len({r.label for r in mapped.report.rows}) == len(mapped.report.rows)
    assert list(numeric[0].values.values()) == ["1240", "-300"]
    assert numeric[0].label != numeric[1].label
    payload = json.loads(mapped_mode_body(mapped, "toy", {})["messages"][1]["content"])
    assert payload["original_table"] == [list(row) for row in item.table]
    assert payload["paragraphs"] == list(item.paragraphs)
    assert "expected" not in payload and "answer_type" not in payload


def test_paragraph_spans_and_percent_units_pass_unchanged_reader_logic():
    item = TableInput("invented", (("", "2021", "2022"), ("Margin (%)", "20%", "25%")),
                      ("The fictional material is woven basalt.",))
    mapped = map_input(item)
    assert any(r.unit == "percent" and list(r.values.values()) == ["20", "25"]
               for r in mapped.report.rows)
    _, result = resolve_content(json.dumps({
        "mode": "text_span", "spans": [{"paragraph_id": 0, "span": "woven basalt"}],
        "answer_dimension": "text",
    }), mapped.report)
    assert result.values == ["woven basalt"]
    assert numeric_cell("(1,234.50)") == ("-1234.50", "")


def test_ambiguous_banner_is_explicit_mapping_failure_not_silent_scale_default():
    with pytest.raises(MappingError, match="conflicting"):
        map_input(TableInput("invented", (("(in millions)", "Value"), ("Cost", "8")),
                            ("Other amounts are in thousands.",)))


def test_year_shaped_data_values_are_not_reclassified_as_header_years():
    mapped = map_input(TableInput("invented", (("(in thousands)", "2021", "2022"),
        ("Cost", "2021", "2022")), ()))
    assert any(r.unit == "thousand" and list(r.values.values()) == ["2021","2022"]
               for r in mapped.report.rows)
