import importlib.util
import json
from pathlib import Path

import pytest

from asof.benchmark_baseline import predict_table


def _script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "run_benchmark_diagnostic", scripts / "run_benchmark_diagnostic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selection_is_fixed_uid_sampling_not_answer_or_success_filtering(monkeypatch):
    script = _script(monkeypatch)
    contexts = [{"questions": [{"uid": str(i)} for i in range(40)]}]
    first = script.select_ids(contexts, 30, 2026111403)
    assert len(first) == 30 and len(set(first)) == 30
    assert first == script.select_ids(list(reversed(contexts)), 30, 2026111403)
    with pytest.raises(ValueError, match="unique"):
        script.select_ids([{"questions": [{"uid": "duplicate"}, {"uid": "duplicate"}]}], 2, 1)


def test_gold_fields_never_cross_the_baseline_input_boundary(monkeypatch):
    script = _script(monkeypatch)

    class NoGold(dict):
        def __getitem__(self, key):
            assert key == "question", "gold fields were read before prediction"
            return super().__getitem__(key)

    question = NoGold(question="What were sales in 2019?", answer="not_to_be_read",
                      derivation="not_to_be_read", scale="not_to_be_read")
    context = {"table": {"table": [["Metric", "2019", "2018"], ["sales", "20", "10"]]},
               "paragraphs": [{"text": "Amounts in millions."}]}
    assert predict_table(script.prediction_input(context, question)).answer == "20"


def test_deleted_finqa_quarantine_does_not_block_tatqa_freeze(monkeypatch, tmp_path):
    script = _script(monkeypatch)
    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "QUARANTINE", tmp_path / "deleted.json")
    monkeypatch.setattr(script, "SUMMARY", tmp_path / "years.json")
    monkeypatch.setattr(script, "CONFIG", tmp_path / "config.json")
    monkeypatch.setattr(script, "verified_assets", lambda: {"synthetic": {}})
    monkeypatch.setattr(script, "load_native", lambda *_: None)
    (tmp_path / "years.json").write_text(json.dumps(
        {"item_count": 1, "year_histogram": {"2021": 1}, "nonmatching": 0}))
    (tmp_path / "tatqa").mkdir()
    (tmp_path / "tatqa" / "dev.json").write_text(json.dumps([
        {"questions": [{"uid": str(i)} for i in range(40)]}]))
    script.freeze()
    config = json.loads((tmp_path / "config.json").read_text())
    assert config["tatqa_items"] == 30
    assert config["finqa"]["retained"] is False
    assert config["finqa"]["skip_reason"] == "identity_check_failed_file_deleted"
