"""Fixed descriptive reporting for paired public-benchmark reader measurements."""

from __future__ import annotations

import math
from collections import Counter

from asof.benchmark_reporting import wilson95

ARMS = ("report_supplied", "no_report")
ANSWER_TYPES = ("span", "multi-span", "arithmetic", "count")
VALID_OUTCOMES = ("correct", "wrong", "abstain")


def exact_mcnemar(with_only: int, without_only: int) -> float:
    if any(type(n) is not int or n < 0 for n in (with_only, without_only)):
        raise ValueError("discordant counts must be nonnegative integers")
    n = with_only + without_only
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(with_only, without_only) + 1))
               / 2**n)


def arm_summary(rows: list[dict], arm: str) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "native_EM": None, "native_F1": None,
                "native_scale_accuracy": None, "coverage": None,
                "EM_Wilson95": None, "scale_Wilson95": None, "coverage_Wilson95": None,
                "counts": {}, "generation_attempts": 0, "timeouts": 0}
    for row in rows:
        value = row[arm]
        if value["native_EM"] not in (0, 1) or value["native_scale_accuracy"] not in (0, 1):
            raise ValueError("native binary metrics must be zero or one")
        if not math.isfinite(value["native_F1"]) or not 0 <= value["native_F1"] <= 1:
            raise ValueError("invalid native F1")
    em = sum(int(r[arm]["native_EM"]) for r in rows)
    scale = sum(int(r[arm]["native_scale_accuracy"]) for r in rows)
    answered = sum(r[arm]["outcome"] in ("correct", "wrong") for r in rows)
    return {
        "n": n, "native_EM": em/n,
        "native_F1": sum(r[arm]["native_F1"] for r in rows)/n,
        "native_scale_accuracy": scale/n, "coverage": answered/n,
        "EM_Wilson95": wilson95(em, n), "scale_Wilson95": wilson95(scale, n),
        "coverage_Wilson95": wilson95(answered, n),
        "counts": dict(Counter(r[arm]["outcome"] for r in rows)),
        "generation_attempts": sum(r[arm]["attempted"] for r in rows),
        "timeouts": sum(r[arm].get("timeout", False) for r in rows),
    }


def contrast(rows: list[dict]) -> dict:
    both = sum(r[ARMS[0]]["native_EM"] == r[ARMS[1]]["native_EM"] == 1 for r in rows)
    with_only = sum(r[ARMS[0]]["native_EM"] == 1 and r[ARMS[1]]["native_EM"] == 0 for r in rows)
    without_only = sum(r[ARMS[0]]["native_EM"] == 0 and r[ARMS[1]]["native_EM"] == 1 for r in rows)
    return {"n": len(rows), "right_only_with_report": with_only,
            "right_only_without_report": without_only, "both_right": both,
            "neither_right": len(rows)-both-with_only-without_only,
            "exact_McNemar_p_descriptive": exact_mcnemar(with_only, without_only) if rows else None}


def report(rows: list[dict]) -> dict:
    if len(rows) != 30 or len({r["id"] for r in rows}) != 30:
        raise ValueError("REAL1 must retain all thirty unique selected questions")
    if any(r["answer_type"] not in ANSWER_TYPES for r in rows):
        raise ValueError("unexpected TAT-QA answer type")
    valid_pairs = [r for r in rows if all(r[a]["outcome"] in VALID_OUTCOMES for a in ARMS)]
    return {
        "arms": {a: arm_summary(rows, a) for a in ARMS},
        "paired_all_selected": contrast(rows),
        "completed_pairs": {
            "both_HTTP_responses": sum(all(r[a].get("response_received", False) for a in ARMS)
                                       for r in rows),
            "both_generations_finished": sum(all(r[a].get("generation_finished", False) for a in ARMS)
                                             for r in rows),
            "both_predictions_valid": len(valid_pairs),
        },
        "paired_valid_predictions_only": contrast(valid_pairs),
        "by_answer_type": {
            kind: {a: arm_summary([r for r in rows if r["answer_type"] == kind], a) for a in ARMS}
            for kind in ANSWER_TYPES
        },
        "limits": "Question-level descriptive intervals ignore shared report dependence. F1 has "
                  "no binomial interval. McNemar is descriptive, not confirmatory. "
                  "No-report correctness may reflect memorization or guessing.",
    }
