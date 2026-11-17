import importlib.util
import json
import multiprocessing
import sys
from pathlib import Path

import pytest


@pytest.fixture
def runner(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "validate_quant_frontiers", scripts / "validate_quant_frontiers.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("change", ["seed", "cases_per_area", "binary_horizon"])
def test_changed_allocation_is_rejected_without_drawing(runner, change) -> None:
    plan = json.loads(runner.PLAN.read_bytes())
    plan[change] += 1
    with pytest.raises(ValueError, match="frozen approved allocation"):
        runner.validate_plan(plan)


def test_prior_attempt_blocks_before_source_or_launch(runner, monkeypatch, tmp_path) -> None:
    marker = tmp_path / "attempt.json"
    marker.write_text("{}")
    monkeypatch.setattr(runner, "ATTEMPT", marker)
    monkeypatch.setattr(runner, "freeze_receipt", lambda: pytest.fail("no source read"))
    with pytest.raises(FileExistsError, match="no retry"):
        runner.main(["--execute"])


def test_worker_rejects_missing_controller_gate_before_any_rng_import(runner) -> None:
    parent, child = multiprocessing.Pipe()
    try:
        parent.send("not-the-controller")
        with pytest.raises(RuntimeError, match="handshake"):
            runner.worker({}, child)
    finally:
        parent.close()
        child.close()


def test_guard_failure_is_recorded_and_cannot_auto_retry(runner, monkeypatch, tmp_path) -> None:
    plan = json.loads(runner.PLAN.read_bytes())
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(runner, "PLAN", path)
    monkeypatch.setattr(runner, "ATTEMPT", tmp_path / "attempt.json")
    monkeypatch.setattr(runner, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(runner, "freeze_receipt", lambda: {"source_SHA256": {}})
    monkeypatch.setattr(runner, "source_hashes", dict)
    monkeypatch.setattr(runner, "resident_bytes", lambda: 1024)
    for key in runner.THREAD_VARIABLES:
        monkeypatch.setenv(key, "1")

    def denied(**kwargs):
        raise OSError("fixture guard denied")

    monkeypatch.setattr(runner, "WorkerJob", denied)
    assert runner.main(["--execute"]) == 2
    receipt = json.loads(runner.REPORT.read_bytes())
    assert receipt["status"] == "stopped" and not receipt["synthetic_QA_passed"]
    assert "fixture guard denied" in receipt["stop_reason"]
    assert receipt["unreported_work_unknown_if_stopped"]
    with pytest.raises(FileExistsError, match="no retry"):
        runner.main(["--execute"])


def test_frozen_matching_allows_only_git_line_endings(runner, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "FROZEN", ("source.py",))
    (tmp_path / "source.py").write_bytes(b"pass\r\n")

    def git(args, **kwargs):
        return b"" if "status" in args else b"pass\n" if "show" in args else b"fake-sha\n"

    monkeypatch.setattr(runner.subprocess, "check_output", git)
    assert runner.freeze_receipt()["git_commit"] == "fake-sha"
    (tmp_path / "source.py").write_bytes(b"raise RuntimeError\n")
    with pytest.raises(RuntimeError, match="differs"):
        runner.freeze_receipt()


def test_owned_job_rejects_invalid_memory_before_os_access(runner) -> None:
    with pytest.raises(ValueError, match="positive byte"):
        runner.WorkerJob(memory_bytes=0)
