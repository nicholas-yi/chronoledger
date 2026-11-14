"""Native FinQA execution accuracy with the unchanged a36126d table baseline."""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from benchmark_followup_utils import (
    FOLLOWUP,
    ORIGINAL_RECEIPT,
    ROOT,
    V1,
    Budget,
    assert_frozen,
    load_v1,
    read_followup,
)
from run_benchmark_diagnostic import load_native, verified_assets

from asof import ledger
from asof.benchmark_adapters import finqa_input, finqa_program
from asof.benchmark_reporting import wilson95
from asof.config import PROJECT_ROOT

SEED = 2026111404
CONFIG = PROJECT_ROOT / "results" / "finqa_diagnostic_config.json"
ADAPTER = PROJECT_ROOT / "src" / "asof" / "benchmark_adapters.py"


def freeze() -> None:
    assets = verified_assets()
    baseline = load_v1()
    current = PROJECT_ROOT / "src" / "asof" / "benchmark_baseline.py"
    if ledger.file_sha256(current) != ledger.file_sha256(V1):
        raise ValueError("FinQA must precede any baseline change")
    load_native(ROOT / "finqa" / "evaluate.py", "finqa_native_preflight2")
    rows = json.loads((ROOT / "quarantine" / "finqa_dev.json").read_bytes())
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids) or len(ids) < 10:
        raise ValueError("unique fixed FinQA item identities required")
    config = {
        "seed": SEED, "ids": random.Random(SEED).sample(sorted(ids), 10),
        "selection": "Random(seed).sample(sorted(all883unique devIDs),10), no filtering/resampling",
        "baseline": "Unchanged a36126d predict_table; adapter reads only question/pre_text/table/post_text",
        "adapter": "Reconstruct same successful row/year operands and encode emitted operation in "
                   "native DSL, not an answer constant. Context magnitudes retained; percent "
                   "outputs become ratios. Native eval_program(predicted,table), exact equality "
                   "against exe_ans as in official evaluate_result; abstention is a miss. "
                   "No gold program execution or program-equivalence metric.",
        "runner_sha256": ledger.file_sha256(Path(__file__)),
        "adapter_sha256": ledger.file_sha256(ADAPTER),
        "baseline_sha256": ledger.file_sha256(V1),
        "original_receipt_sha256": ledger.file_sha256(ORIGINAL_RECEIPT),
        "assets": assets,
        "packages": {n: version(n) for n in ("tqdm", "sympy", "mpmath")},
    }
    if baseline.predict_table is None:
        raise ValueError("frozen baseline unavailable")
    CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print({"frozen_finqa_items": 10, "seed": SEED})


def run() -> None:
    budget = Budget()
    config = json.loads(CONFIG.read_text())
    assert_frozen(config, Path(__file__))
    if ledger.file_sha256(ADAPTER) != config["adapter_sha256"]:
        raise ValueError("adapter changed after freeze")
    current = PROJECT_ROOT / "src" / "asof" / "benchmark_baseline.py"
    if ledger.file_sha256(current) != config["baseline_sha256"]:
        raise ValueError("baseline changed before FinQA scoring")
    output = read_followup()
    if "finqa" in output:
        raise RuntimeError("FinQA diagnostic already attempted")
    part = {"status": "incomplete", "items": [], "config_sha256": ledger.file_sha256(CONFIG)}
    output["finqa"] = part
    private = {}
    try:
        baseline = load_v1()
        native = load_native(ROOT / "finqa" / "evaluate.py", "finqa_native_scoring2")
        records = json.loads((ROOT / "quarantine" / "finqa_dev.json").read_bytes())
        by_id = {r["id"]: r for r in records}
        if config["ids"] != random.Random(config["seed"]).sample(sorted(by_id), 10):
            raise ValueError("frozen selection mismatch")
        for uid in config["ids"]:
            budget.check()
            record = by_id[uid]
            item = finqa_input(record)
            prediction = baseline.predict_table(item)
            program = finqa_program(item, prediction)
            correct, failed = False, False
            if program.tokens is None:
                outcome = "abstain"
            else:
                invalid, result = native.eval_program(list(program.tokens), record["table"])
                if invalid:
                    failed, outcome = True, "failed"
                else:
                    if program.expected_answer is None:
                        raise ValueError("emitted program lacks its adapter interpretation")
                    if not math.isclose(result, program.expected_answer, rel_tol=5e-9, abs_tol=1e-5):
                        raise ValueError("adapter/native result differs from frozen baseline convention")
                    # Reference accessed only after the predicted program was generated/executed.
                    correct = result == record["qa"]["exe_ans"]
                    outcome = "correct" if correct else "wrong"
            part["items"].append({"id": uid, "outcome": outcome, "baseline_reason": prediction.reason,
                                  "native_execution_correct": int(correct), "failed": failed})
            private[uid] = {"predicted": program.tokens, "answer": prediction.answer,
                            "scale": prediction.scale}
        counts = Counter(r["outcome"] for r in part["items"])
        part.update(status="complete", counts=dict(counts), attempted=10,
                    execution_accuracy=counts["correct"] / 10,
                    execution_accuracy_Wilson95=wilson95(counts["correct"], 10),
                    coverage=sum(r["outcome"] != "abstain" for r in part["items"]) / 10,
                    gold_programs_executed=False, packages=config["packages"])
    except (ValueError, KeyError, TypeError, ImportError, RuntimeError) as exc:
        part["stop"] = type(exc).__name__
        raise
    finally:
        part.update(resources=budget.receipt(), lineage=ledger.lineage([CONFIG, ADAPTER, V1]))
        (ROOT.parent / "bench_2" / "finqa_predictions.json").write_text(
            json.dumps(private, indent=2), encoding="utf-8")
        FOLLOWUP.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
        print({"finqa_status": part["status"], "attempted": len(part["items"])})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    freeze() if parser.parse_args().phase == "freeze" else run()
