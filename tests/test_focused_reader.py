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


def test_field_challenge_is_fresh_and_shares_a_fixed_comparison_contract(runner):
    runner.select_version("fields")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    values = runner.load_cases(runner.FIXTURE)
    assert len(values) == plan["case_count"] == plan["max_calls"] == 24
    assert all(case.id.startswith("F") for case in values)
    assert plan["evidence_contract"] == "field-record-v1"
    assert runner.REPORT.name == "reader_fields.json" and runner.PRIVATE.name == "reader_fields_v1"
    assert {"src/asof/reader_fields.py", "results/linked_reader.json"} <= set(runner.FROZEN)
    runner.select_version("v1")


def test_reliability_audit_pairs_formats_without_doubling_the_call_budget(runner):
    from asof.reader_reliability import WIRE, generation_orders, reliability_messages

    runner.select_version("reliable")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    values = runner.load_cases(runner.FIXTURE)
    assert len(values) == plan["case_count"] == 12
    assert plan["max_calls"] == 2*len(values) == 24 and plan["offline_cases"] == 24
    assert len({case.category for case in values}) == 6
    assert sum(order[0] == "structured" for order in generation_orders(values).values()) == 6
    assert "results/reader_fields.json" in runner.FROZEN
    from asof.reader_real2_guards import input_fit

    for case in values:
        request = {"model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                   "messages": reliability_messages(case), "options": plan["options"],
                   "format": WIRE.json_schema()}
        assert input_fit(json.dumps(request, sort_keys=True).encode(), plan["options"])[2]
    runner.select_version("v1")


def test_cell_audit_uses_strict_formats_and_source_candidates_within_context_budget(runner):
    from asof.reader_cells import audit_fixture, cell_messages, selection_schema
    from asof.reader_real2_guards import input_fit

    runner.select_version("cells")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    values = runner.load_cases(runner.FIXTURE)
    assert values == audit_fixture()[0] and len(values) == 12
    assert plan["max_calls"] == 24 and plan["offline_cases"] == 192
    assert "results/reader_reliability.json" in runner.FROZEN
    assert all(runner.ROOT.joinpath(*path.split("/")).exists() for path in runner.FROZEN)
    for case in values:
        request = {"model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                   "messages": cell_messages(case), "options": plan["options"],
                   "format": selection_schema(case)}
        assert input_fit(json.dumps(request, sort_keys=True).encode(), plan["options"])[2]
    runner.select_version("v1")


def test_ai_review_is_a_separate_bounded_advisory_profile_with_no_human_replacement(runner):
    from asof.reader_ai_review import (
        compact_cell_messages,
        opinion_schema,
        review_messages,
        review_tasks,
    )
    from asof.reader_cells import selection_schema
    from asof.reader_real2_guards import input_fit

    runner.select_version("ai-review")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    tasks = review_tasks()
    assert len(tasks) == plan["case_count"] == 12 and plan["max_calls"] == 24
    assert plan["wall_seconds"] == 1200 and plan["call_seconds"] == 90
    assert {"results/reader_cell_selection.json", "results/reader_cell_selection_accounting.json"} <= set(runner.FROZEN)
    for task in tasks:
        for reviewing in (False, True):
            options = {**plan["options"], "num_predict": 128 if reviewing else 64}
            body = {
                "model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                "options": options,
                "messages": review_messages(task.case, task.candidate) if reviewing else compact_cell_messages(task.case),
                "format": opinion_schema() if reviewing else selection_schema(task.case),
            }
            assert input_fit(json.dumps(body, sort_keys=True).encode(), options)[2]
    runner.select_version("v1")


