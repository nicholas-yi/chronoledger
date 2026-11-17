import importlib.util
import json
import sys
from pathlib import Path

import pytest


def test_prior_case_attempt_blocks_before_data_or_worker_access(tmp_path, monkeypatch) -> None:
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("study_kpi_omission", scripts / "study_kpi_omission.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    (tmp_path / "attempt.json").write_text("{}")
    monkeypatch.setattr(module, "PRIVATE", tmp_path)
    monkeypatch.setattr(module, "REPORT", tmp_path / "new_report.json")
    monkeypatch.setattr(module, "WorkerJob", lambda: pytest.fail("must not start"))
    with pytest.raises(FileExistsError, match="already attempted"):
        module.run()
    parts = tmp_path / "case_parts"
    parts.mkdir()
    (parts / "a.json").write_text(json.dumps({"case_id": "a", "candidate_count": 1}))
    (parts / "b.json").write_text("{")
    recovered, issues = module.recover_cases([{"case_id": "a"}, {"case_id": "b"}])
    assert [r["case_id"] for r in recovered] == ["a"]
    assert issues == ["b:truncated_checkpoint"]


def test_insufficient_development_cache_stops_before_body_pinning(tmp_path, monkeypatch) -> None:
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("kpi_guard_test", scripts / "study_kpi_omission.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(module, "PLAN", tmp_path / "plan.json")
    monkeypatch.setattr(module, "inventory", lambda: ({}, [{}] * 29))
    monkeypatch.setattr(module, "pin_filing", lambda *a, **k: pytest.fail("no body pin"))
    with pytest.raises(RuntimeError, match="fewer than30"):
        module.prepare()
