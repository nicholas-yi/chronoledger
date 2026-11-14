"""One frozen invented positive-control run; never loads a benchmark dataset."""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import math
import os
import random
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import httpx
from pydantic import ValidationError

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_diagnostic import ReaderAnswer, references_locally_valid
from asof.reader_positive_control import (
    ARMS,
    cases,
    classify_response,
    control_body,
    pass_criterion,
    score_answer,
)

ENDPOINT = "http://127.0.0.1:11435"
MODEL = "qwen3.5:4b"
DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"
CONFIG = PROJECT_ROOT / "results" / "reader_pc1_config.json"
DIAGNOSIS = PROJECT_ROOT / "results" / "reader_pc1_diagnosis.json"
RECEIPT = PROJECT_ROOT / "results" / "reader_pc1_status.json"
PRIVATE = DATA_DIR / "reader_pc1"
SEED, WALL_LIMIT, CALL_LIMIT = 2026111411, 1200, 24
SOURCES = [
    Path(__file__), PROJECT_ROOT / "src" / "asof" / "reader_positive_control.py",
    PROJECT_ROOT / "src" / "asof" / "reader_diagnostic.py",
    PROJECT_ROOT / "src" / "asof" / "benchmark_baseline.py",
    PROJECT_ROOT / "src" / "asof" / "extraction.py",
]


class ResourceStop(RuntimeError):
    pass


class WindowsCPU:
    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("this resource sampler requires Windows")
        self.previous = self.read()

    @staticmethod
    def read() -> tuple[int, int]:
        from ctypes import wintypes
        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            raise ctypes.WinError()

        def ticks(value) -> int:
            return (value.dwHighDateTime << 32) + value.dwLowDateTime
        return ticks(idle), ticks(kernel) + ticks(user)

    def percent(self) -> float:
        current = self.read()
        idle, total = current[0] - self.previous[0], current[1] - self.previous[1]
        self.previous = current
        if total <= 0 or idle < 0 or idle > total:
            raise ResourceStop("invalid host CPU measurement")
        return 100 * (1 - idle / total)


class LoadHistory:
    def __init__(self) -> None:
        self.samples: list[float] = []
        self.high_streak = 0

    def add(self, value: float) -> None:
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ResourceStop("host CPU load unavailable")
        self.samples.append(value)
        self.high_streak = self.high_streak + 1 if value > 90 else 0
        if self.high_streak >= 3:
            raise ResourceStop("host CPU above90percent for3consecutive1second samples")


async def watch_resources(started: float, cpu: WindowsCPU, loads: LoadHistory) -> None:
    while True:
        await asyncio.sleep(1)
        loads.add(cpu.percent())
        if time.monotonic() - started >= WALL_LIMIT:
            raise ResourceStop("20minute wall limit")


async def guarded_request(client, body: dict, watch: asyncio.Task, timeout: float):
    request = asyncio.create_task(asyncio.wait_for(client.post(
        "/api/chat", json=body, timeout=timeout,
    ), timeout=timeout))
    try:
        done, _ = await asyncio.wait((request, watch), return_when=asyncio.FIRST_COMPLETED)
        if watch in done:
            await watch
            raise ResourceStop("resource monitor ended unexpectedly")
        return await request
    finally:
        if not request.done():
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)


def diagnose() -> None:
    if DIAGNOSIS.exists():
        raise RuntimeError("saved-response diagnosis already recorded")
    paths = sorted((DATA_DIR / "reader_diagnostic").glob("*_*.json"))
    if len(paths) != 8:
        raise ValueError("expected exactly eight stored prior responses")
    rows = [{"file": p.name, "sha256": ledger.file_sha256(p),
             **classify_response(json.loads(p.read_text()), 256)} for p in paths]
    output = {
        "kind": "Offline metadata/parse diagnosis only; raw text stays ignored/local.",
        "responses": rows,
        "counts": {
            "responses": len(rows),
            "done_reason": dict(Counter(r["done_reason"] for r in rows)),
            "eval_count": dict(Counter(r["eval_count"] for r in rows)),
            "valid_parse": sum(r["parse_rule"] == "valid" for r in rows),
            "explicit_abstain_true": sum(r["explicit_abstain"] is True for r in rows),
            "thinking_field_present": sum(r["thinking_field_present"] for r in rows),
            "nonempty_thinking": sum(r["nonempty_thinking_field"] for r in rows),
            "empty_visible_text": sum(r["empty_visible_text"] for r in rows),
            "token_limit_hits": sum(r["token_limit_hit"] for r in rows),
        },
        "conclusion": "All eight are explicit schema-valid abstentions with normal stops, "
                      "not parse-to-abstain fallbacks, hidden-thinking text or token-cap truncation. "
                      "Prompt/schema conservatism is a hypothesis; timeout/slowness is separate.",
        "lineage": ledger.lineage(),
    }
    DIAGNOSIS.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["counts"]))


