"""Freeze and run the approved conditional-clock metadata pilot; never repair data."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import random
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, RAW_DIR
from asof.edgar import response_cache_path
from asof.filing_header_pilot import (
    EXPECTED_POOL_COUNTS,
    POOLS,
    ScopedFilingMetadata,
    comparison,
    parse_header,
    parse_index,
    pool_for,
    resource_urls,
)
from asof.sec_documentation import DocumentationStop, MetadataUnknown

CONFIG = PROJECT_ROOT / "results" / "header_pilot_config.json"
STATUS = PROJECT_ROOT / "results" / "header_pilot_status.json"
REQUESTS = PROJECT_ROOT / "results" / "header_pilot_requests.jsonl"
BUDGET = DATA_DIR / "p0_SEC_request_receipt.json"
QUEUE = DATA_DIR / "p0_assignment_queue.parquet"
METADATA = DATA_DIR / "p0_pair_metadata_comparison.parquet"
PRIVATE = DATA_DIR / "header_pilot"
PLAN = PROJECT_ROOT / "results" / "timestamp_authority_plan.json"
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "filing_header_pilot.py",
           PROJECT_ROOT / "src" / "asof" / "sec_documentation.py",
           PROJECT_ROOT / "src" / "asof" / "timeutil.py",
           PROJECT_ROOT / "tests" / "test_filing_header_pilot.py"]


def freeze() -> None:
    if any(p.exists() for p in (CONFIG, STATUS, REQUESTS)):
        raise RuntimeError("pilot already frozen/attempted; no resampling")
    if json.loads(BUDGET.read_text()) != {"actual_HTTP_attempts": 48, "ceiling": 150}:
        raise ValueError("pilot baseline must be48of150")
    q = pd.read_parquet(QUEUE, columns=[
        "accession", "pair_time", "bulk_time", "CIKs_agree", "source_times_agree",
        "candidate_times", "clock_issues", "assignment_sensitive"], use_threads=False)
    m = pd.read_parquet(METADATA, columns=["accession", "cik_pair", "cik_bulk"], use_threads=False)
    frame = q.merge(m, on="accession", validate="one_to_one", how="outer", indicator=True)
    if not frame["_merge"].eq("both").all() or len(frame) != 21502:
        raise ValueError("metadata identity inventory differs")
    for column in ("pair_time", "bulk_time"):
        stamps = pd.to_datetime(frame[column], utc=True)
        if not ((stamps >= "2022-01-01") & (stamps < "2024-07-01")).all():
            raise ValueError("metadata observation envelope differs; no sampling/request")
    frame["pool"] = [pool_for(r) for r in frame.to_dict("records")]
    counts = tuple(int((frame["pool"] == p).sum()) for p in POOLS)
    if counts != EXPECTED_POOL_COUNTS:
        raise ValueError(f"exclusive pools differ from plan: {counts}")
    rng, roster = random.Random(2026111601), []
    for pool in POOLS:
        part = frame.loc[frame["pool"] == pool].set_index("accession")
        for accession in rng.sample(sorted(part.index), 8):
            row = part.loc[accession]
            urls = resource_urls(int(row.cik_pair), accession)
            caches = {}
            for kind, url in urls.items():
                path = response_cache_path(url, RAW_DIR / "sec")
                caches[kind] = ({"path": str(path.relative_to(DATA_DIR)),
                                 "SHA256": ledger.file_sha256(path)} if path.exists() else None)
            roster.append({"accession": accession, "pool": pool, "cik_pair": int(row.cik_pair),
                           "cik_bulk": int(row.cik_bulk), "pair_time": row.pair_time,
                           "bulk_time": row.bulk_time, "URLs": urls, "cached": caches})
    if len({r["accession"] for r in roster}) != 48:
        raise ValueError("pilot accession identities not unique")
    value = {
        "kind": "APPROVED CONDITIONAL EASTERN-CLOCK PILOT; NOT TIMESTAMP CERTIFICATION",
        "seed": 2026111601, "selection": "One Random(seed); pool priority as listed; sample8from "
            "sorted accession IDs per pool without replacement. No filtering, backfill or resampling.",
        "pool_counts": dict(zip(POOLS, counts, strict=True)), "roster": roster,
        "observation_envelope": "Already-used2022-to2024June acceptance/role metadata only. "
            "No fundamental holdout outcomes, XBRL facts, filing bodies/exhibits, scores, market "
            "data or return observations. Metadata dates do not open fundamental/return seals.",
        "clock_assumption": "Stage1 page supplies no acceptance-field clock definition. Owner's "
            "new decision permits CONDITIONAL comparison assuming header Eastern wall time, "
            "not a change to registered knowledge time or clearance of either JSON source.",
        "URL_identity": "Use original pair metadata CIK only as archive address. Preserve bulk "
            "CIK and observed header roles; do not treat path/firstCIK/accession prefix as issuer "
            "truth and do not remap after response. Redirects stop, never try an alternateCIK.",
        "protocol": {"max_new_HTTP_attempts": 96, "historical_start": 48,
                     "authorized_total_max": 144, "historical_ceiling": 150,
                     "requests_per_second": 2, "parallelism": 1, "timeout_seconds": 30,
                     "body_bound_bytes": 65536, "wall_seconds": 1800, "retries": 0,
                     "redirects": False},
        "unknown_policy": "Read-cap or404missing metadata is unknown and does not stop; never "
            "parse a partial body or count it as agreement. Other non2xx,403/429/5xx,transport,"
            "redirect,budget/scope/integrity/wall stop whole pilot. Cache hits consume no request.",
        "budget_SHA256": ledger.file_sha256(BUDGET),
        "input_SHA256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p)
                        for p in (QUEUE, METADATA, PLAN)},
        "source_SHA256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
        "limits": "Stratified diagnostic, not cohort error rate/certification. No repair, correction "
            "release,CIK remap,financial rerun,holdout opening or ledger row. P0 stays blocked.",
    }
    CONFIG.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"roster": 48, "pools": value["pool_counts"],
                      "config_SHA256": ledger.file_sha256(CONFIG)}))


def summarize(rows: list[dict]) -> dict:
    return {p: {
        "accessions": sum(r["pool"] == p for r in rows),
        "conditional_classes": dict(Counter(r["comparison"]["class"] for r in rows if r["pool"] == p)),
        "header_unknown": sum("unknown" in r["header"] for r in rows if r["pool"] == p),
        "index_unknown": sum("unknown" in r["index"] for r in rows if r["pool"] == p),
        "index_wall_agree": sum(r["comparison"]["index_header_wall_agree"] is True
                                for r in rows if r["pool"] == p),
        "index_wall_conflict": sum(r["comparison"]["index_header_wall_agree"] is False
                                   for r in rows if r["pool"] == p),
    } for p in POOLS}


async def run() -> None:
    if STATUS.exists() or REQUESTS.exists():
        raise RuntimeError("pilot already attempted; no automatic continuation")
    config = json.loads(CONFIG.read_text())
    if ledger.lineage()["git_dirty"] or ledger.file_sha256(BUDGET) != config["budget_SHA256"]:
        raise ValueError("commit frozen roster/source and preserve budget")
    for path, digest in {**config["source_SHA256"], **config["input_SHA256"]}.items():
        if ledger.file_sha256(PROJECT_ROOT / path) != digest:
            raise ValueError("frozen pilot source/input changed")
    rows = [{**r, "header": {"unknown": "not_attempted"}, "index": {"unknown": "not_attempted"}}
            for r in config["roster"]]
    output = {"status": "in_progress", "config_SHA256": ledger.file_sha256(CONFIG),
              "items": rows, "lineage": ledger.lineage([CONFIG]),
              "clock_assumption": config["clock_assumption"],
              "timestamp_repairs": 0, "CIK_remaps": 0, "P0": "BLOCKED"}
    started, cpu_started = time.monotonic(), time.process_time()

    def persist() -> None:
        STATUS.write_text(json.dumps(output, indent=2), encoding="utf-8")

    persist()
    stop = None
    try:
        urls = tuple(u for r in rows for u in r["URLs"].values())
        async with ScopedFilingMetadata(urls, BUDGET, REQUESTS, PRIVATE) as client:
            for row in rows:
                for kind, url in row["URLs"].items():
                    if time.monotonic() - started >= 1800 - 30:
                        raise DocumentationStop("pilot_wall_budget")
                    cached = row["cached"][kind]
                    row[kind] = {"unknown": "resource_started", "URL": url,
                                 "cache_hit": bool(cached), "HTTP_attempted": not bool(cached)}
                    persist()
                    try:
                        if cached:
                            path = DATA_DIR / cached["path"]
                            if ledger.file_sha256(path) != cached["SHA256"]:
                                raise DocumentationStop("frozen_cache_changed")
                            with gzip.open(path, "rb") as stream:
                                raw = stream.read(65536)
                            if len(raw) >= 65536:
                                raise MetadataUnknown("cached_metadata_at_read_cap")
                            provenance = {"cache_hit": True, **cached}
                        else:
                            raw = await client.fetch(url)
                            provenance = {"cache_hit": False, "request": dict(client.last_record)}
                    except MetadataUnknown as exc:
                        row[kind] = {"unknown": str(exc), "URL": url,
                                     "cache_hit": bool(cached),
                                     "request": None if cached else dict(client.last_record)}
                        persist()
                        continue
                    try:
                        value = (parse_header(raw, row["accession"])
                                 if kind == "header" else parse_index(raw))
                    except ValueError as exc:
                        row[kind] = {"unknown": str(exc), "URL": url, "provenance": provenance}
                        raise DocumentationStop(str(exc)) from exc
                    candidate = value.get("UTC_assuming_Eastern")
                    if candidate and datetime.fromisoformat(candidate).date().isoformat() >= "2024-07-01":
                        raise DocumentationStop("header_outside_metadata_envelope")
                    row[kind] = {**value, "URL": url, "provenance": provenance}
                    persist()
        output["status"] = "complete_conditional_diagnostic"
    except (DocumentationStop, ValueError, OSError) as exc:
        stop = str(exc)
        output.update(status="stopped", stop_reason=stop)
    finally:
        for row in rows:
            for kind in ("header", "index"):
                if row[kind].get("unknown") == "not_attempted":
                    row[kind]["unknown"] = f"not_attempted:{stop or 'unexpected_interruption'}"
                elif row[kind].get("unknown") == "resource_started":
                    row[kind]["unknown"] = f"resource_failed:{stop or 'unexpected_interruption'}"
            row["comparison"] = comparison(row, row["header"], row["index"])
        after = json.loads(BUDGET.read_text())["actual_HTTP_attempts"]
        output.update(pool_summary=summarize(rows), budget_start=48, budget_final=after,
                      new_HTTP_attempts=after - 48, roster_rows_accounted_for=48,
                      resources={"wall_seconds": time.monotonic() - started,
                                 "Python_CPU_seconds": time.process_time() - cpu_started},
                      limits="Every roster row accounted for, including unattempted/unknown; not "
                             "all observed if stopped. API/bulk columns are stored representations, "
                             "not new API downloads. Clock assumption unqualified; no population "
                             "certification or source promotion.")
        persist()
        print(json.dumps({"status": output["status"], "budget_final": after,
                          "stop": stop, "pools": output["pool_summary"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze()
    else:
        asyncio.run(run())
