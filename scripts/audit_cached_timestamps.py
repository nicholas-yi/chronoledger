"""Reconcile cached header/index metadata only. No HTTP, source promotion or input repair."""

from __future__ import annotations

import gzip
import html
import json
import re
import time
from collections import Counter
from pathlib import Path

import pandas as pd
from calibrate_inference import resident_bytes
from p0_acceptance_audit import header_fields

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, RAW_DIR
from asof.edgar import response_cache_path

COMPARISON = DATA_DIR / "p0_pair_metadata_comparison.parquet"
QUEUE = DATA_DIR / "p0_assignment_queue.parquet"
HTTP_RECEIPT = DATA_DIR / "p0_SEC_request_receipt.json"
OUTPUT = PROJECT_ROOT / "results" / "p0_cached_authority_audit.json"


def cached_text(url: str, cache: Path) -> tuple[str | None, dict | None]:
    path = response_cache_path(url, cache)
    if not path.exists():
        return None, None
    with gzip.open(path, "rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("cached header/index exceeds bounded metadata read")
    return raw.decode("latin-1"), {"url": url, "sha256": ledger.file_sha256(path)}


def cached_evidence(cik: int, accession: str, cache: Path) -> dict:
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
    header, header_asset = cached_text(f"{base}/{accession}-index-headers.html", cache)
    index, index_asset = cached_text(f"{base}/{accession}-index.html", cache)
    result = {
        "header_cached": header is not None, "index_cached": index is not None,
        "assets": [a for a in (header_asset, index_asset) if a is not None],
    }
    if header is None:
        return result
    result.update(header_fields(header))
    match = None if index is None else re.search(
        r"Accepted\s*</div>\s*<div[^>]*>\s*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)",
        html.unescape(index), re.IGNORECASE,
    )
    result["index_Accepted"] = None if match is None else match.group(1)
    result["header_index_wall_match"] = (
        None if match is None or result["header_raw"] is None
        else re.sub(r"\D", "", match.group(1)) == result["header_raw"]
    )
    return result


def main() -> None:
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit source before the cached metadata audit")
    start, cpu = time.monotonic(), time.process_time()
    receipt_hash = ledger.file_sha256(HTTP_RECEIPT)
    inputs = [COMPARISON, QUEUE, HTTP_RECEIPT]
    comparison = pd.read_parquet(COMPARISON, columns=[
        "cik_pair", "cik_bulk", "accession", "knowledge_time_pair", "knowledge_time_bulk",
    ], use_threads=False)
    queue = pd.read_parquet(QUEUE, columns=["accession", "assignment_sensitive"], use_threads=False)
    frame = comparison.merge(queue, on="accession", validate="one_to_one", how="outer", indicator=True)
    if not frame["_merge"].eq("both").all() or frame.drop(columns="_merge").isna().any().any():
        raise ValueError("cached comparison and queue identities/required metadata differ")
    counts, records, assets = Counter(), [], {}
    output = {"status": "incomplete", "new_HTTP_attempts": 0, "timestamp_repairs": 0,
              "CIK_remaps": 0, "authority_certified": False}
    try:
        for row in frame.itertuples():
            if time.process_time() - cpu > 120 or resident_bytes() >= 1 << 30:
                raise RuntimeError("cached audit CPU/RSS ceiling")
            sources = [cached_evidence(int(cik), row.accession, RAW_DIR / "sec")
                       for cik in sorted({row.cik_pair, row.cik_bulk})]
            for source in sources:
                for asset in source.pop("assets"):
                    assets[asset["url"]] = asset
            present = [s for s in sources if s["header_cached"]]
            clocks = {s["UTC_if_header_ET"] for s in present if s.get("UTC_if_header_ET")}
            raw_clocks = {s["header_raw"] for s in present if s.get("header_raw")}
            candidate = next(iter(clocks)) if len(clocks) == 1 and len(raw_clocks) == 1 else None
            match = any(s.get("header_index_wall_match") is True for s in present)
            issues = sorted({s["header_clock_issue"] for s in present if s.get("header_clock_issue")})
            candidate = None if issues else candidate
            record = {
                "accession": row.accession, "assignment_sensitive": bool(row.assignment_sensitive),
                "header_cached": bool(present), "own_index_wall_match": match,
                "conflicting_cached_header_clocks": len(raw_clocks) > 1 or len(clocks) > 1,
                "clock_issues": "; ".join(issues), "conditional_UTC_if_header_ET": candidate,
                "conditional_matches_pair": None if candidate is None else (
                    pd.Timestamp(candidate) == row.knowledge_time_pair),
                "conditional_matches_bulk": None if candidate is None else (
                    pd.Timestamp(candidate) == row.knowledge_time_bulk),
                "multi_party_header": any(len(s.get("header_CIKs", [])) > 1 for s in present),
            }
            records.append(record)
            counts["metadata_rows"] += 1
            for key in ("header_cached", "own_index_wall_match", "multi_party_header",
                        "conflicting_cached_header_clocks"):
                counts[key] += int(record[key])
            counts["sensitive_rows"] += int(record["assignment_sensitive"])
            counts["sensitive_with_cached_header"] += int(
                record["assignment_sensitive"] and record["header_cached"])
            counts["conditional_pair_matches"] += int(record["conditional_matches_pair"] is True)
            counts["conditional_bulk_matches"] += int(record["conditional_matches_bulk"] is True)
            counts["neither_source_matches_conditional_ET"] += int(
                candidate is not None and not record["conditional_matches_pair"]
                and not record["conditional_matches_bulk"])
        if ledger.file_sha256(HTTP_RECEIPT) != receipt_hash:
            raise RuntimeError("SEC request receipt changed during the offline audit")
        pd.DataFrame(records).to_parquet(DATA_DIR / "p0_cached_authority_rows.parquet", index=False)
        output["status"] = "cached_coverage_diagnostic_only"
    finally:
        output.update(
            counts=dict(counts), cached_assets=list(assets.values()),
            prior_SEC_request_receipt_sha256=receipt_hash,
            resources={"CPU_seconds": time.process_time() - cpu,
                       "wall_seconds": time.monotonic() - start,
                       "peak_resident_bytes": resident_bytes()},
            lineage=ledger.lineage(inputs),
            limits="Cached header/index agreement and unique ET conversion are conditional evidence, "
                   "not field-clock certification, full coverage or co-registrant role adjudication. "
                   "Missing cache is unknown, not agreement. No scores, prices or financial outcomes read.",
        )
        OUTPUT.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": output["status"], "counts": output["counts"]}))


if __name__ == "__main__":
    main()