def freeze() -> None:
    if CONFIG.exists() or RECEIPT.exists():
        raise RuntimeError("PC1 already frozen/attempted; no overwrite or tuning")
    items = cases()
    if Counter(c.category for c in items) != {
        "lookup": 4, "arithmetic": 4, "text": 2, "unanswerable": 2,
    } or len({c.id for c in items}) != 12:
        raise ValueError("positive-control composition/identities differ")
    config = {
        "kind": "INVENTED POSITIVE CONTROL, not benchmark/financial-reading evidence",
        "items": [asdict(c) for c in items], "seed": SEED, "arms": ARMS,
        "primary_arm": "answer_first", "model": MODEL, "model_API_digest": DIGEST,
        "endpoint": ENDPOINT, "expected_Ollama_version": "0.40.16",
        "options": {"temperature": 0, "seed": SEED, "num_predict": 512, "num_ctx": 8192,
                    "num_thread": 4, "num_gpu": 0, "num_batch": 128},
        "matched_arm_note": "Both arms use identical new runtime options and240s call limit. "
                            "Old arm preserves original prompt/schema, not its1thread/90s limits. "
                            "New arm changes only system guidance plus schema property/required order. "
                            "This bundle comparison cannot isolate those two components.",
        "thinking": "think=false in both arms, as it already was in the prior run.",
        "normalization": "Numeric Decimal exact after comma/$ removal; trailing% implies percent "
                         "unless conflicting scale. Numeric value and scale must both match; "
                         "no rescaling/tolerance. Text casefold/collapse whitespace/strip terminal "
                         "periods. Scalar only. No fuzzy matching or synonym substitution.",
        "pass": "Primary arm:>=9of10 answerable exact+scale AND2of2 unanswerable explicitabstain; "
                "all12attempted, no missing/errors substituted. Old arm descriptive, samecriterion.",
        "order": "Fixed item order; per-item arm order shuffled by Random(seed). No retries.",
        "limits": {"calls": CALL_LIMIT, "wall_seconds": WALL_LIMIT, "per_call_seconds": 240,
                   "launch_host_CPU_mean3samples_below_percent": 70,
                   "abort_host_CPU_percent_above": 90, "consecutive_1second_samples": 3,
                   "expected_model_RAM_GiB": "~5", "note": "Cooperative watchdog, not OS sandbox."},
        "source_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
        "diagnosis_sha256": ledger.file_sha256(DIAGNOSIS),
        "scope": "No benchmark dataset opened or questions rerun, model pull, training, keys, "
                 "paid calls, market data, sealed data, push, tag or trial-ledger append.",
    }
    CONFIG.write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    print({"frozen_items": 12, "planned_calls": CALL_LIMIT, "primary": "answer_first"})


