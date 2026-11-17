"""D13 metadata/file-existence inventory. Never opens a cached filing body."""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.document_scope import filing_document_dates, require_eligible_documents
from asof.edgar import response_cache_path
from asof.kpi_omission import filing_url
from asof.periods import HoldoutAccessError

OUTPUT = PROJECT_ROOT / "results" / "kpi_development_cache_inventory.json"
MINIMUM = 30


def inventory(data_dir: Path = DATA_DIR) -> tuple[dict, list[dict]]:
    import pandas as pd

    columns = ["cik", "accession", "form", "knowledge_time", "report_date", "primary_doc"]
    filters = [
        ("form", "==", "10-K"),
        ("knowledge_time", ">=", pd.Timestamp("2012-01-01", tz="UTC")),
        ("knowledge_time", "<=", pd.Timestamp("2018-12-31 23:59:59", tz="UTC")),
    ]
    frame = pd.read_parquet(
        data_dir / "bulk_filings.parquet", columns=columns, filters=filters, use_threads=False)
    cache = data_dir / "raw" / "sec"
    cached = []
    rejected = 0
    for row in frame.itertuples():
        ref = {
            "cik": int(row.cik), "accession": row.accession, "form": row.form,
            "accepted_at": row.knowledge_time.isoformat(),
            "knowledge_time": row.knowledge_time.isoformat(),
            "report_date": str(row.report_date)[:10], "primary_doc": row.primary_doc,
        }
        try:
            require_eligible_documents((filing_document_dates(ref),))
        except HoldoutAccessError:
            rejected += 1
            continue
        if not isinstance(ref["primary_doc"], str) or not ref["primary_doc"]:
            rejected += 1
            continue
        if response_cache_path(filing_url(ref), cache).is_file():
            cached.append(ref)
    triples = []
    if cached:
        available = pd.DataFrame(cached).sort_values(["cik", "report_date", "knowledge_time"])
        for cik, group in available.groupby("cik"):
            records = group.drop_duplicates("report_date", keep="first").to_dict("records")
            latest = None
            for i in range(2, len(records)):
                three = records[i - 2:i + 1]
                periods = pd.to_datetime([r["report_date"] for r in three])
                times = pd.to_datetime([r["knowledge_time"] for r in three])
                if (all(330 <= (b - a).days <= 400
                        for a, b in pairwise(periods))
                        and all(a < b for a, b in pairwise(times))):
                    latest = three
            if latest is not None:
                triples.append({"cik": int(cik), "annual": latest})
    context_rejections = 0
    context_rows = 0
    if triples:
        context = pd.read_parquet(
            data_dir / "bulk_filings.parquet", columns=[*columns, "items"],
            filters=[("form", "==", "8-K"), ("cik", "in", [r["cik"] for r in triples]),
                     *filters[1:]], use_threads=False)
        context_rows = len(context)
        eligible = []
        for candidate in triples:
            current = pd.Timestamp(candidate["annual"][-1]["knowledge_time"])
            used = context[
                (context.cik == candidate["cik"]) & (context.knowledge_time < current)
                & (context.knowledge_time >= current - pd.Timedelta(days=120))
                & context["items"].fillna("").astype(str).str.contains("2.02", regex=False)
            ].sort_values(["knowledge_time", "accession"]).tail(2)
            refs = [{
                "cik": int(r.cik), "accession": r.accession, "form": r.form,
                "accepted_at": r.knowledge_time.isoformat(),
                "knowledge_time": r.knowledge_time.isoformat(), "report_date": str(r.report_date)[:10],
                "primary_doc": r.primary_doc,
            } for r in used.itertuples()]
            try:
                require_eligible_documents(tuple(
                    filing_document_dates(r) for r in candidate["annual"] + refs))
            except HoldoutAccessError:
                context_rejections += 1
                continue
            eligible.append(candidate | {"context": refs})
        triples = eligible
    result = {
        "status": "sufficient_for_new_freeze" if len(triples) >= MINIMUM else "stopped_insufficient_cache",
        "knowledge_and_period_envelope": ["2012-01-01", "2018-12-31"],
        "metadata_annual_rows": len(frame), "scope_or_metadata_rejections": rejected,
        "cached_eligible_annual_bodies_by_existence": len(cached),
        "eligible_issuer_triples": len(triples), "minimum_required": MINIMUM,
        "used_context_scope_rejections": context_rejections,
        "context_metadata_rows_loaded": context_rows,
        "method": "latest eligible annual triple per issuer; all dates checked including used context",
        "acceptance_mapping": "bulk knowledge_time stores reported SEC acceptance; explicitly "
                              "declared as both date roles, not independently UTC-certified",
        "metadata_columns": columns, "metadata_filters": "10-K,2012-01-01..2018-12-31",
        "document_bodies_read": 0, "document_cache_objects_hashed": 0,
        "new_downloads": 0, "model_calls": 0, "return_evaluations": 0,
        "trial_ledger_rows_appended": 0, "scientific_acceptance": False,
        "old_quarantined_roster_used": False,
        "lineage": ledger.lineage(),
    }
    return result, triples


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError("inventory already recorded; do not overwrite")
    result, _ = inventory()
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["eligible_issuer_triples"] >= MINIMUM else 2


if __name__ == "__main__":
    raise SystemExit(main())
