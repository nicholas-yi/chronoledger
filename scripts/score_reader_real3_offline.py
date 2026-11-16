"""Scoring-only Windows shutdown-check repair; never generates or changes predictions."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess

from run_reader_real3 import (
    ARMS,
    BENCH_ROOT,
    DATASET,
    ROOT,
    ledger,
    load_native,
    native_pins,
    paths,
    report,
    verify,
)


def shutdown_evidence(pid: int) -> dict:
    if type(pid) is not int or pid <= 0:
        raise ValueError("positive_owned_server_PID_required")
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise RuntimeError("PowerShell_required_for_OS_shutdown_evidence")
    command = (
        "$ErrorActionPreference='Stop';"
        "$listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | "
        "Where-Object {$_.LocalPort -eq 11435});"
        "$running=$true;"
        f"try {{[void][System.Diagnostics.Process]::GetProcessById({pid})}}"
        "catch [System.ArgumentException] {$running=$false};"
        f"@{{owned_server_PID={pid};owned_server_running=$running;"
        "isolated_port_listeners=$listeners.Count;checked_UTC=[DateTime]::UtcNow.ToString('o')}"
        "|ConvertTo-Json -Compress"
    )
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", command],
                            check=True, capture_output=True, text=True, timeout=30)
    evidence = json.loads(result.stdout)
    if evidence["owned_server_running"] is not False or evidence["isolated_port_listeners"] != 0:
        raise RuntimeError("owned_generation_service_not_confirmed_stopped")
    return evidence


def score(server_pid: int) -> None:
    cp, sp, private = paths(False, 1)
    target = ROOT / "results" / "reader_real3_report.json"
    if target.exists():
        raise RuntimeError("already_scored_no_overwrite")
    cfg, receipt = json.loads(cp.read_text()), json.loads(sp.read_text())
    if not receipt["generation_closed"] or not receipt["frozen_source_and_config_unchanged"]:
        raise RuntimeError("generation_not_closed_or_integrity_failed")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit_scoring_only_repair_before_gold")
    evidence = shutdown_evidence(server_pid)
    verify(cfg)
    if native_pins() != cfg["native_assets"]:
        raise ValueError("native_pins_changed_before_gold_phase")
    pred_path = private / "predictions.json"
    if ledger.file_sha256(pred_path) != receipt["sealed_predictions_SHA256"]:
        raise ValueError("sealed_predictions_changed")
    predictions = json.loads(pred_path.read_text())
    # Same frozen native scoring/denominators; only the pre-gold shutdown check differs.
    contexts = json.loads(DATASET.read_bytes())
    gold = {q["uid"]: q for c in contexts for q in c["questions"]}
    native = load_native(BENCH_ROOT / "tatqa" / "tatqa_metric.py", "real3_native_scoring")
    rows = json.loads(json.dumps(receipt["items"]))
    for row in rows:
        uid, annotation = row["id"], gold[row["id"]]
        row["answer_type"] = annotation["answer_type"]
        for arm in ARMS:
            value = row[arm]
            value.update(native_EM=0, native_F1=0, native_scale_accuracy=0)
            if value["outcome"] == "answered":
                answer, scale = predictions[uid][arm]
                scorer = native.TaTQAEmAndF1()
                scorer(ground_truth=annotation, prediction=answer, pred_scale=scale)
                detail = scorer.get_raw()[-1]
                value.update(native_EM=detail["em"], native_F1=detail["f1"],
                             native_scale_accuracy=int(scale == annotation["scale"]),
                             outcome="correct" if detail["em"] == 1 else "wrong")
    output = {"status": receipt["status"], "items": rows, "report": report(rows),
              "generation_receipt_SHA256": ledger.file_sha256(sp),
              "sealed_predictions_SHA256": receipt["sealed_predictions_SHA256"],
              "config_SHA256": ledger.file_sha256(cp),
              "resources": receipt["resources"], "CPU_summary": receipt["CPU_summary"],
              "scoring_only_amendment": {
                  "cause": "Original1sTCPprobe timed out on Windows after OS listener/PID absence; "
                           "it stopped BEFORE gold access. No metric/prediction was produced then.",
                  "change": "Require direct OS listener+specific ownedPID evidence instead of "
                            "ambiguous TCP negative. Frozen runner/logic/mapping/config unchanged; "
                            "same native scorer and report functions, no new generation/rescore.",
                  "shutdown_evidence": evidence,
                  "offline_entry_SHA256": ledger.file_sha256(__file__),
              }}
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["report"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-pid", type=int, required=True)
    args = parser.parse_args()
    score(args.server_pid)
