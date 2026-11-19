import importlib.util
import json
import multiprocessing
import socket
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from asof.focused_reader import (
    Answer,
    Case,
    CompactCritique,
    Critique,
    abstention,
    account_incomplete_attempts,
    choose_final,
    development_lessons,
    grounded,
    messages,
    parser_answer,
    promotion_gate,
    score,
    summarize,
    verified_error_bank,
)


def cases():
    payload = json.loads((Path(__file__).parent / "fixtures" / "focused_reader.json").read_text())
    return [Case(**{**row, "split": split,
                    "expected": tuple(row["expected"]) if row["expected"] else None})
            for split, rows in payload.items() for row in rows]


def test_task_parser_source_evidence_and_unanswerable_truth_are_distinct():
    values = cases()
    assert score(values[0], parser_answer(values[0]))["correct"]
    assert parser_answer(values[5]).abstain  # unresolved conflict, not choose-first
    assert parser_answer(values[6]).abstain  # wording outside the narrow parser grammar
    assert not score(values[6], parser_answer(values[6]))["correct"]
    misleading = Answer.model_validate(values[2].probe)
    assert grounded(values[2], misleading) == ()
    assert not score(values[2], misleading)["correct"]  # industry number passes token checks
    assert all(not score(case, Answer.model_validate(case.probe))["correct"] for case in values[:6])


def test_missing_or_invalid_responses_are_not_converted_to_successful_abstentions():
    case = cases()[-1]
    with pytest.raises(ValidationError):
        Answer.model_validate_json('{"abstain":true}')
    assert not score(case, None)["correct"]
    assert score(case, abstention("missing_metric"))["correct"]
    summary = summarize(cases(), {})
    assert summary["evaluation"]["single_pass"]["recorded_cases"] == 0
    assert summary["evaluation"]["single_pass"]["accuracy_all_planned"] == 0


def test_grounding_rejects_bad_quote_period_units_and_does_not_consult_gold_for_rollback():
    case = cases()[0]
    initial = parser_answer(case)
    for fields in ({"evidence": "not in source"}, {"unit": "EUR million"},
                   {"period": "2015"}, {"value": "999"}):
        bad = initial.model_copy(update=fields)
        assert grounded(case, bad)
        selected, reason = choose_final(case, initial, bad)
        assert selected == initial and reason == "retained_initial_no_verified_revision"
    # Wrong year/value association can pass necessary checks: do NOT silently use gold to undo it.
    plausible_wrong = Answer.model_validate(case.probe)
    chosen, _ = choose_final(case, initial, plausible_wrong)
    assert chosen == plausible_wrong and not score(case, chosen)["correct"]
    assert choose_final(case, None, None)[0].abstain


def test_model_messages_exclude_gold_probe_and_split_and_critic_errors_are_explicit():
    case = cases()[0]
    for stage in ("generate", "judge", "revise"):
        payload = json.loads(messages(case, stage, draft="{}", critique="{}")[-1]["content"])
        assert not {"expected", "probe", "split", "category"} & payload.keys()
    with pytest.raises(ValidationError):
        Critique(verdict="accept", issues=["wrong_unit"], feedback="fix")
    with pytest.raises(ValidationError):
        Critique(verdict="revise", issues=[], feedback="")
    with pytest.raises(ValueError, match="actual draft"):
        messages(case, "judge")


def test_error_bank_and_adaptation_cannot_consume_evaluation_or_judge_pseudo_gold():
    values = cases()
    records = {case.id: {"single_pass": {"answer": None, "score": score(case, None)}}
               for case in values}
    errors = verified_error_bank(values, records)
    assert len(errors) == 6 and all(item["case_id"].startswith("D") for item in errors)
    lessons = development_lessons(errors)
    assert len(lessons) == 6
    with pytest.raises(ValueError, match="machine-verified"):
        development_lessons([{**errors[0], "verifier": "model_judge"}])
    with pytest.raises(ValueError, match="machine-verified"):
        development_lessons([{**errors[0], "case_id": "E01"}])
    assert not promotion_gate(values, records, independent_audit=True)["promote"]
    assert development_lessons([]) == ()


