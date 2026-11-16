"""Offline recovery of practice-three reporting; never calls a model or scorer."""

import json
from collections import Counter

from run_reader_modes import LOG, paths, practice_predecessor, prior_practice

from asof import ledger
from asof.config import PROJECT_ROOT
from asof.reader_contract import Report
from asof.reader_modes import ADAPTER, resolve_mode
from asof.reader_real2_guards import SustainedCPU


def main() -> None:
    config_path, status_path, private = paths(True, 3)
    config, receipt = json.loads(config_path.read_text()), json.loads(status_path.read_text())
    if "operational_gate" in receipt or sum(len(r["calls"]) for r in receipt["items"]) != 3:
        raise RuntimeError("expected only the three generated, unfinalized practice calls")
    original = status_path.read_bytes()
    interrupted = status_path.with_name("reader_modes_practice_3_interrupted.json")
    if interrupted.exists():
        raise RuntimeError("recovery already attempted")
    interrupted.write_bytes(original)
    reports = {r["id"]: Report.model_validate(r["report"]) for r in config["items"]}
    for row in receipt["items"]:
        call = row["calls"][0]
        path = private / f"{row['id']}_True_answer.json"
        if ledger.file_sha256(path) != call["raw_SHA256"] or row["outcome"] != "practice_path_valid":
            raise ValueError("raw call or stored path differs")
        raw = json.loads(path.read_text())
        values, computed = resolve_mode(ADAPTER.validate_json(raw["message"]["content"]),
                                        reports[row["id"]])
        if values != row["values"] or computed != row["computed_by_code"]:
            raise ValueError("offline parse/resolve differs; do not repair item")
    prior = practice_predecessor(prior_practice(), 3)
    if not all(r.get("schema_valid") for r in prior["items"] if r["constrained"]):
        raise ValueError("prior mode grammar path unavailable")
    if not {"difference", "average", "ratio"} <= set(prior["code_path_operations"]) or not any(
        r.get("operation") == "percent_change" and r["computed_by_code"] for r in receipt["items"]
    ):
        raise ValueError("required calculator smoke paths not observed")
    policy = SustainedCPU()
    for line in (private / "CPU_trace.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["phase"] == "generation" and not policy.active:
            policy.activate()
        policy.add(row["start_seconds"], row["end_seconds"], row["host_CPU_percent"],
                   row["timestamp_UTC"])
    changed = {p: ledger.file_sha256(PROJECT_ROOT / p)
               for p, h in config["source_sha256"].items()
               if ledger.file_sha256(PROJECT_ROOT / p) != h}
    if set(changed) != {r"scripts\run_reader_modes.py"}:
        raise ValueError("only the runner's reporting fix may differ")
    receipt.update(status="complete_offline_reporting_recovery", attempts=3, items_attempted=3,
        stop_reason="post_generation_reporting_KeyError_recovered_offline",
        source_and_config_unchanged_during_generation=True,
        source_and_config_unchanged=False, operational_gate=True,
        outcomes=dict(Counter(r["outcome"] for r in receipt["items"])),
        code_path_operations={"percent_change": 1}, CPU_summary=policy.summary(),
        resources={"wall_seconds": None, "Python_CPU_seconds": None,
                   "owned_RSS_peak_sample_bytes": None,
                   "note": "Final timer/memory summaries lost in reporting exception. "
                           "Per-call durations and persisted CPU trace remain; no guard trip/sleep. "
                           "Do not replace missing peak or CPU measurements with current samples."},
        warning="Practice only. No native score/accuracy, prediction repair or new generation.")
    recovery = {
        "kind": "OFFLINE REPORTING RECOVERY ONLY",
        "interrupted_receipt": str(interrupted.relative_to(PROJECT_ROOT)),
        "interrupted_SHA256": ledger.file_sha256(interrupted),
        "reporting_only_source_after": changed,
        "source_before": {p: config["source_sha256"][p] for p in changed},
        "cause": "Finalizer selected current iteration3 partial receipt as predecessor, "
                 "then accessed its not-yet-written code_path_operations. "
                 "Fixed by selecting iteration-1 explicitly; regression test added.",
        "generation_request_prompt_schema_options_parser_calculator_changed_by_fix": False,
        "raw_item_records_changed": False, "new_model_calls": 0, "native_scores": 0,
        "actual_total_practice_calls": 40,
        "resource_limitations": receipt["resources"],
    }
    (PROJECT_ROOT / "results" / "reader_modes_practice_3_recovery.json").write_text(
        json.dumps(recovery, indent=2), encoding="utf-8")
    status_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    history = prior_practice()
    LOG.write_text(json.dumps({
        "kind": "PRACTICE ONLY, NEVER ACCURACY",
        "iterations": [{
            "iteration": r["iteration"], "attempts": r["attempts"],
            "change": json.loads(paths(True, r["iteration"])[0].read_text())["change"],
            "outcomes": r["outcomes"], "operational_gate": r["operational_gate"],
            "constrained_schema_valid": sum(bool(x.get("schema_valid")) for x in r["items"]
                                             if x["constrained"]),
            "constrained_mode_first": sum(bool(x.get("mode_first")) for x in r["items"]
                                           if x["constrained"]),
            "unconstrained_disallowed_mode_observed": sum(
                bool(x.get("disallowed_mode_observed")) for x in r["items"]
                if not x["constrained"]),
            "config_sha256": r["config_sha256"]} for r in history],
        "total_calls": sum(r["attempts"] for r in history),
        "recovery": "Iteration3 summary recovered offline; original interrupted receipt retained.",
    }, indent=2), encoding="utf-8")
    print(json.dumps({"practice_calls": 40, "operational_gate": True,
                      "new_calls_in_recovery": 0}))


if __name__ == "__main__":
    main()
