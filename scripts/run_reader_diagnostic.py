"""Freeze then run one small local-reader diagnostic, without downloads or model acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from collections import Counter
from pathlib import Path

import httpx
from calibrate_inference import resident_bytes
from pydantic import ValidationError
from run_benchmark_diagnostic import ROOT, load_native, prediction_input, verified_assets

from asof import ledger
from asof.benchmark_baseline import predict_table
from asof.benchmark_reporting import wilson95
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid, request_body

CONFIG = PROJECT_ROOT / "results" / "reader_diagnostic_config_v2.json"
FIRST_CONFIG = PROJECT_ROOT / "results" / "reader_diagnostic_config.json"
RECEIPT = PROJECT_ROOT / "results" / "reader_diagnostic_status.json"
PRIVATE = DATA_DIR / "reader_diagnostic"
ENDPOINT = "http://127.0.0.1:11435"
MODEL = "qwen3.5:4b"
DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"
SEED, COUNT, CALL_LIMIT, WALL_LIMIT = 2026111406, 10, 20, 900
ARMS = ("grounded", "no_context")
SOURCE_FILES = [
    Path(__file__), PROJECT_ROOT / "src" / "asof" / "reader_diagnostic.py",
    PROJECT_ROOT / "src" / "asof" / "benchmark_baseline.py",
]


def model_metadata(client: httpx.Client) -> dict:
    tags = client.get("/api/tags")
    tags.raise_for_status()
    matches = [m for m in tags.json()["models"] if m["name"] == MODEL]
    if len(matches) != 1 or matches[0]["digest"] != DIGEST:
        raise ValueError("existing local model digest differs; do not pull or substitute")
    version = client.get("/api/version")
    version.raise_for_status()
    return {"name": MODEL, "digest": DIGEST, "ollama_version": version.json()["version"]}


def freeze() -> None:
    if CONFIG.exists() or RECEIPT.exists():
        raise RuntimeError("reader contract/result already exists; do not replace or resample")
    assets = verified_assets()
    old = json.loads((PROJECT_ROOT / "results" / "benchmark_diagnostic_config.json").read_text())
    paired = json.loads((PROJECT_ROOT / "results" / "tatqa_average_comparison_config.json").read_text())
    excluded = set(old["tatqa_ids"]) | set(paired["ids"])
    contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
    ids = [q["uid"] for c in contexts for q in c["questions"]]
    if len(set(ids)) != len(ids) or len(excluded) != 60:
        raise ValueError("unique development IDs and exactly sixty prior exclusions required")
    chosen = random.Random(SEED).sample(sorted(set(ids) - excluded), COUNT)
    first = json.loads(FIRST_CONFIG.read_text())
    if chosen != first["ids"]:
        raise ValueError("pre-inference technical amendment must preserve the first selected items")
    with httpx.Client(base_url=ENDPOINT, timeout=5) as client:
        model = model_metadata(client)
    options = {
        "temperature": 0, "seed": SEED, "num_predict": 256, "num_ctx": 16384,
        "num_thread": 1, "num_gpu": 0, "num_batch": 128,
    }
    if model != first["model"] or options != first["options"] or assets != first["assets"]:
        raise ValueError("technical amendment must not change model, options or benchmark assets")
    config = {
        "kind": "SMALL CURRENT-MODEL DEVELOPMENT QA DIAGNOSTIC; not formal H1 or historical usability",
        "previous_config_sha256": ledger.file_sha256(FIRST_CONFIG),
        "pre_inference_amendment": "Capture clean start lineage before self-generated result writes; "
                                  "verify frozen source/config again at finish. No model call or "
                                  "question scoring occurred; IDs, model, prompts, metrics and limits unchanged.",
        "ids": chosen, "excluded_ids": sorted(excluded), "seed": SEED, "count": COUNT,
        "selection": "Random(seed).sample(sorted(all devUIDs minus prior60),10); no type/answer filter",
        "model": model, "endpoint": ENDPOINT, "options": options, "arms": ARMS,
        "order": "Per item, shuffle both arms with Random(seed+1); both predictions precede gold scoring.",
        "assets": assets,
        "source_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCE_FILES},
        "limits": {"generation_attempts": CALL_LIMIT, "wall_seconds": WALL_LIMIT,
                   "per_call_seconds": 90, "serialized_request_bytes": 12000,
                   "Python_RSS_bytes": 1 << 30,
                   "note": "Ollama runs separately, CPU1/noGPU; Python RSS excludes its model memory. "
                           "Settings/checks are cooperative, not an OS quota."},
        "metrics": "Unmodified native TAT-QA EM/F1/scale and coverage on all10 per arm, plus "
                   "unchanged symbolic v2 on same10; failures/oversize/unattempted count as misses. "
                   "Question-level descriptive Wilson95 for binary EM/coverage only.",
        "citation_boundary": "Only location/normalized-quote validity; not answer relevance, "
                             "complete arithmetic proof or verified claim support.",
        "control_boundary": "No-context arm measures evidence-withholding behavior, not a clean "
                            "memorization test. Abstention does not prove no training contamination.",
        "rights_and_time": "Same immutable pre-2022 TAT-QA dev asset already qualified; data CC BY4.0. "
                           "Current model may have seen public benchmark answers; no training-cutoff "
                           "or historical-use claim. No new corpus/model download or training.",
    }
    CONFIG.write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    print({"frozen_items": COUNT, "max_calls": CALL_LIMIT, "model": model})


def run() -> None:
    if RECEIPT.exists():
        raise RuntimeError("reader diagnostic already attempted; no retry or result overwrite")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit source and prospective config before inference")
    config = json.loads(CONFIG.read_text())
    if config["assets"] != verified_assets() or any(
        ledger.file_sha256(PROJECT_ROOT / p) != digest
        for p, digest in config["source_sha256"].items()
    ):
        raise ValueError("frozen source/assets changed")
    if any(os.environ.get(k) != "1" for k in (
        "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"
    )):
        raise RuntimeError("single-thread flags required")
    contexts = json.loads((ROOT / "tatqa" / "dev.json").read_bytes())
    by_id = {q["uid"]: (c, q) for c in contexts for q in c["questions"]}
    expected = random.Random(config["seed"]).sample(
        sorted(set(by_id) - set(config["excluded_ids"])), COUNT)
    if config["ids"] != expected or set(expected) & set(config["excluded_ids"]):
        raise ValueError("fresh deterministic selection does not reconcile")
    native = load_native(ROOT / "tatqa" / "tatqa_metric.py", "tatqa_reader_native")
    scorers = {a: native.TaTQAEmAndF1() for a in (*ARMS, "symbolic_v2")}
    start_lineage = ledger.lineage([CONFIG, *SOURCE_FILES])
    config_hash = ledger.file_sha256(CONFIG)
    receipt = {"status": "incomplete", "generation_attempts": 0, "items": [],
               "config_sha256": ledger.file_sha256(CONFIG)}
    for uid in expected:
        receipt["items"].append({"id": uid, **{
            a: {"outcome": "not_attempted", "native_EM": 0, "native_F1": 0}
            for a in (*ARMS, "symbolic_v2")
        }})
    PRIVATE.mkdir(parents=True, exist_ok=True)
    wall, cpu = time.monotonic(), time.process_time()
    peak, stopped = 0, False
    stop_reason = None
    order = random.Random(config["seed"] + 1)

    def persist() -> None:
        RECEIPT.write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")

    persist()
    try:
        with httpx.Client(base_url=ENDPOINT, timeout=5) as client:
            if model_metadata(client) != config["model"]:
                raise ValueError("model/server version changed after freeze")
            for row in receipt["items"]:
                context, gold = by_id[row["id"]]
                item = prediction_input(context, gold)
                base = predict_table(item)
                predictions = {"symbolic_v2": (base.answer, base.scale)}
                row["symbolic_v2"]["reason"] = base.reason
                arms = list(ARMS)
                order.shuffle(arms)
                for arm in arms:
                    body = request_body(item, model=MODEL, supplied_context=arm == "grounded",
                                        options=config["options"])
                    encoded = json.dumps(body).encode()
                    prediction, scale = None, ""
                    row[arm]["request_sha256"] = hashlib.sha256(encoded).hexdigest()
                    remaining = WALL_LIMIT - (time.monotonic() - wall)
                    peak = max(peak, resident_bytes())
                    if stopped:
                        row[arm]["reason"] = f"prior_stop:{stop_reason}"
                    elif remaining <= 1 or peak >= 1 << 30:
                        stopped = True
                        stop_reason = "wall_ceiling" if remaining <= 1 else "Python_RSS_ceiling"
                        row[arm]["reason"] = stop_reason
                    elif len(encoded) > config["limits"]["serialized_request_bytes"]:
                        row[arm].update(outcome="failed", reason="oversized_input_not_truncated")
                    else:
                        if receipt["generation_attempts"] >= CALL_LIMIT:
                            raise RuntimeError("generation cap; do not retry")
                        receipt["generation_attempts"] += 1
                        row[arm]["outcome"] = "attempt_started"
                        persist()
                        try:
                            response = client.post(
                                "/api/chat", content=encoded,
                                headers={"Content-Type": "application/json"},
                                timeout=min(90, remaining),
                            )
                            response.raise_for_status()
                        except httpx.HTTPError as exc:
                            row[arm].update(outcome="failed", reason=type(exc).__name__)
                            stopped = True
                            stop_reason = type(exc).__name__
                        else:
                            raw = response.json()
                            (PRIVATE / f"{row['id']}_{arm}.json").write_text(
                                json.dumps(raw, indent=2), encoding="utf-8")
                            row[arm]["ollama_timing"] = {
                                key: raw.get(key) for key in (
                                    "total_duration", "load_duration", "prompt_eval_count",
                                    "prompt_eval_duration", "eval_count", "eval_duration",
                                )
                            }
                            try:
                                if raw.get("done") is not True or raw.get("done_reason") != "stop":
                                    raise ValueError("generation incomplete or token limit")
                                parsed = ReaderAnswer.model_validate_json(raw["message"]["content"])
                            except (ValidationError, ValueError, KeyError) as exc:
                                row[arm].update(outcome="failed", reason=type(exc).__name__)
                            else:
                                prediction, scale = parsed.answer, parsed.scale
                                row[arm].update(
                                    outcome="abstain" if parsed.abstain else "answered",
                                    citation_locations_or_quotes_valid=references_locally_valid(
                                        parsed, item, supplied_context=arm == "grounded"),
                                )
                    predictions[arm] = (prediction, scale)
                # Both model inputs/predictions are finished before reading gold for scoring.
                for arm, (answer, scale) in predictions.items():
                    scorers[arm](ground_truth=gold, prediction=answer, pred_scale=scale)
                    detail = scorers[arm].get_raw()[-1]
                    row[arm].update(native_EM=detail["em"], native_F1=detail["f1"])
                    if arm == "symbolic_v2" or row[arm]["outcome"] == "answered":
                        row[arm]["outcome"] = (
                            "abstain" if answer is None else "correct" if detail["em"] == 1 else "wrong"
                        )
                persist()
        summaries = {}
        for arm, metric in scorers.items():
            em, f1, scale, _ = metric.get_overall_metric()
            counts = Counter(r[arm]["outcome"] for r in receipt["items"])
            answered = counts["correct"] + counts["wrong"]
            summaries[arm] = {
                "counts": dict(counts), "native_EM": em, "native_F1": f1,
                "native_scale_accuracy": scale, "coverage": answered / COUNT,
                "EM_Wilson95": wilson95(counts["correct"], COUNT),
                "coverage_Wilson95": wilson95(answered, COUNT),
            }
        receipt.update(status="partial" if stopped else "complete",
                       stop_reason=stop_reason, summaries=summaries)
    except (ValueError, KeyError, TypeError, RuntimeError) as exc:
        receipt["stop_reason"] = type(exc).__name__
        raise
    finally:
        receipt.update(
            resources={"Python_CPU_seconds": time.process_time() - cpu,
                       "wall_seconds": time.monotonic() - wall,
                       "Python_peak_resident_bytes": max(peak, resident_bytes()),
                       "note": "Ollama durations are not CPU measurements; model memory is separate."},
            lineage=start_lineage,
            frozen_source_and_config_unchanged=(
                ledger.file_sha256(CONFIG) == config_hash and all(
                    ledger.file_sha256(PROJECT_ROOT / p) == digest
                    for p, digest in config["source_sha256"].items()
                )
            ),
        )
        if not receipt["frozen_source_and_config_unchanged"]:
            receipt.update(status="invalid_source_changed", stop_reason="source_or_config_changed")
        persist()
        print({"status": receipt["status"], "generation_attempts": receipt["generation_attempts"]})
        if not receipt["frozen_source_and_config_unchanged"]:
            raise RuntimeError("frozen reader source or configuration changed during inference")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    freeze() if parser.parse_args().phase == "freeze" else run()
