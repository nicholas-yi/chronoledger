"""Content-independent REAL2 completion routing and immutable-case combination."""

from __future__ import annotations

import copy
import hashlib
import json

from asof.reader_real_report import ARMS, VALID_OUTCOMES, report


def case_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def effective_config(base: dict) -> dict:
    if base["limits"]["owned_process_tree_RSS_bytes"] != 6 << 30:
        raise ValueError("amendment must start from the declared six-GiB limit")
    result = copy.deepcopy(base)
    result["limits"]["owned_process_tree_RSS_bytes"] = 10 << 30
    return result


def completion_plan(base: dict, original: dict) -> tuple[list[dict], list[dict]]:
    if [r["id"] for r in original["items"]] != base["ids"]:
        raise ValueError("original item identities/order differ")
    by_id = {r["id"]: r for r in original["items"]}
    jobs, protected = [], []
    for order in base["orders"]:
        for arm in order["arms"]:
            value = by_id[order["id"]][arm]
            key = {"id": order["id"], "arm": arm}
            if value["outcome"] == "not_attempted" and not value["attempted"]:
                jobs.append({**key, "eligibility": "never_attempted"})
            elif (
                arm == "report_supplied" and value["outcome"] == "failed"
                and value["attempted"]
                and value.get("reason") == (
                    "run_stopped:owned isolated process tree working set exceeds6GiB")
            ):
                jobs.append({**key, "eligibility": "memory_cancelled"})
            elif value.get("generation_finished") is True and value["outcome"] in VALID_OUTCOMES:
                protected.append({**key, "record_sha256": case_hash(value)})
            else:
                raise ValueError("case is neither eligible nor a protected finished prediction")
    if (
        len(jobs) != 40 or len(protected) != 20
        or sum(j["eligibility"] == "memory_cancelled" for j in jobs) != 1
        or sum(j["eligibility"] == "never_attempted" for j in jobs) != 39
    ):
        raise ValueError("completion must contain exactly39never-attempted+1memory-cancelled")
    selected = {(j["id"], j["arm"]) for j in jobs}
    if len(selected) != 40 or selected & {(p["id"], p["arm"]) for p in protected}:
        raise ValueError("duplicate or protected case selected for generation")
    for uid in {j["id"] for j in jobs}:
        if {a for u, a in selected if u == uid} != set(ARMS):
            raise ValueError("verified REAL2 completion is twenty remaining pairs")
    return jobs, protected


def combine(base: dict, original: dict, completion: dict, jobs: list[dict]) -> dict:
    expected, protected = completion_plan(base, original)
    if jobs != expected:
        raise ValueError("completion case order differs from frozen routing")
    selected = {(j["id"], j["arm"]) for j in jobs}
    new = {r["id"]: r for r in completion["items"]}
    if set(new) != {uid for uid, _ in selected} or len(new) != len(completion["items"]):
        raise ValueError("completion UID set differs")
    rows = copy.deepcopy(original["items"])
    for row in rows:
        row["case_record_source"] = {}
        for arm in ARMS:
            if (row["id"], arm) in selected:
                if new[row["id"]]["answer_type"] != row["answer_type"]:
                    raise ValueError("native answer-type metadata changed")
                row[arm] = copy.deepcopy(new[row["id"]][arm])
                row["case_record_source"][arm] = "REAL2-C"
            else:
                row["case_record_source"][arm] = "REAL2"
    indexed = {r["id"]: r for r in rows}
    for item in protected:
        if case_hash(indexed[item["id"]][item["arm"]]) != item["record_sha256"]:
            raise ValueError("a finished original case was overwritten")
    return {
        "status": completion["status"], "items": rows,
        "as_stopped_report": copy.deepcopy(original["report"]),
        "combined_report": report(rows),
        "attempt_accounting": {
            "original_generation_attempts": original["generation_attempts"],
            "completion_generation_attempts": completion["generation_attempts"],
            "total_generation_attempts": (
                original["generation_attempts"] + completion["generation_attempts"]),
            "unique_condition_cases": 60,
            "declared_extra_attempt_for_memory_cancelled_case": 1,
        },
        "meaning": "Declared content-independent operational completion after initial outcomes "
                   "were available; only memory cap changed. Twenty finished cases preserved "
                   "verbatim; original failure/trace/accounting remain in the stopped receipt. "
                   "No-report abstention does not rule out training exposure. Public-benchmark "
                   "reading only, not historical usability, formal H1 or financial returns.",
    }
