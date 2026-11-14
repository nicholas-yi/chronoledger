"""Once-only paired native comparison on 30 fresh development questions."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import subprocess
from collections import Counter
from pathlib import Path

from benchmark_followup_utils import (
    FOLLOWUP,
    ORIGINAL_CONFIG,
    ORIGINAL_RECEIPT,
    ROOT,
    V1,
    Budget,
    assert_frozen,
    load_v1,
    read_followup,
)
from run_benchmark_diagnostic import load_native, prediction_input, verified_assets

from asof import ledger
from asof.benchmark_baseline import predict_table
from asof.benchmark_reporting import wilson95
from asof.config import PROJECT_ROOT

SEED = 2026111405
CONFIG = PROJECT_ROOT / "results" / "tatqa_average_comparison_config.json"
CURRENT = PROJECT_ROOT / "src" / "asof" / "benchmark_baseline.py"


def assert_average_only(old: Path, new: Path) -> None:
    target = ast.dump(ast.parse('"average" in question', mode="eval").body)

    class Mask(ast.NodeTransformer):
        def __init__(self) -> None:
            self.count = 0

        def visit_If(self, node):
            node = self.generic_visit(node)
            if ast.dump(node.test) == target:
                self.count += 1
                node.body = [ast.Pass()]
            return node

    normalized = []
    for path in (old, new):
        mask = Mask()
        tree = mask.visit(ast.parse(path.read_text(encoding="utf-8")))
        if mask.count != 1:
            raise ValueError("one exact average-rule body must be identifiable")
        normalized.append(ast.dump(tree, include_attributes=False))
    if normalized[0] != normalized[1]:
        raise ValueError("code outside the average-rule body changed")


def _part_hash(part: dict) -> str:
    return hashlib.sha256(json.dumps(part, sort_keys=True).encode()).hexdigest()


def freeze() -> None:
    followup = read_followup()
    if followup.get("finqa", {}).get("status") != "complete":
        raise ValueError("FinQA must complete first")
    committed = subprocess.run(
        ["git", "diff", "--quiet", "--", str(FOLLOWUP.relative_to(PROJECT_ROOT))],
        cwd=PROJECT_ROOT, check=False)
    if committed.returncode != 0:
        raise ValueError("commit FinQA result before average comparison")
    assert_average_only(V1, CURRENT)
    assets = verified_assets()
    original = json.loads(ORIGINAL_CONFIG.read_text())
    excluded = set(original["tatqa_ids"])
    contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
    all_ids = [q["uid"] for c in contexts for q in c["questions"]]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("duplicate question identities")
    eligible = sorted(set(all_ids) - excluded)
    config = {
        "seed": SEED, "ids": random.Random(SEED).sample(eligible, 30),
        "selection": "Random(newseed).sample(sorted(all devUIDs minus original30),30); "
                     "no type/answer/success filter or resampling",
        "excluded_ids": sorted(excluded),
        "v1_sha256": ledger.file_sha256(V1), "v2_sha256": ledger.file_sha256(CURRENT),
        "runner_sha256": ledger.file_sha256(Path(__file__)),
        "original_receipt_sha256": ledger.file_sha256(ORIGINAL_RECEIPT),
        "finqa_result_sha256": _part_hash(followup["finqa"]),
        "assets": assets,
        "rule_change": "Only average body: explicit year ranges include every observed year; "
                       "listed endpoints stay listed. Abstain on weighted-average metric/"
                       "respectively lookups, missing range values, conflicting units and "
                       "ambiguous negative expense signs; explicit magnitude/signed requests "
                       "honored. Unique table unit banner considered locally for averages.",
        "native_metrics": "Unmodified TATQA EM/F1/scale for each version on same30; "
                          "coverage, all outcomes and paired metadata diffs. Wilson95 for "
                          "EM/scale/coverage only, not continuous F1 or a paired-difference CI.",
        "diagnosis": [
            {"id": "028bf685-261d-420f-a080-1a9b62147d53",
             "category": "inclusive_range_omitted_middle_year",
             "action": "include all observed range years; otherwise abstain"},
            {"id": "1427bbad-0def-4340-a537-4713dad96ea7",
             "category": "signed_expense_convention_and_later_table_unit_banner",
             "action": "do not infer absolute sign; abstain ambiguity, use local banner for averages"},
            {"id": "7c540b6e-6f7f-421a-9aa8-b173f882dbac",
             "category": "average_is_metric_name_and_ordered_lookup_not_aggregation",
             "action": "abstain; no new multi-span return type"},
        ],
        "other_observations_not_acted_on": [
            "FinQA explicit-year/row/ratio restrictions caused all10abstentions; not broadened.",
            "Non-average global unit inference can miss later banners; unchanged.",
            "Ordered multi-span lookup is unsupported; not implemented.",
        ],
        "original_items_rescored": False,
    }
    CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print({"frozen_fresh_items": 30, "excluded_original": len(excluded), "seed": SEED})


def run() -> None:
    budget = Budget()
    config = json.loads(CONFIG.read_text())
    assert_frozen(config, Path(__file__))
    assert_average_only(V1, CURRENT)
    if (ledger.file_sha256(V1) != config["v1_sha256"]
            or ledger.file_sha256(CURRENT) != config["v2_sha256"]):
        raise ValueError("baseline changed after paired freeze")
    output = read_followup()
    if "tatqa_paired" in output:
        raise RuntimeError("paired diagnostic already attempted")
    if _part_hash(output["finqa"]) != config["finqa_result_sha256"]:
        raise ValueError("committed FinQA result changed")
    ids = config["ids"]
    if len(ids) != 30 or len(set(ids)) != 30 or set(ids) & set(config["excluded_ids"]):
        raise ValueError("fresh paired identities must exclude every original item")
    part = {"status": "incomplete", "items": [], "config_sha256": ledger.file_sha256(CONFIG)}
    output["tatqa_paired"] = part
    private = {"v1": {}, "v2": {}}
    try:
        v1 = load_v1()
        native = load_native(ROOT / "tatqa" / "tatqa_metric.py", "tatqa_native_paired")
        scorers = {v: native.TaTQAEmAndF1() for v in ("v1", "v2")}
        contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
        by_id = {q["uid"]: (c, q) for c in contexts for q in c["questions"]}
        expected = random.Random(config["seed"]).sample(
            sorted(set(by_id) - set(config["excluded_ids"])), 30)
        if ids != expected:
            raise ValueError("paired selection mismatch")
        for uid in ids:
            budget.check()
            context, q = by_id[uid]
            item = prediction_input(context, q)
            # Both predictions precede reference access; no adaptive use of v1's score by v2.
            predictions = {"v1": v1.predict_table(item), "v2": predict_table(item)}
            row = {"id": uid}
            for name, prediction in predictions.items():
                metric = scorers[name]
                metric(ground_truth=q, prediction=prediction.answer, pred_scale=prediction.scale)
                detail = metric.get_raw()[-1]
                outcome = ("abstain" if prediction.answer is None else
                           "correct" if detail["em"] == 1 else "wrong")
                row[name] = {"outcome": outcome, "reason": prediction.reason,
                             "native_EM": detail["em"], "native_F1": detail["f1"]}
                private[name][uid] = [prediction.answer, prediction.scale]
            a, b = predictions["v1"], predictions["v2"]
            row["prediction_changed"] = (a.answer, a.scale) != (b.answer, b.scale)
            row["EM_change"] = row["v2"]["native_EM"] - row["v1"]["native_EM"]
            part["items"].append(row)
        budget.check()
        versions = {}
        for name, metric in scorers.items():
            em, f1, scale, _ = metric.get_overall_metric()
            counts = Counter(r[name]["outcome"] for r in part["items"])
            answered = 30 - counts["abstain"]
            versions[name] = {
                "counts": {k: counts[k] for k in ("correct", "wrong", "abstain")},
                "native_EM": em, "native_F1": f1, "native_scale_accuracy": scale,
                "coverage": answered / 30,
                "EM_Wilson95": wilson95(counts["correct"], 30),
                "scale_Wilson95": wilson95(round(scale * 30), 30),
                "coverage_Wilson95": wilson95(answered, 30),
            }
        part.update(status="complete", attempted_per_version=30, versions=versions,
                    improved=sum(r["EM_change"] > 0 for r in part["items"]),
                    regressed=sum(r["EM_change"] < 0 for r in part["items"]),
                    changed_predictions=sum(r["prediction_changed"] for r in part["items"]),
                    paired_EM_change=versions["v2"]["native_EM"] - versions["v1"]["native_EM"],
                    diagnosis=config["diagnosis"],
                    other_observations_not_acted_on=config["other_observations_not_acted_on"],
                    interval_note="Descriptive question-level Wilson intervals; ignore shared "
                                  "contexts, not a significance test of the paired difference.")
    except (ValueError, KeyError, TypeError, ImportError, RuntimeError, AssertionError) as exc:
        part["stop"] = type(exc).__name__
        raise
    finally:
        part.update(resources=budget.receipt(), lineage=ledger.lineage([CONFIG, CURRENT, V1]))
        for name, predictions in private.items():
            (ROOT.parent / "bench_2" / f"tatqa_{name}_predictions.json").write_text(
                json.dumps(predictions, indent=2), encoding="utf-8")
        FOLLOWUP.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
        print({"paired_status": part["status"], "items": len(part["items"])})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    freeze() if parser.parse_args().phase == "freeze" else run()