def test_decomposed_ai_review_v2_profile_is_new_bounded_and_fits_context(runner):
    from asof.reader_ai_review_v2 import messages, probes, schema
    from asof.reader_real2_guards import input_fit

    runner.select_version("ai-review-v2b")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    stopped = json.loads((runner.ROOT / "results" / "reader_ai_review_v2_plan.json").read_bytes())
    assert {**plan, "study": stopped["study"]} == stopped
    assert runner.REPORT.name == "reader_ai_review_v2b.json" and runner.PRIVATE.name == "reader_ai_review_v2b_v1"
    assert "results/reader_ai_review_v2.json" in runner.FROZEN
    runner.select_version("ai-review-v2")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    assert runner.REPORT.name == "reader_ai_review_v2.json" and runner.PRIVATE.name == "reader_ai_review_v2_v1"
    assert runner.load_cases(runner.FIXTURE) == tuple(probe.task.case for probe in probes())
    assert plan["case_count"] == plan["max_calls"] == 18 and plan["call_seconds"] == 90
    assert "results/reader_ai_review.json" in runner.FROZEN
    assert all(runner.ROOT.joinpath(*path.split("/")).exists() for path in runner.FROZEN)
    for probe in probes():
        body = {"model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                "options": plan["options"], "messages": messages(probe.task), "format": schema(probe.task)}
        assert input_fit(json.dumps(body, sort_keys=True).encode(), plan["options"])[2]
    runner.select_version("v1")


def test_fresh_v3_review_arms_share_one_frozen_fixture_and_fit_context(runner):
    from asof.reader_ai_review_v3 import ARMS, load_probes
    from asof.reader_real2_guards import input_fit

    plans = {}
    for version, arm in (("ai-review-v3", "blind_extraction_v3"), ("ai-review-v3-control", "decomposed_v2_control")):
        runner.select_version(version)
        plan = json.loads(runner.PLAN.read_bytes())
        runner.validate_plan(plan)
        plans[version] = plan
        assert runner.FIXTURE.name == "reader_ai_review_v3.json"
        assert all(runner.ROOT.joinpath(*path.split("/")).exists() for path in runner.FROZEN)
        probes = load_probes(runner.FIXTURE)
        assert runner.load_cases(runner.FIXTURE) == tuple(probe.task.case for probe in probes)
        assert plan["case_count"] == plan["max_calls"] == len(probes) == 24
        for probe in probes:
            body = {"model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                    "options": plan["options"], "messages": ARMS[arm].messages(probe.task),
                    "format": ARMS[arm].schema(probe.task)}
            assert input_fit(json.dumps(body, sort_keys=True).encode(), plan["options"])[2]
    first, second = plans.values()
    assert {**first, "study": "", "generation_contract": ""} == {**second, "study": "", "generation_contract": ""}
    runner.select_version("v1")


def test_round4_pipeline_profile_reuses_the_unchanged_v2_reviewer_on_new_probes(runner):
    from asof.reader_ai_review_v3 import ARMS, load_probes
    from asof.reader_real2_guards import input_fit

    runner.select_version("ai-review-v4")
    plan = json.loads(runner.PLAN.read_bytes())
    runner.validate_plan(plan)
    assert runner.FIXTURE.name == "reader_ai_review_v4.json" and runner.REPORT.name == "reader_ai_review_v4.json"
    assert {"src/asof/review_pipeline.py", "results/reader_ai_review_v3_rules.json"} <= set(runner.FROZEN)
    assert all(runner.ROOT.joinpath(*path.split("/")).exists() for path in runner.FROZEN)
    probes = load_probes(runner.FIXTURE)
    assert plan["case_count"] == plan["max_calls"] == len(probes) == 24
    arm = ARMS["decomposed_v2_control"]
    for probe in probes:
        body = {"model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                "options": plan["options"], "messages": arm.messages(probe.task), "format": arm.schema(probe.task)}
        assert input_fit(json.dumps(body, sort_keys=True).encode(), plan["options"])[2]
    runner.select_version("v1")


def test_round5_pipeline_halves_cover_all_probes_once_within_the_call_ceiling(runner):
    from asof.reader_ai_review_v3 import load_probes
    from asof.reader_real2_guards import input_fit
    from asof.review_pipeline_v2 import request, start_entry

    covered = []
    for version in ("pipeline-v5a", "pipeline-v5b"):
        runner.select_version(version)
        plan = json.loads(runner.PLAN.read_bytes())
        runner.validate_plan(plan)
        assert runner.FIXTURE.name == "review_pipeline_v5.json"
        assert all(runner.ROOT.joinpath(*path.split("/")).exists() for path in runner.FROZEN)
        part = load_probes(runner.FIXTURE, 30)[slice(*plan["case_slice"])]
        covered.extend(probe.task.case.id for probe in part)
        worst = sum(0 if start_entry(probe)["decided_by"] else (1 if probe.task.candidate.abstain else 2)
                    for probe in part)
        assert worst <= plan["max_calls"]
        for probe in part:
            for step in ("disclosure",) if probe.task.candidate.abstain else ("value", "disclosure"):
                body = {"model": plan["model"], "stream": False, "think": False, "keep_alive": "20m",
                        "options": plan["options"], "messages": request(probe.task, step)["messages"],
                        "format": request(probe.task, step)["format"]}
                assert input_fit(json.dumps(body, sort_keys=True).encode(), plan["options"])[2]
    assert len(covered) == len(set(covered)) == 30
    runner.select_version("v1")
