"""Exact Batch B rerun reconciliation and conditional current-vintage DEVELOPMENT diagnostics."""

from __future__ import annotations

import json
import math
import subprocess

import numpy as np
import pandas as pd
from scipy import stats

from asof import ledger
from asof.config import PROJECT_ROOT
from asof.inference import expected_max_sharpe, probabilistic_sharpe_ratio, sharpe
from asof.trial_manifest import registered_co_primary_decision

BASELINE = "15b8a2d0b53942dda7627fdabbaf934334beceef"


def differences(old, new, path="") -> list[dict]:
    if isinstance(old, dict):
        found = []
        for key, value in old.items():
            if key not in new:
                found.append({"path": f"{path}/{key}", "reason": "missing_field"})
            else:
                found.extend(differences(value, new[key], f"{path}/{key}"))
        return found
    if isinstance(old, list):
        if not isinstance(new, list) or len(old) != len(new):
            return [{"path": path, "reason": "length_mismatch"}]
        return [d for i, (a, b) in enumerate(zip(old, new, strict=True))
                for d in differences(a, b, f"{path}/{i}")]
    if isinstance(old, float) and isinstance(new, float) and math.isnan(old) and math.isnan(new):
        return []
    return [] if old == new else [{"path": path, "old": old, "new": new}]


def current_family_diagnostic(matrix: pd.DataFrame, registered_n: int) -> dict:
    if (len(matrix) < 3 or len(matrix.columns) < 2 or not matrix.index.is_unique
            or not matrix.columns.is_unique or not np.isfinite(matrix.to_numpy()).all()
            or (matrix.std(ddof=1) <= 0).any() or registered_n < len(matrix.columns)):
        raise ValueError("invalid aligned diagnostic matrix or registered N")
    srs = np.array([sharpe(matrix[c].to_numpy()) for c in matrix])
    benchmark = expected_max_sharpe(registered_n, float(srs.var(ddof=1)))
    output = {}
    for column, sr in zip(matrix.columns, srs, strict=True):
        r = matrix[column].to_numpy()
        output[column] = {
            "per_month_SR": float(sr),
            "conditional_DSR": probabilistic_sharpe_ratio(
                float(sr), len(r), float(stats.skew(r)),
                float(stats.kurtosis(r, fisher=False)), benchmark),
        }
    return {
        "label": "DEVELOPMENT DIAGNOSTIC, current-vintage SR variance, registered N; "
                 "not full historical-family inference or support",
        "registered_N": registered_n, "current_columns": len(matrix.columns),
        "aligned_months": [str(m) for m in matrix.index], "SR_benchmark": benchmark,
        "results": output,
        "PBO": {"status": "not_estimable" if len(matrix) < 32 else "not_computed",
                "reason": "16 blocks require at least32 aligned months; no automatic computation"},
        "full_historical_family_DSR": {"status": "unavailable",
                                      "reason": "older/invalid configuration aligned streams absent"},
    }


def baseline(name: str):
    content = subprocess.run(
        ["git", "show", f"{BASELINE}:results/{name}"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True).stdout
    return json.loads(content)


def main() -> None:
    results = PROJECT_ROOT / "results"
    old_h0 = baseline("returns_h0_development.json")
    h0 = json.loads((results / "returns_h0_development.json").read_text())
    old_h4 = baseline("h4_development.json")
    h4 = json.loads((results / "h4_development.json").read_text())
    report = {
        "baseline_commit": BASELINE,
        "H4_deltas": differences(old_h4["results"], h4["results"]),
        "H0_summary_differences": differences(old_h0["results"], h0["results"])
                                  + differences(old_h0["coverage"], h0["coverage"])
                                  + differences(old_h0["n_trials"], h0["n_trials"]),
        "note": "Elapsed time is not a summary metric. New monthly series are output-only. "
                "No tolerance-based matching or rerun toward a preferred answer.",
        "lineage": ledger.lineage(),
    }
    (results / "batch_b_rerun_comparison.json").write_text(json.dumps(report, indent=2))
    if report["H0_summary_differences"]:
        raise RuntimeError("H0 exact summary mismatch: stop B2; evidence preserved, no DSR computed")
    families: dict[str, dict[str, pd.Series]] = {"H0": {}, "H1n": {}}
    decisions = {}
    for variant in h0["results"]:
        name = variant["variant"]
        family = "H0" if "raw" in name else "H1n"
        for assumption, rows in variant["monthly_return_series"].items():
            monthly = variant["monthly_missing_return_sensitivity"][assumption]
            frame = pd.DataFrame(rows)
            if (len(frame) != monthly["months"] or not frame["return_month"].is_unique
                    or float(frame["ls_net"].mean()) != monthly["mean_net"]
                    or float(frame["ls_gross"].mean()) != monthly["mean_gross"]):
                raise ValueError("persisted series does not exactly reconcile to its summary")
            idx = pd.PeriodIndex(frame["return_month"], freq="M")
            if idx.max() > pd.Period("2024-07", "M"):
                raise ValueError("persisted series exceeds permitted return cutoff")
            families[family][f"{name}:{assumption}"] = pd.Series(frame["ls_net"].to_numpy(), index=idx)
        if family == "H0":
            decision = registered_co_primary_decision(
                "H0", monthly_t=variant["monthly"]["alpha_t"], event_change_t=None,
                delisting_effects={float(a): m["alpha"] for a, m in
                                   variant["monthly_missing_return_sensitivity"].items()},
                referee_passed=None, requires_tfidf=False, tfidf_t=None)
            decisions[name] = {"status": decision.status, "reasons": decision.reasons,
                               "note": "Required neutralized event co-primary not evaluated; "
                                       "raw descriptive panel is not substituted."}
        else:
            decisions[name] = {"status": "not_applicable", "reason": "H1n is not formal H1"}
    output = {
        "label": "DEVELOPMENT ONLY; no support claim or new strategy/configuration",
        "families": {h: current_family_diagnostic(pd.concat(list(v.values()), axis=1,
                      keys=list(v), join="inner"), ledger.n_trials(h)) for h, v in families.items()},
        "D4": decisions, "lineage": ledger.lineage(),
    }
    (results / "current_vintage_diagnostics.json").write_text(json.dumps(output, indent=2))
    print(json.dumps({"H0_exact_summary_match": True, "H4_changed_fields": len(report["H4_deltas"]),
                      "diagnostic_months": {h: len(v["aligned_months"])
                                            for h, v in output["families"].items()}}))


if __name__ == "__main__":
    main()
