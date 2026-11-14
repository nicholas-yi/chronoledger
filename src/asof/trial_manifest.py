"""Supplementary trial classification and prospective gates; never modifies the ledger."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from asof import ledger
from asof.config import PROJECT_ROOT

Purpose = Literal["scientific", "repeat_vintage", "engineering", "timing", "unknown"]


def build_manifest(entries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, set[str]] = {}
    seen: dict[tuple[str, str, str], int] = {}
    attempts = []
    for index, entry in enumerate(entries, 1):
        hypothesis, digest, period = (entry.get(k) for k in ("hypothesis", "config_hash", "period"))
        config, metrics = entry.get("config"), entry.get("metrics")
        if (not all(isinstance(v, str) and v for v in (hypothesis, digest, period))
                or not isinstance(config, dict)
                or (metrics is not None and not isinstance(metrics, dict))):
            raise ValueError(f"malformed ledger entry at row {index}")
        counts.setdefault(hypothesis, set()).add(digest)
        key = (hypothesis, period, digest)
        declared = config.get("purpose")
        purpose: Purpose = "unknown"
        reason = "purpose_not_established"
        if config.get("test") == "h0_full_runtime" or declared == "timing":
            purpose, reason = "timing", "explicit_runtime_check"
        elif declared in ("engineering", "optimization_equivalence"):
            purpose, reason = "engineering", "explicit_engineering_purpose"
        elif declared in ("scientific", "repeat_vintage"):
            purpose, reason = declared, "explicit_purpose"
        elif declared is None and hypothesis in {"H0", "H1n", "H4", "H5a", "H5b", "H5c", "H6"}:
            purpose, reason = "scientific", "recognized_legacy_hypothesis"
        previous = seen.get(key)
        if purpose == "scientific" and previous is not None:
            purpose, reason = "repeat_vintage", "same_hypothesis_period_configuration"
        seen.setdefault(key, index)
        output_status = "missing" if not metrics else metrics.get("execution_status", "recorded_unreviewed")
        scientific_status = None if metrics is None else metrics.get("scientific_status")
        attempts.append({
            "ledger_row": index, "logged_at": entry.get("logged_at"),
            "hypothesis": hypothesis, "period": period, "config_hash": digest,
            "purpose": purpose, "classification_reason": reason, "previous_attempt_row": previous,
            "output_status": output_status, "recorded_scientific_status": scientific_status,
            "lineage": entry.get("lineage"),
            "matrix_eligibility": "unavailable",
            "matrix_reason": "ledger summaries are not persisted aligned return series",
            "formal_H1": False if hypothesis == "H1n" else None,
        })
    return {
        "schema_version": 1,
        "note": "Supplementary classification, not new inference or a reduction of registered N. "
                "Unknown/failed/invalid/engineering/repeated entries remain present.",
        "registered_N_per_hypothesis": {h: len(v) for h, v in sorted(counts.items())},
        "attempts": attempts,
    }


@dataclass(frozen=True)
class ProtocolDecision:
    status: Literal["supported", "not_supported", "unavailable"]
    reasons: tuple[str, ...]
    supplementary_holm_p: tuple[float, float] | None


def co_primary_decision(
    hypothesis: str,
    *,
    monthly_t: float | None,
    event_change_t: float | None,
    delisting_effects: Mapping[float, float | None],
    referee_passed: bool | None,
    requires_tfidf: bool,
    tfidf_t: float | None,
) -> ProtocolDecision:
    """Apply Lead-D4 to supplied evidence, not to the existing development outputs.

    Monthly/scenario/TF-IDF effects are oriented positive; event_change_t is on an
    increasing-change score (expected negative). Scenario effects must be the same
    registered statistic under 0%, -30%, -100%, not opportunistically chosen metrics.
    """
    if hypothesis not in {"H0", "H1", "H3"}:
        raise ValueError("co-primary gate supports H0, formal H1 and H3 only; H1n is not H1")
    if set(delisting_effects) != {0.0, -0.3, -1.0}:
        raise ValueError("all three registered delisting assumptions are required")
    if hypothesis == "H1" and not requires_tfidf:
        raise ValueError("formal H1 requires D3 TF-IDF agreement")
    values = [monthly_t, event_change_t, *delisting_effects.values()]
    if requires_tfidf:
        values.append(tfidf_t)
    if referee_passed is None or any(v is None or not math.isfinite(v) for v in values):
        return ProtocolDecision("unavailable", ("missing_or_nonfinite_required_evidence",), None)
    assert monthly_t is not None and event_change_t is not None
    oriented_event = -event_change_t
    p = [math.erfc(t / math.sqrt(2)) / 2 for t in (monthly_t, oriented_event)]
    order = sorted(range(2), key=p.__getitem__)
    adjusted = [0.0, 0.0]
    adjusted[order[0]] = min(1.0, 2 * p[order[0]])
    adjusted[order[1]] = max(adjusted[order[0]], p[order[1]])
    reasons = []
    if monthly_t < (2.0 if hypothesis == "H0" else 3.0):
        reasons.append("v1_monthly_threshold_or_direction")
    if any(v is None or v <= 0 for v in delisting_effects.values()):
        reasons.append("delisting_direction")
    if not referee_passed:
        reasons.append("referee_gate")
    if monthly_t <= 0 or oriented_event <= 0 or max(monthly_t, oriented_event) < 3.2:
        reasons.append("v2_co_primary_threshold_or_direction")
    if requires_tfidf and (tfidf_t is None or tfidf_t < 2.0):
        reasons.append("D3_TFIDF_agreement")
    return ProtocolDecision("not_supported" if reasons else "supported", tuple(reasons),
                            (adjusted[0], adjusted[1]))


def inference_availability(
    series: pd.DataFrame | None, *, endpoint_kind: str, persisted: bool,
    family_complete: bool, registered_count: int,
) -> dict[str, dict[str, str]]:
    reason = None
    if endpoint_kind != "monthly_net_returns":
        reason = "incomparable_endpoint"
    elif not persisted or series is None:
        reason = "persisted_aligned_series_missing"
    elif not family_complete or len(series.columns) != registered_count:
        reason = "registered_family_incomplete"
    elif (registered_count < 2 or len(series) < 2 or not series.index.is_unique
          or not series.index.is_monotonic_increasing or not series.columns.is_unique
          or not np.isfinite(series.to_numpy(dtype=float)).all()
          or (series.std(ddof=1) <= 0).any()):
        reason = "invalid_or_degenerate_aligned_series"
    if reason:
        return {k: {"status": "unavailable", "reason": reason} for k in ("DSR", "PBO")}
    assert series is not None
    return {
        "DSR": {"status": "available", "reason": "inputs_only_not_computed"},
        "PBO": {"status": "available" if len(series) >= 32 else "not_estimable",
                "reason": "inputs_only_not_computed" if len(series) >= 32
                          else "16_blocks_require_at_least_32_aligned_months"},
    }


def main() -> None:
    if not ledger.LEDGER_PATH.exists():
        raise FileNotFoundError(ledger.LEDGER_PATH)
    entries = ledger.read_ledger()
    result = build_manifest(entries)
    result["source_ledger"] = "results/trial_ledger.jsonl"
    result["generation_lineage"] = ledger.lineage()
    result["project_inference"] = inference_availability(
        None, endpoint_kind="monthly_net_returns", persisted=False, family_complete=False,
        registered_count=result["registered_N_per_hypothesis"].get("H0", 0))
    path = PROJECT_ROOT / "results" / "trial_manifest.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Manifest: {len(entries)} preserved attempts; {path.name}")


if __name__ == "__main__":
    main()
