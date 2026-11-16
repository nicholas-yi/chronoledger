import json

import pytest
from pydantic import ValidationError

from asof.reader_columns import ColumnReport, answer_body, mode_body, resolve_content
from asof.reader_contract import Row


def column_value(label, value):
    return {"row_label": "Depot", "column_label": label, "unit": "text", "value": value}


def test_non_temporal_column_labels_are_literal_locations_not_missing_periods():
    r = ColumnReport(question="invented", monetary_banner="",
        rows=[Row(label="Depot", unit="text", values={"North":"Crimson Jetty","South":"Gold Knoll"})])
    schema = answer_body(r, "multi_value", "toy", {})["format"]
    props = schema["$defs"]["ColumnOperand"]["properties"]
    assert "period" not in props and props["column_label"]["enum"] == ["NOT_PRESENT","North","South"]
    raw = {"mode": "multi_value", "values": [
        column_value("North", "Crimson Jetty"), column_value("South", "Gold Knoll")],
        "answer_dimension": "text"}
    mode, result = resolve_content(json.dumps(raw), r)
    assert mode == "multi_value" and result.values == ["Crimson Jetty","Gold Knoll"]
    raw["values"][0]["period"] = raw["values"][0].pop("column_label")
    with pytest.raises(ValidationError):
        resolve_content(json.dumps(raw), r)


def test_named_arithmetic_uses_generic_column_keys_and_same_calculator():
    r = ColumnReport(question="invented", monetary_banner="million",
        rows=[Row(label="Cost", unit="million", values={"2021":"90","2022":"65"})])
    def op(column, value):
        return {"row_label":"Cost","column_label":column,"unit":"million","value":value}
    _, result = resolve_content(json.dumps({
        "mode":"arithmetic","operation":"difference","start_value":op("2021","90"),
        "end_value":op("2022","65"),"answer_dimension":"money",
    }), r)
    assert result.values == ["-25.00"] and result.computed_by_code


def test_text_spans_require_no_table_metadata_and_are_verified_exactly():
    r = ColumnReport(question="invented", monetary_banner="", rows=[],
                     paragraphs=["The fictional venture names its project Copper Orchard."])
    raw = {"mode":"text_span","spans":[{"paragraph_id":0,"span":"Copper Orchard"}],
           "answer_dimension":"text"}
    _, result = resolve_content(json.dumps(raw), r)
    assert result.values == ["Copper Orchard"] and result.abstention_source is None
    raw["spans"][0]["span"] = "Copper Ocean"
    assert resolve_content(json.dumps(raw), r)[1].decline_reason == "span_not_in_source"
    raw["spans"][0] = {"paragraph_id":"NOT_PRESENT","span":"NOT_PRESENT"}
    assert resolve_content(json.dumps(raw), r)[1].abstention_source == "system"
    sent = json.loads(mode_body(r, "toy", {})["messages"][1]["content"])
    assert sent["paragraphs"] == r.paragraphs and "expected" not in sent


def test_tableless_report_still_has_valid_schema_for_an_incorrect_table_mode():
    r = ColumnReport(question="invented", monetary_banner="", rows=[], paragraphs=["A demo sentence."])
    for mode in ("lookup", "multi_value"):
        schema = answer_body(r, mode, "toy", {})["format"]
        assert schema["properties"]["answer_dimension"]["enum"]
        assert schema["$defs"]["ColumnOperand"]["properties"]["value"]["enum"] == ["NOT_PRESENT"]
