import importlib.util
import json
import multiprocessing
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def runner(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("validate_audit_cs", scripts / "validate_audit_cs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_prior_attempt_blocks_before_lineage_or_worker_launch(runner, tmp_path, monkeypatch) -> None:
    marker = tmp_path / "attempt.json"
    marker.write_text("{}")
    monkeypatch.setattr(runner, "ATTEMPT", marker)
    monkeypatch.setattr(runner, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(runner, "frozen_lineage", lambda: pytest.fail("must not start"))
    with pytest.raises(FileExistsError, match="no retry"):
        runner.main([])


def test_unbounded_worker_cannot_start_without_controller(runner) -> None:
    controller, child = multiprocessing.Pipe()
    try:
        controller.send("wrong-gate")
        with pytest.raises(RuntimeError, match="handshake"):
            runner.worker(json.loads(runner.PLAN.read_bytes()), child)
    finally:
        controller.close()
        child.close()


def blocked_worker(ready, gate) -> None:
    ready.set()
    gate.wait()


@pytest.mark.parametrize("change", ["unknown_missingness", "threads", "wall"])
def test_altered_allocation_fails_before_launch(runner, change: str) -> None:
    plan = json.loads(runner.PLAN.read_bytes())
    if change == "unknown_missingness":
        plan["missingness"][0] = "unknown"
    elif change == "threads":
        plan["limits"]["compute_threads"] = 2
    else:
        plan["limits"]["worker_soft_wall_seconds"] = 301
    with pytest.raises(ValueError, match="approved bounded allocation"):
        runner.validate_plan(plan)


@pytest.mark.skipif(os.name != "nt", reason="Windows owned-worker resource backstop")
def test_job_close_terminates_only_the_owned_blocked_worker(runner) -> None:
    job = runner.WorkerJob()
    context = multiprocessing.get_context("spawn")
    ready, gate = context.Event(), context.Event()
    process = context.Process(target=blocked_worker, args=(ready, gate))
    process.start()
    try:
        assert process.pid is not None
        mask = job.attach(process.pid)
        assert mask > 0 and mask & (mask - 1) == 0
        assert ready.wait(timeout=10)
        assert process.is_alive()
        job.close()
        process.join(timeout=10)
        assert not process.is_alive()
        assert not gate.is_set()
    finally:
        job.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        process.close()


def test_guard_failure_keeps_stopped_receipt_and_blocks_retry(runner, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "ATTEMPT", tmp_path / "attempt.json")
    monkeypatch.setattr(runner, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(runner, "FROZEN", ())
    monkeypatch.setattr(runner, "PROTECTED", ())
    monkeypatch.setattr(runner, "frozen_lineage", lambda: {"SHA256": {}})
    for name in runner.THREAD_VARIABLES:
        monkeypatch.setenv(name, "1")

    def denied():
        raise OSError("guard denied")

    monkeypatch.setattr(runner, "WorkerJob", denied)
    assert runner.main([]) == 2
    receipt = json.loads(runner.REPORT.read_bytes())
    assert receipt["status"] == "stopped"
    assert receipt["implementation_QA_screen_passed"] is False
    assert "guard denied" in receipt["stop_reason"]
    with pytest.raises(FileExistsError, match="no retry"):
        runner.main([])