@pytest.fixture
def runner(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("run_focused_reader", scripts / "run_focused_reader.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_model_runner_requires_frozen_plan_explicit_execution_and_never_implicit_resume(
    runner, tmp_path, monkeypatch,
):
    plan = json.loads(runner.PLAN.read_bytes())
    plan["max_calls"] = 37
    with pytest.raises(ValueError, match="approved fixed allocation"):
        runner.validate_plan(plan)
    with pytest.raises(SystemExit):
        runner.main([])
    (tmp_path / "attempt.json").write_text("{}")
    monkeypatch.setattr(runner, "PRIVATE", tmp_path)
    monkeypatch.setattr(runner, "freeze_receipt", lambda: pytest.fail("no source/model access"))
    with pytest.raises(FileExistsError, match="no automatic retry"):
        runner.run()


def test_model_worker_cannot_launch_before_containment_gate(runner):
    parent, child = multiprocessing.Pipe()
    try:
        parent.send("not-the-controller")
        with pytest.raises(RuntimeError, match="containment handshake"):
            runner.worker({}, child)
    finally:
        parent.close()
        child.close()


def test_stopped_attempts_are_not_reported_as_never_attempted_or_zero_cost():
    values = cases()
    records = account_incomplete_attempts(values, {}, [
        {"case_id": "E01", "stage": "generate"}, {"case_id": "E01", "stage": "judge"}])
    assert records["E01"]["single_pass"]["score"]["outcome"] == "invalid_response"
    assert records["E01"]["judge_assisted"]["answer"] is None
    result = summarize(values, records)["evaluation"]["judge_assisted"]
    assert result["recorded_cases"] == result["missing_latency_records"] == 1
    assert result["outcomes"] == {"invalid_response": 1, "not_attempted": 5}


def test_port_preflight_uses_exclusive_os_binding_not_absent_listener_http(runner):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        with pytest.raises(RuntimeError, match="port is unavailable"):
            runner.require_free_port(port)
    runner.require_free_port(port)


def test_compact_critic_cannot_emit_freeform_feedback_or_unbounded_codes():
    raw = CompactCritique(verdict="revise", issues=["wrong_period", "wrong_unit"])
    expanded = raw.expanded()
    assert expanded.issues == ["wrong_period", "wrong_unit"]
    assert "reporting year" in expanded.feedback and "currency" in expanded.feedback
    assert CompactCritique(verdict="accept", issues=[]).expanded().feedback == ""
    for data in (
        {"verdict": "accept", "issues": [], "feedback": "unbounded prose"},
        {"verdict": "revise", "issues": []},
        {"verdict": "accept", "issues": ["wrong_value"]},
        {"verdict": "revise", "issues": ["invented_code"]},
        {"verdict": "revise", "issues": ["wrong_value"] * 2},
        {"verdict": "revise", "issues": ["wrong_value", "wrong_unit", "missing", "ambiguous"]},
    ):
        with pytest.raises(ValidationError):
            CompactCritique.model_validate(data)
    schema = CompactCritique.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["issues"]["maxItems"] == 3


def test_v2_only_changes_critic_messages_and_selects_new_attempt_paths(runner):
    case = cases()[0]
    assert messages(case, "generate") == messages(case, "generate", compact_critic=True)
    assert messages(case, "revise", draft="{}", critique="{}") == messages(
        case, "revise", draft="{}", critique="{}", compact_critic=True)
    assert messages(case, "judge", draft="{}") != messages(
        case, "judge", draft="{}", compact_critic=True)
    old_private, old_report = runner.PRIVATE, runner.REPORT
    runner.select_version("v2")
    runner.validate_plan(json.loads(runner.PLAN.read_bytes()))
    assert runner.PRIVATE != old_private and runner.REPORT != old_report
    assert runner.PRIVATE.name == "focused_reader_v2"
    assert "results/focused_reader_v2_plan.json" in runner.FROZEN
    runner.select_version("v1")
    assert runner.PRIVATE == old_private and runner.REPORT == old_report


def test_verifier_run_has_fresh_pairs_and_no_room_for_judge_calls(runner):
    runner.select_version("verifier")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    values = runner.load_cases(runner.FIXTURE)
    assert len(values) == plan["case_count"] == plan["max_calls"] == 24
    assert all(case.split == "evaluation" and case.probe is None for case in values)
    assert runner.REPORT.name == "verified_reader.json"
    assert "results/focused_reader_v2.json" in runner.FROZEN
    runner.select_version("v1")


def test_stress_version_expands_offline_coverage_without_claiming_more_model_calls(runner):
    runner.select_version("stress")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    values = runner.load_cases(runner.FIXTURE)
    assert len(values) == plan["max_calls"] == 24
    assert plan["offline_cases"] == 288 and len({case.category for case in values}) == 12
    assert runner.REPORT.name == "reader_stress.json"
    assert "results/verified_reader.json" in runner.FROZEN
    runner.select_version("v1")


def test_linked_challenge_keeps_old_contracts_and_results_separate(runner):
    runner.select_version("linked")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    values = runner.load_cases(runner.FIXTURE)
    assert len(values) == plan["max_calls"] == 24
    assert sum(case.expected is None for case in values) == 12
    assert runner.REPORT.name == "linked_reader.json"
    assert plan["evidence_contract"] == "linked-evidence-v1"
    assert "results/reader_stress.json" in runner.FROZEN
    runner.select_version("v1")