async def run() -> None:
    if RECEIPT.exists():
        raise RuntimeError("PC1 already attempted; no retry or result overwrite")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit source, diagnosis and contract before generation")
    config = json.loads(CONFIG.read_text())
    if (ledger.file_sha256(DIAGNOSIS) != config["diagnosis_sha256"] or any(
        ledger.file_sha256(PROJECT_ROOT / p) != digest
        for p, digest in config["source_sha256"].items()
    )):
        raise ValueError("PC1 frozen evidence/source changed")
    start, cpu_start = time.monotonic(), time.process_time()
    start_lineage = ledger.lineage([CONFIG, DIAGNOSIS, *SOURCES])
    config_hash = ledger.file_sha256(CONFIG)
    cpu, loads = WindowsCPU(), LoadHistory()
    receipt = {"status": "incomplete", "generation_attempts": 0, "items": [],
               "config_sha256": config_hash, "lineage": start_lineage}
    for case in cases():
        receipt["items"].append({"id": case.id, "answerable": case.expected is not None, **{
            arm: {"correct": False, "outcome": "not_attempted"} for arm in ARMS
        }})
    PRIVATE.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        RECEIPT.write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")

    persist()
    watch = None
    try:
        for _ in range(3):
            await asyncio.sleep(1)
            loads.add(cpu.percent())
        launch_load = sum(loads.samples) / 3
        receipt["launch_host_CPU_percent"] = launch_load
        if launch_load >= 70:
            raise ResourceStop("launch CPU mean is not below70percent")
        watch = asyncio.create_task(watch_resources(start, cpu, loads))
        order = random.Random(SEED)
        async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
            tags, version = await client.get("/api/tags"), await client.get("/api/version")
            tags.raise_for_status()
            version.raise_for_status()
            models = [m for m in tags.json()["models"] if m["name"] == MODEL]
            if len(models) != 1 or models[0]["digest"] != DIGEST or (
                version.json()["version"] != config["expected_Ollama_version"]
            ):
                raise ResourceStop("existing model/server pin differs; do not substitute")
            for case, row in zip(cases(), receipt["items"], strict=True):
                arms = list(ARMS)
                order.shuffle(arms)
                for arm in arms:
                    if receipt["generation_attempts"] >= CALL_LIMIT:
                        raise ResourceStop("call ceiling")
                    body = control_body(case, arm, model=MODEL, options=config["options"])
                    encoded = json.dumps(body).encode()
                    if len(encoded) > 6000:
                        raise ResourceStop("synthetic request byte guard; no truncation")
                    receipt["generation_attempts"] += 1
                    row[arm].update(outcome="attempt_started",
                                    request_sha256=hashlib.sha256(encoded).hexdigest())
                    persist()
                    try:
                        response = await guarded_request(
                            client, body, watch, min(240, WALL_LIMIT - (time.monotonic() - start)))
                        response.raise_for_status()
                    except (httpx.HTTPError, TimeoutError, ResourceStop) as exc:
                        row[arm].update(outcome="failed", failure_type=type(exc).__name__)
                        raise
                    raw = response.json()
                    (PRIVATE / f"{case.id}_{arm}.json").write_text(
                        json.dumps(raw, indent=2), encoding="utf-8")
                    row[arm]["response_classification"] = classify_response(raw, 512)
                    row[arm]["ollama_metrics"] = {k: raw.get(k) for k in (
                        "total_duration", "load_duration", "prompt_eval_count", "eval_count",
                    )}
                    if raw.get("done") is not True or raw.get("done_reason") != "stop":
                        row[arm].update(outcome="incomplete_generation")
                    else:
                        try:
                            answer = ReaderAnswer.model_validate_json(raw["message"]["content"])
                        except (ValidationError, KeyError):
                            row[arm].update(outcome="invalid_output")
                        else:
                            row[arm].update(**score_answer(case, answer),
                                explicit_abstain=answer.abstain,
                                citation_locations_or_quotes_valid=references_locally_valid(
                                    answer, case.item, supplied_context=True))
                    persist()
        receipt["status"] = "complete"
    except (httpx.HTTPError, TimeoutError, ResourceStop, ValueError, KeyError) as exc:
        receipt["stop_reason"] = type(exc).__name__
        if isinstance(exc, ResourceStop):
            receipt["resource_stop"] = str(exc)
    finally:
        if watch is not None:
            watch.cancel()
            await asyncio.gather(watch, return_exceptions=True)
        summaries = {}
        for arm in ARMS:
            attempted = sum(row[arm]["outcome"] != "not_attempted" for row in receipt["items"])
            a = sum(row["answerable"] and row[arm]["correct"] for row in receipt["items"])
            u = sum(not row["answerable"] and row[arm]["correct"] for row in receipt["items"])
            summaries[arm] = {
                "answerable_correct": a, "answerable_total": 10,
                "unanswerable_correct": u, "unanswerable_total": 2, "attempted": attempted,
                "criterion_passed": pass_criterion(a, u, attempted),
                "outcomes": dict(Counter(row[arm]["outcome"] for row in receipt["items"])),
            }
        source_ok = ledger.file_sha256(CONFIG) == config_hash and all(
            ledger.file_sha256(PROJECT_ROOT / p) == digest
            for p, digest in config["source_sha256"].items())
        passed = receipt["status"] == "complete" and source_ok and summaries["answer_first"]["criterion_passed"]
        receipt.update(verdict="PASS" if passed else "FAIL", summaries=summaries,
            frozen_source_and_config_unchanged=source_ok,
            resources={"wall_seconds": time.monotonic() - start,
                       "Python_CPU_seconds": time.process_time() - cpu_start,
                       "host_CPU_samples": len(loads.samples),
                       "host_CPU_max_percent": max(loads.samples) if loads.samples else None,
                       "host_CPU_mean_percent": sum(loads.samples)/len(loads.samples)
                       if loads.samples else None,
                       "note": "Hostload is not processCPU; Ollama model memory/CPU is separate."})
        persist()
        print(json.dumps({"status": receipt["status"], "verdict": receipt["verdict"],
                          "generation_attempts": receipt["generation_attempts"],
                          "summaries": summaries}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("diagnose", "freeze", "run"))
    phase = parser.parse_args().phase
    if phase == "diagnose":
        diagnose()
    elif phase == "freeze":
        freeze()
    else:
        asyncio.run(run())
