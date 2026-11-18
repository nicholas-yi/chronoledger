"""Strict projection and descriptive feasibility of an already date-cleared extract.

No file/network access, text parsing, gold generation or financial evaluation.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from itertools import pairwise

from asof.document_scope import (
    filing_document_dates,
    parse_document_date,
    require_eligible_documents,
)
from asof.timeutil import aware_utc

FAMILIES = (
    "backlog", "same_store_sales", "subscribers", "active_users",
    "net_revenue_retention", "customer_retention", "churn", "capacity_utilization",
)


def guard_manifest(manifest: dict) -> dict:
    """Validate metadata for the whole source extract BEFORE its derived text bytes are read."""
    cases = manifest["cases"]
    if not cases or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("nonempty unique manifest cases required")
    refs = [r for case in cases for role in ("annual", "context") for r in case[role]]
    require_eligible_documents(tuple(filing_document_dates(ref) for ref in refs))
    dates = [parse_document_date(value, name) for ref in refs for name, value in (
        ("accepted", ref["accepted_at"]), ("knowledge", ref["knowledge_time"]),
        ("period", ref["report_date"]))]
    return {"guarded_metadata_references": len(refs), "manifest_cases": len(cases),
            "declared_all_role_date_min": min(dates).isoformat(),
            "declared_all_role_date_max": max(dates).isoformat(),
            "source_clock_qualified": False}


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("mention counts must be nonnegative integers, not missing/financial values")
    return value


def project_cases(manifest: dict, cases: list[dict]) -> list[dict]:
    """Keep only dates, lexical counts and coverage. Excerpts/CIKs/URLs never enter the worker."""
    guard_manifest(manifest)
    index = {case["case_id"]: case for case in manifest["cases"]}
    if not cases or len({row["case_id"] for row in cases}) != len(cases):
        raise ValueError("nonempty unique derived case records required")
    projected = []
    for i, row in enumerate(sorted(cases, key=lambda r: r["case_id"]), 1):
        if row["case_id"] not in index:
            raise ValueError("derived case lies outside the guarded manifest")
        original = index[row["case_id"]]
        if row["cik"] != original["cik"] or len(original["annual"]) != 3:
            raise ValueError("derived issuer/triple does not match the manifest")
        if len(row["sources"]) != 3 or len(row["source_statuses"]) != 3:
            raise ValueError("exactly three annual source/provenance rows required")
        for source, ref in zip(row["sources"], original["annual"], strict=True):
            if (source["accession"] != ref["accession"]
                    or source["stored_knowledge_time_unqualified"] != ref["knowledge_time"]
                    or source["metadata_report_date"] != ref["report_date"]):
                raise ValueError("derived source identity/date binding differs from the manifest")
        allowed_context = {ref["accession"] for ref in original["context"]}
        if any(ref["accession"] not in allowed_context for ref in row["earlier_context"]):
            raise ValueError("derived context lies outside the guarded manifest")
        available = all(item["status"] == "available" for item in row["source_statuses"])
        counts = numeric = None
        if available:
            if set(row["metrics"]) != set(FAMILIES):
                raise ValueError("derived metric dictionary differs from the frozen lexical families")
            counts, numeric = [[] for _ in range(3)], [[] for _ in range(3)]
            for name in FAMILIES:
                observations = row["metrics"][name]["observations"]
                if len(observations) != 3:
                    raise ValueError("each lexical family needs three source observations")
                for j, observation in enumerate(observations):
                    alias = _count(observation["alias_mentions"])
                    number = _count(observation["numeric_context_mentions"])
                    if number > alias:
                        raise ValueError("numeric-context count exceeds actual mentions")
                    counts[j].append(alias)
                    numeric[j].append(number)
        if not isinstance(row["public_history_complete"], bool):
            raise TypeError("public history coverage must be explicit")
        projected.append({
            "case_key": f"DEV-FEAS-{i:03d}",
            "documents": [{k: ref[k] for k in ("accepted_at", "knowledge_time", "report_date")}
                          for ref in original["annual"]],
            "contexts": [{k: ref[k] for k in ("accepted_at", "knowledge_time", "report_date")}
                         for ref in original["context"]],
            "annual_sources_available": available, "alias_counts": counts,
            "numeric_context_counts": numeric,
            "public_history_complete": row["public_history_complete"],
            "earlier_context_records": len(row["earlier_context"]),
            "available_context_bodies": sum(ref["status"] == "available"
                                            for ref in row["earlier_context"]),
        })
    return projected


def diagnose_projection(rows: list[dict]) -> dict:
    """Retrospective lexical-feature diagnostics, NOT economic observations or predictive scores."""
    import numpy as np

    from .economic import MetricKey, Observation, numeric_update
    from .trajectories import causal_trajectory

    if not rows or len({row["case_key"] for row in rows}) != len(rows):
        raise ValueError("nonempty unique projected cases required")
    features, errors = [], []
    temporal_issues: Counter[str] = Counter()
    families = {name: {"any_mentions": 0, "all_three_mentions": 0,
                       "any_numeric_context": 0, "changed_last_count": 0}
                for name in FAMILIES}
    complete_sources = state_updates = 0
    for row in rows:
        refs = row["documents"] + row["contexts"]
        require_eligible_documents(tuple(filing_document_dates(ref) for ref in refs))
        if not row["annual_sources_available"]:
            temporal_issues["annual_source_unavailable"] += 1
            continue
        counts = np.asarray(row["alias_counts"], dtype=float)
        numeric = np.asarray(row["numeric_context_counts"], dtype=float)
        if (counts.shape != (3, len(FAMILIES)) or numeric.shape != counts.shape
                or not np.isfinite(counts).all() or not np.isfinite(numeric).all()
                or (counts < 0).any() or (numeric < 0).any() or (numeric > counts).any()):
            raise ValueError("invalid projected lexical-count matrices")
        complete_sources += 1
        for j, name in enumerate(FAMILIES):
            families[name]["any_mentions"] += bool((counts[:, j] > 0).any())
            families[name]["all_three_mentions"] += bool((counts[:, j] > 0).all())
            families[name]["any_numeric_context"] += bool((numeric[:, j] > 0).any())
            families[name]["changed_last_count"] += counts[2, j] != counts[1, j]
        declared = [datetime.fromisoformat(ref["knowledge_time"]) for ref in row["documents"]]
        if any(t.tzinfo is None or t.utcoffset() is None for t in declared):
            temporal_issues["date_only_or_naive_declared_time"] += 1
            continue
        times = tuple(aware_utc(t) for t in declared)
        if not times[0] < times[1] < times[2]:
            temporal_issues["unordered_or_tied_declared_time"] += 1
            continue
        for j, name in enumerate(FAMILIES):
            key = MetricKey(row["case_key"], f"{name}:alias_matches",
                            "regex-match count", "primary-visible-text", "KPI-DEV-v1")
            observations = [Observation(
                key, parse_document_date(ref["report_date"], "period"),
                at, f"source-{k}", float(counts[k, j]))
                for k, (ref, at) in enumerate(zip(row["documents"], times, strict=True))]
            for previous, current in pairwise(observations):
                numeric_update(current, previous)
                state_updates += 1
        trajectory = causal_trajectory(times, counts, as_of=times[-1])
        clock = np.array([(at-times[0]).total_seconds()/86400 for at in times])
        increments = np.diff(np.column_stack((clock, counts)), axis=0)
        a, b = increments
        lag_area = (np.outer(a, b)-np.outer(b, a))/2
        error = float(np.max(np.abs(trajectory.signature.area()-lag_area)))
        if not np.allclose(trajectory.signature.area(), lag_area, atol=1e-8, rtol=1e-10):
            raise FloatingPointError("real-input path area differs from its ordered-lag identity")
        features.append(trajectory.signature.features())
        errors.append(error)
    for family in families.values():
        for key in family:
            family[key] = int(family[key])
    matrix = np.stack(features) if features else None
    feature_summary = {
        "ordered_trajectories": len(features),
        "coordinate_count": int(matrix.shape[1]) if matrix is not None else None,
        "nonconstant_coordinates": int(np.count_nonzero(np.ptp(matrix, axis=0)))
        if matrix is not None else None,
        "numerical_matrix_rank": int(np.linalg.matrix_rank(matrix)) if matrix is not None else None,
        "maximum_ordered_lag_area_error": max(errors) if errors else None,
        "interpretation": "unscaled lexical-count features; rank is scale-sensitive, not effective N",
    }
    blockers = {
        "A": ("proxy_only", ("lexical counts are not independently labelled economic states; "
                            "public-history qualification is not established")),
        "B": ("not_evaluable", "three annual observations are not a complete disclosure opportunity process"),
        "C": ("features_only", "path features computed; no independently labelled target or return test"),
        "D": ("not_evaluable", "no independently qualified dated counterparties/economic exposure fractions"),
        "E": ("not_evaluable", "no approved qualified VAR/cashflow/discount-rate outcome inputs"),
        "F": ("not_evaluable", "no qualified candidate economic forecasts/targets for incremental testing"),
        "G": ("not_evaluable", "no qualified means,uncertainty,costs,borrow or execution inputs"),
        "H": ("not_evaluable", "no qualified empirical return universe or joint feasible outcome supports"),
        "I": ("not_evaluable", "retrospective exposed cohort has no genuine prospective forecast/settlement evidence"),
    }
    if not features:
        blockers["C"] = ("not_evaluable", "no eligible ordered feature trajectories")
    return {
        "source_cases": len(rows), "complete_three_source_cases": complete_sources,
        "numeric_proxy_state_updates": state_updates, "temporal_unavailable": dict(temporal_issues),
        "family_coverage": families, "trajectory_diagnostics": feature_summary,
        "complete_public_history_cases": sum(row["public_history_complete"] for row in rows),
        "earlier_context_records": sum(row["earlier_context_records"] for row in rows),
        "available_context_bodies": sum(row["available_context_bodies"] for row in rows),
        "areas": {area: {"status": status, "reason": reason}
                  for area, (status, reason) in blockers.items()},
        "independent_gold_cases": 0, "semantic_accuracy": None, "incremental_alpha": None,
        "economic_claim_validated": False,
        "interpretation": "real-input unlabelled mechanical feasibility, not independent validation",
    }
