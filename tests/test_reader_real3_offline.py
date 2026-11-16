import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("real3_offline_score",
                                                scripts / "score_reader_real3_offline.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize(("running", "listeners"), [(True,0),(False,1),(False,0)])
def test_shutdown_requires_both_specific_PID_absence_and_listener_absence(monkeypatch, running, listeners):
    m = module(monkeypatch)
    monkeypatch.setattr(m.shutil, "which", lambda name: "synthetic-powershell")
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps({
        "owned_server_running": running, "isolated_port_listeners": listeners})))
    if running or listeners:
        with pytest.raises(RuntimeError, match="not_confirmed_stopped"):
            m.shutdown_evidence(123)
    else:
        assert m.shutdown_evidence(123)["isolated_port_listeners"] == 0


def test_offline_entry_also_refuses_gold_before_closed_generation(tmp_path, monkeypatch):
    m = module(monkeypatch)
    cp, sp = tmp_path / "cfg.json", tmp_path / "status.json"
    cp.write_text("{}")
    sp.write_text(json.dumps({"generation_closed":False,"frozen_source_and_config_unchanged":True}))
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "paths", lambda *a: (cp,sp,tmp_path))
    monkeypatch.setattr(m, "DATASET", tmp_path / "no_gold_file.json")
    with pytest.raises(RuntimeError, match="generation_not_closed"):
        m.score(123)
