"""Seeded metadata-only development rosters; no signal values, outcomes or annotation."""

from __future__ import annotations

import json
from collections.abc import Mapping

import numpy as np
import pandas as pd

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT

SEED = 20261113
META = ["cik", "accession", "form", "knowledge_time", "report_date", "primary_doc", "items"]
EXPORT = [*META, "prev_accession", "prev_knowledge_time", "prev_report_date", "category",
          "metadata_next_report", "followup_end", "selection_envelope_end"]


def filings(lo: str, hi: str, ciks: list[int] | None = None) -> pd.DataFrame:
    filters = [("knowledge_time", ">=", pd.Timestamp(lo, tz="UTC")),
               ("knowledge_time", "<=", pd.Timestamp(hi, tz="UTC"))]
    if ciks is not None:
        filters.append(("cik", "in", ciks))
    return pd.read_parquet(DATA_DIR / "bulk_filings.parquet", columns=META,
                           filters=filters, use_threads=False).reset_index(drop=True)


def sample_metadata(
    candidates: pd.DataFrame, allocations: Mapping[str, int], *, stream: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    required = {"cik", "accession", "knowledge_time", "category"}
    if not required <= set(candidates):
        raise ValueError("metadata selection requires cik/accession/knowledge_time/category")
    frame = candidates[[c for c in EXPORT if c in candidates]].copy()
    rng = np.random.default_rng(np.random.SeedSequence(SEED, spawn_key=(stream,)))
    rows, used, shortfalls = [], set(), {}
    for category, target in allocations.items():
        pool = frame[(frame["category"] == category) & ~frame["cik"].isin(used)]
        issuers = sorted(pool["cik"].unique())
        chosen = rng.choice(issuers, min(target, len(issuers)), replace=False)
        shortfalls[category] = target - len(chosen)
        for cik in chosen:
            choices = pool[pool["cik"] == cik].sort_values(["knowledge_time", "accession"])
            rows.append(choices.iloc[int(rng.integers(len(choices)))])
            used.add(int(cik))
    return pd.DataFrame(rows, columns=frame.columns).reset_index(drop=True), shortfalls


def claims() -> tuple[pd.DataFrame, dict[str, int]]:
    pairs = pd.read_parquet(
        DATA_DIR / "h0_signals.parquet",
        columns=["cik", "accession", "form", "knowledge_time", "prev_accession"],
        filters=[("knowledge_time", ">=", pd.Timestamp("2023-01-01", tz="UTC")),
                 ("knowledge_time", "<=", pd.Timestamp("2024-06-30 23:59:59", tz="UTC"))],
        use_threads=False)
    meta = filings("2021-01-01", "2024-07-31 23:59:59")
    current = meta[["accession", "cik", "form", "knowledge_time", "report_date"]]
    check = pairs.merge(current, on="accession", how="left", suffixes=("", "_metadata"),
                         validate="one_to_one")
    if (check["cik_metadata"].isna().any()
            or not check["cik"].equals(check["cik_metadata"])
            or not (check["form"] == check["form_metadata"]).all()
            or not (check["knowledge_time"] == check["knowledge_time_metadata"]).all()):
        raise ValueError("H0 pair/current filing metadata mismatch; stop rather than resample")
    previous = current.rename(columns={
        "accession": "prev_accession", "cik": "prev_cik", "form": "prev_form",
        "knowledge_time": "prev_knowledge_time", "report_date": "prev_report_date"})
    pairs = pairs.merge(current[["accession", "report_date"]], on="accession", validate="one_to_one")
    pairs = pairs.merge(previous, on="prev_accession", how="left", validate="many_to_one")
    if (pairs["prev_cik"].isna().any() or not (pairs["cik"] == pairs["prev_cik"]).all()
            or not (pairs["form"] == pairs["prev_form"]).all()
            or not (pairs["prev_knowledge_time"] < pairs["knowledge_time"]).all()):
        raise ValueError("previous filing identity/time mismatch; stop rather than resample")
    lag = (pd.to_datetime(pairs["report_date"]) - pd.to_datetime(pairs["prev_report_date"])).dt.days
    if not lag[pairs["form"] == "10-Q"].between(340, 390).all():
        raise ValueError("10-Q pair differs from the existing year-ago rule")
    pairs["category"] = pairs["form"]
    return sample_metadata(pairs, {"10-K": 30, "10-Q": 30}, stream=0)


def endpoints() -> tuple[pd.DataFrame, dict[str, int]]:
    sample = pd.read_parquet(DATA_DIR / "h4_sample.parquet", columns=["cik"])["cik"].tolist()
    meta = filings("2011-01-01", "2018-12-31 23:59:59", sample)
    tenk = meta[meta["form"] == "10-K"].copy()
    tenk["report_date"] = pd.to_datetime(tenk["report_date"])
    tenk = tenk.sort_values(["cik", "report_date", "knowledge_time"])
    following = tenk.groupby("cik")["report_date"].shift(-1)
    gap = (following - tenk["report_date"]).dt.days
    tenk["metadata_next_report"] = following.where(gap.between(300, 430))
    pairs = pd.read_parquet(
        DATA_DIR / "h4_pairs.parquet", columns=["cik", "accession", "knowledge_time", "report_date"],
        filters=[("knowledge_time", ">=", pd.Timestamp("2012-01-01", tz="UTC")),
                 ("knowledge_time", "<=", pd.Timestamp("2018-12-31 23:59:59", tz="UTC"))],
        use_threads=False)
    pairs = pairs.merge(tenk[["accession", "metadata_next_report"]], on="accession",
                         how="left", validate="one_to_one")
    pairs["form"] = "10-K"
    pairs["category"] = np.where(pairs["metadata_next_report"].notna(),
                                 "H4_next_report_present", "H4_next_report_absent_in_envelope")
    regular = meta[meta["form"].isin(["10-K", "10-Q"])
                   & (meta["knowledge_time"] >= pd.Timestamp("2012-01-01", tz="UTC"))].copy()
    regular["followup_end"] = regular["knowledge_time"] + pd.Timedelta(days=365)
    envelope = pd.Timestamp("2018-12-31 23:59:59", tz="UTC")
    regular["category"] = np.where(regular["followup_end"] <= envelope,
                                   "H6_nominal_followup_inside", "H6_nominal_followup_outside")
    combined = pd.concat([pairs, regular], ignore_index=True)
    combined["selection_envelope_end"] = envelope
    return sample_metadata(combined, {
        "H4_next_report_present": 5, "H4_next_report_absent_in_envelope": 5,
        "H6_nominal_followup_inside": 5, "H6_nominal_followup_outside": 5,
    }, stream=1)


def main() -> None:
    for name, builder in (("claims", claims), ("endpoints", endpoints)):
        selected, shortfalls = builder()
        records = json.loads(selected.to_json(orient="records", date_format="iso"))
        output = {
            "note": "METADATA ONLY, not annotated gold or endpoint values. Existing H0 sample "
                    "conditioning is retained for claims; endpoint envelope categories do not "
                    "prove complete observation or actual missing reports.",
            "seed": SEED, "spawn_key": [0 if name == "claims" else 1],
            "status": "incomplete" if any(shortfalls.values()) else "complete_roster_only",
            "shortfalls": shortfalls, "cases": records, "lineage": ledger.lineage(),
        }
        path = PROJECT_ROOT / "results" / f"{name}_audit_roster.json"
        path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        for column in ("annotation_status", "label_value", "evidence_refs", "reason",
                       "annotator_id", "adjudication"):
            selected[column] = ""
        selected.to_csv(PROJECT_ROOT / "results" / f"{name}_annotation_template.csv", index=False)
        print(f"{name}: {len(records)} metadata cases, shortfalls {shortfalls}")


if __name__ == "__main__":
    main()
