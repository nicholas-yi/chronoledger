import json

import pytest

from asof.reader_real3_data import ARMS, blind_inputs, report


def test_blind_projection_does_not_retain_gold_or_support_annotations(tmp_path):
    p = tmp_path / "synthetic.json"
    p.write_text(json.dumps([{"table": {"table": [["Label","Year"],["Units","12"]]},
        "paragraphs": [{"text":"A fictional source."}],
        "questions": [{"uid":"synthetic","question":"What units?","answer":"GOLD_ONLY",
                       "answer_type":"count","scale":"million","derivation":"GOLD_ONLY"}]}]))
    values = blind_inputs(p)
    assert values["synthetic"].question == "What units?"
    assert "GOLD_ONLY" not in repr(values)


def test_all30_denominators_pairing_and_empty_type_groups():
    rows = []
    for i in range(30):
        row = {"id":str(i),"answer_type":"span"}
        for arm in ARMS:
            right = (i < 9 if arm == ARMS[0] else i < 6)
            row[arm] = {"outcome":"correct" if right else "abstain",
                        "native_EM":int(right),"native_F1":int(right),
                        "native_scale_accuracy":int(right),"attempted":True,
                        "abstention_source":None if right else "system"}
        rows.append(row)
    r = report(rows)
    assert r["arms"][ARMS[0]]["native_EM"] == 9/30
    assert r["paired_all30"]["right_only_with_A"] == 3
    assert r["paired_all30"]["both_right"] == 6
    assert r["by_answer_type"]["count"][ARMS[0]]["native_EM"] is None
    with pytest.raises(ValueError):
        report(rows[:-1])


def test_score_command_refuses_gold_phase_before_generation_closes(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("real3_blind_phase", scripts / "run_reader_real3.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config, state = tmp_path / "config.json", tmp_path / "state.json"
    config.write_text("{}")
    state.write_text(json.dumps({"generation_closed":False,"frozen_source_and_config_unchanged":True}))
    monkeypatch.setattr(module, "paths", lambda *args: (config, state, tmp_path))
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "DATASET", tmp_path / "absent_gold.json")
    with pytest.raises(RuntimeError, match="generation_not_closed"):
        module.score()
