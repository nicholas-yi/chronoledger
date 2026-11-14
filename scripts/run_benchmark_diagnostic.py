"""One scoped TAT-QA diagnostic; optional FinQA remains unscored when native imports fail."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

from benchmark_downloads import ASSETS, ROOT, file_identity
from calibrate_inference import resident_bytes
from check_finqa_years import QUARANTINE, SUMMARY, check_quarantine

from asof import ledger
from asof.benchmark_baseline import TableInput, predict_table
from asof.config import PROJECT_ROOT

SEED = 2026111403
CONFIG = PROJECT_ROOT / "results" / "benchmark_diagnostic_config.json"
RECEIPT = PROJECT_ROOT / "results" / "benchmark_diagnostic_status.json"
BASELINE = PROJECT_ROOT / "src" / "asof" / "benchmark_baseline.py"
MAX_CPU_SECONDS, MAX_RSS = 780, 1 << 30


def verified_assets() -> dict:
    entries = {}
    for group in ASSETS.values():
        for source, relative, expected in group:
            path = ROOT / relative
            if not path.exists():
                continue
            identity = file_identity(path)
            if identity["git_blob_sha1"] != expected:
                raise ValueError("benchmark asset differs from immutable pin; no parse/import")
            entries[str(relative)] = {"source_path": source, **identity}
    required = [str(relative) for _, relative, _ in ASSETS["tatqa"]]
    if any(name not in entries for name in required):
        raise FileNotFoundError("TAT-QA native/data/licence asset missing")
    return entries


def load_native(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("native scorer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_ids(contexts: list, count: int, seed: int) -> list[str]:
    identifiers = [q["uid"] for context in contexts for q in context["questions"]]
    if any(not isinstance(uid, str) or not uid for uid in identifiers):
        raise ValueError("question identities must be nonempty strings")
    if len(set(identifiers)) != len(identifiers) or len(identifiers) < count:
        raise ValueError("unique question identities and sufficient fixed sample required")
    return random.Random(seed).sample(sorted(identifiers), count)


def prediction_input(context: dict, question: dict) -> TableInput:
    # Only these input fields cross into the baseline; no answer/type/derivation/evidence labels.
    return TableInput(question["question"],
                      tuple(tuple(row) for row in context["table"]["table"]),
                      tuple(p["text"] for p in context["paragraphs"]))


def freeze() -> None:
    verified_assets()
    if QUARANTINE.exists():
        summary, safe = check_quarantine(QUARANTINE)
    else:
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        safe = False
    assets = verified_assets()
    finqa_skip = None
    if not safe:
        finqa_skip = "identity_check_failed_file_deleted"
    else:
        try:
            load_native(ROOT / "finqa" / "evaluate.py", "native_finqa_preflight")
        except ModuleNotFoundError as exc:
            finqa_skip = f"missing_native_dependency:{exc.name}"
    if finqa_skip is None:
        raise RuntimeError("FinQA native dependency status changed: its separate baseline freeze is required")
    load_native(ROOT / "tatqa" / "tatqa_metric.py", "native_tatqa_preflight")
    contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
    config = {
        "kind": "NON-MODEL DEVELOPMENT DIAGNOSTIC; not strategy inference or a trained system",
        "seed": SEED, "tatqa_items": 30, "tatqa_ids": select_ids(contexts, 30, SEED),
        "selection": "Python Random(seed).sample(sorted(all unique dev question UIDs),30); "
                     "no type/answer/success filtering, resampling or training",
        "baseline": "Unique positive row-header token overlap, one/two explicit year columns "
                    "within first3 table rows. Numeric lookup or average/sum/change/"
                    "percentage-change; oldest-to-latest unless explicit from-to. "
                    "Scale from inline cell, per-share exception or unique context unit; "
                    "blank if unmarked. Unsupported/tied/mixed/zero-denominator cases abstain. "
                    "No gold, retrieval labels, embeddings, model or external access.",
        "baseline_file_sha256": ledger.file_sha256(BASELINE),
        "runner_file_sha256": ledger.file_sha256(Path(__file__)),
        "native_metrics": "Unmodified TaTQAEmAndF1 on all30attempted items, including "
                          "abstentions; official EM/F1/scale. No native metric substitute.",
        "native_missing_dependency_policy": "report and do not install/stub/copy around imports",
        "asset_hashes": assets,
        "finqa": {"year_check": summary, "retained": safe, "selected_items": 0,
                  "scored_items": 0, "skip_reason": finqa_skip},
        "resources": {"runner_CPU_seconds": MAX_CPU_SECONDS, "resident_bytes": MAX_RSS,
                      "batch_CPU_minutes": 15, "threads": 1,
                      "note": "Reserve120CPU seconds for intake/checks; cooperative checks, no Docker."},
        "rights": "TAT-QA data CC BY4.0; code MIT copies/licences retained in ignoreddata. "
                  "FinQA repo MIT; underlying report rights limit remains stated.",
        "source_acceptance": "TAT-QA fixed2021dev bytes verified; FinQA committed ID-only "
                             "check before nonidentity fields; all checked years<=2020 required.",
    }
    CONFIG.write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"frozen_selection_items": 30, "seed": SEED,
                      "finqa_selected_items": 0, "finqa_skip": finqa_skip}))


def run() -> None:
    started_cpu, started_wall = time.process_time(), time.monotonic()
    if any(os.environ.get(k) != "1"
           for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("single-thread BLAS flags are required")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("scoring_run_attempted"):
        raise RuntimeError("this diagnostic was already attempted; do not rerun toward preferred results")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit source/config before scoring")
    if (ledger.file_sha256(BASELINE) != config["baseline_file_sha256"]
            or ledger.file_sha256(Path(__file__)) != config["runner_file_sha256"]):
        raise ValueError("baseline/runner changed after freeze")
    assets = verified_assets()
    if assets != config["asset_hashes"]:
        raise ValueError("asset bytes changed after freeze")
    receipt["history"] = [{"status": receipt["status"], "scored_items": 0,
                           "note": "Earlier public-metadata stop; subsequently clarified."}]
    receipt["status"] = "scoring_incomplete"
    receipt["scoring_run_attempted"] = True
    receipt["scope"] = "Thirty native-scored TAT-QA dev items; optional FinQA has no model/scorer substitute."
    outcomes = []
    local_predictions = {}
    peak = 0
    scorer = None
    try:
        native = load_native(ROOT / "tatqa" / "tatqa_metric.py", "native_tatqa_scoring")
        scorer = native.TaTQAEmAndF1()
        contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
        by_id = {q["uid"]: (context, q) for context in contexts for q in context["questions"]}
        ids = config["tatqa_ids"]
        if ids != select_ids(contexts, 30, config["seed"]):
            raise ValueError("frozen item selection does not reconcile")
        for uid in ids:
            peak = max(peak, resident_bytes())
            if time.process_time() - started_cpu >= MAX_CPU_SECONDS or peak >= MAX_RSS:
                raise RuntimeError("diagnostic resource ceiling")
            context, question = by_id[uid]
            failure = None
            try:
                prediction = predict_table(prediction_input(context, question))
            except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
                failure = type(exc).__name__
                answer, scale, reason = None, "", f"input_or_baseline_error:{failure}"
            else:
                answer, scale, reason = prediction.answer, prediction.scale, prediction.reason
            # Prediction is completed before any gold is passed to the official scorer.
            scorer(ground_truth=question, prediction=answer, pred_scale=scale)
            detail = scorer.get_raw()[-1]
            outcome = ("failed" if failure else "abstain" if answer is None
                       else "correct" if detail["em"] == 1 else "wrong")
            outcomes.append({"id": uid, "outcome": outcome, "baseline_reason": reason,
                             "native_EM": detail["em"], "native_F1": detail["f1"]})
            local_predictions[uid] = [answer, scale]
        em, f1, scale, _ = scorer.get_overall_metric()
        receipt["status"] = "completed_tatqa_optional_finqa_not_scored"
        receipt["benchmarks"]["TAT-QA"]["overlap_assessment"] = (
            "Unchanged2021dev blob accepted and verified before parse.")
        receipt["benchmarks"]["TAT-QA"]["native_metrics"] = {
            "items": 30, "EM": em, "F1": f1, "scale_accuracy": scale}
    except (KeyError, TypeError, ValueError, RuntimeError, ImportError, AssertionError) as exc:
        receipt["stop_condition"] = f"scoring_error:{type(exc).__name__}"
        raise
    finally:
        peak = max(peak, resident_bytes())
        counts = Counter(r["outcome"] for r in outcomes)
        receipt["resume_config"] = {
            "path": "results/benchmark_diagnostic_config.json",
            "sha256": ledger.file_sha256(CONFIG), "seed": config["seed"],
            "baseline": config["baseline"], "selection": config["selection"]}
        receipt["lineage"] = ledger.lineage(
            [CONFIG, *[ROOT / path for path in assets]])
        receipt["downloaded_asset_hashes"] = assets
        receipt["benchmarks"]["FinQA"]["identity_year_check"] = config["finqa"]["year_check"]
        receipt["benchmarks"]["FinQA"]["file_deleted"] = not config["finqa"]["retained"]
        receipt["benchmarks"]["FinQA"]["skip_reason"] = config["finqa"]["skip_reason"]
        receipt["benchmarks"]["FinQA"]["overlap_assessment"] = (
            "Committed documented-ID year check passed before nonidentity fields; no year>=2021."
            if config["finqa"]["retained"] else
            "Identity-year check rejected the file; deleted before scoring or other field inspection.")
        intake = json.loads((ROOT / "intake.json").read_text(encoding="utf-8"))
        intake_by_path = {r["path"]: r for r in intake["files"]}
        for benchmark, relative in (("TAT-QA", Path("tatqa") / "dev.json"),
                                    ("FinQA", Path("quarantine") / "finqa_dev.json")):
            receipt["benchmarks"][benchmark]["dev_file"].update(
                sha256=intake_by_path[str(relative)]["sha256"], downloaded=True)
        for benchmark, directory in (("TAT-QA", "tatqa"), ("FinQA", "finqa")):
            for f in receipt["benchmarks"][benchmark]["official_scorer_files"]:
                key = str(Path(directory) / f["url"].rsplit("/", 1)[-1])
                if key in assets:
                    f.update(sha256=assets[key]["sha256"], downloaded=True)
        receipt["benchmarks"]["FinQA"]["corrected_preprocessing"].update(
            sha256=assets.get(str(Path("finqa") / "general_utils.py"), {}).get("sha256"),
            downloaded=str(Path("finqa") / "general_utils.py") in assets)
        receipt["download_and_run_state"] = {
            "dataset_files_downloaded": 2,
            "scorer_files_downloaded": sum(Path(path).suffix == ".py" for path in assets),
            "selected_items": 30, "scored_items": len(outcomes),
            **{k: counts[k] for k in ("correct", "wrong", "abstain", "failed")},
            "per_item_outcomes": outcomes, "selection_rule_or_baseline_freeze_performed": True,
            "models_or_training_used": False, "ledger_rows_appended": 0}
        receipt["resources"] = {
            "stage": "single-thread native TAT-QA scoring; no FinQA scoring",
            "scoring_CPU_seconds": time.process_time() - started_cpu,
            "scoring_wall_seconds": time.monotonic() - started_wall,
            "scoring_peak_resident_bytes": peak, **config["resources"]}
        receipt["hash_note"] = (
            "Downloaded files have verified Git blob SHA-1 and content SHA-256. "
            "Data, upstream code and predictions remain under ignoreddata only.")
        receipt["interpretation"] = (
            "Small untrained table baseline diagnostic, not benchmark skill, "
            "formal H1, return evidence or historical deployability.")
        # Answers can contain dataset text: write them only to ignored data, not the public receipt.
        (ROOT / "tatqa" / "predictions.json").write_text(
            json.dumps(local_predictions, indent=2, allow_nan=False), encoding="utf-8")
        RECEIPT.write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({"status": receipt["status"],
                          "outcomes": dict(counts), "scored": len(outcomes)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    phase = parser.parse_args().phase
    freeze() if phase == "freeze" else run()


if __name__ == "__main__":
    main()
