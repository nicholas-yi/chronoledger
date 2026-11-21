"""A5: audit the 2012-2018 H4/H6a filings whose times could change a registered assignment.

Phases (each refuses to repeat): ``freeze`` -> commit -> ``run`` -> ``report``. Metadata only:
header and index pages under the bulk-file CIK path. No companyfacts, price or ledger access.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

import pandas as pd
import pyarrow.dataset as ds
import run_full_timestamps as base

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, user_agent
from asof.filing_clock_basis import clock_basis_test, parse_header_dates, qualify
from asof.filing_header_pilot import parse_header, parse_index, resource_urls
from asof.filing_timestamp_a3 import START_GAP, AdaptiveLimiter
from asof.filing_timestamp_a5 import (
    CEILING,
    DEV,
    FORMAL,
    PREVIOUS_CEILING,
    A5Session,
    sensitive_accessions,
)
from asof.filing_timestamp_audit import AuditGuard
from asof.sec_documentation import DocumentationStop, MetadataUnknown
from asof.timeutil import ET

START_USED = 34670
CONFIG = PROJECT_ROOT / "results" / "timestamp_a5_config.json"
STATUS = PROJECT_ROOT / "results" / "timestamp_a5_status.json"
REPORT = PROJECT_ROOT / "results" / "timestamp_a5_report.json"
A4_R2 = PROJECT_ROOT / "results" / "timestamp_full_a4_report_r2.json"
PRIVATE = DATA_DIR / "timestamp_a5"
ORDER = PRIVATE / "frozen_order.jsonl"
OUTCOMES = PRIVATE / "resource_outcomes.jsonl"
FILINGS = DATA_DIR / "bulk_filings.parquet"
SAMPLE = DATA_DIR / "h4_sample.parquet"
WINDOW = (pd.Timestamp("2011-12-25", tz="UTC"), pd.Timestamp("2020-01-10", tz="UTC"))
WALL = 7200
SOURCES = [PROJECT_ROOT / "scripts" / "run_timestamp_a5.py",
           PROJECT_ROOT / "src" / "asof" / "filing_timestamp_a5.py",
           PROJECT_ROOT / "tests" / "test_filing_timestamp_a5.py"]


def load_filings() -> pd.DataFrame:
    """Metadata columns for the H4 sample window only (the same file H0 reads in full)."""
    table = ds.dataset(FILINGS).to_table(
        columns=["cik", "accession", "form", "knowledge_time", "items"],
        filter=(ds.field("knowledge_time") >= WINDOW[0]) & (ds.field("knowledge_time") <= WINDOW[1]))
    frame = table.to_pandas()
    frame["knowledge_time"] = pd.to_datetime(frame["knowledge_time"], utc=True)
    return frame


def freeze() -> None:
    if CONFIG.exists() or PRIVATE.exists():
        raise RuntimeError("A5 already frozen; preserve it")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": START_USED, "ceiling": PREVIOUS_CEILING}:
        raise ValueError("A5 starts at the recorded A4 end, 34670 of 35000")
    filings = load_filings()
    sample = set(pd.read_parquet(SAMPLE)["cik"])
    reasons = sensitive_accessions(filings, sample)
    rows = filings.set_index("accession").loc[list(reasons)]
    order = []
    for accession, row in rows.iterrows():
        for kind, url in resource_urls(int(row["cik"]), accession).items():
            order.append({"accession": accession, "cik": int(row["cik"]), "form": row["form"],
                          "stored_time": row["knowledge_time"].isoformat(), "kind": kind, "URL": url,
                          "reasons": reasons[accession]})
    PRIVATE.mkdir()
    base.write_lines(ORDER, order)
    value = {
        "kind": "APPROVED CL-TS-A5: 2012-2018 H4/H6a assignment-sensitive filings",
        "approval": "ask_user 2026-11-21 h6_timestamp_audit=audit_264 (ceiling 35,800), after A4.",
        "population_rule": "filing_timestamp_a5.sensitive_accessions: H4-sample filings whose <=5h "
                           "time error could cross the H6a development-window or year edge, flip a "
                           "365-day restatement indicator, or reorder same-company 10-Ks.",
        "scope": {"accessions": len(reasons), "resources": len(order), "counter_start": START_USED,
                  "ceiling": CEILING, "reasons": dict(Counter(r for v in reasons.values() for r in v))},
        "policy": "A4 rules unchanged: 60s uncounted retry on the first 502/504 per URL; counted 600s "
                  "pauses (cap 12) for repeats and 503/429; 3% gateway-rate stop; 2h wall.",
        "report_rule": "A3/A4 qualification rule with the A4 clock basis; the basis must not fail a "
                       "CB1 replication on these older headers when estimable (S1 n>=30), and is "
                       "reported as non-estimable otherwise. Effects compare stored and qualified "
                       "times on H6a development indicators, year, window and H4 10-K order.",
        "budget_change": {"before": {"actual_HTTP_attempts": START_USED, "ceiling": PREVIOUS_CEILING},
                          "after": {"actual_HTTP_attempts": START_USED, "ceiling": CEILING}},
        "input_SHA256": base.pin([FILINGS, SAMPLE, A4_R2]),
        "source_SHA256": base.pin(SOURCES), "order_SHA256": base.pin([ORDER]),
    }
    base.atomic_json(CONFIG, value)
    base.atomic_json(base.BUDGET, value["budget_change"]["after"])
    print(json.dumps({"frozen": value["scope"], "config_SHA256": ledger.file_sha256(CONFIG)}))


def committed_config() -> dict:
    config = json.loads(CONFIG.read_bytes())
    base.verify({**config["input_SHA256"], **config["source_SHA256"], **config["order_SHA256"]})
    lineage = ledger.lineage()
    if lineage["git_dirty"]:
        raise RuntimeError("commit the A5 freeze first")
    committed = subprocess.run(["git", "show", "HEAD:results/timestamp_a5_config.json"],
                               cwd=PROJECT_ROOT, capture_output=True, check=True).stdout
    if committed.replace(b"\r\n", b"\n") != CONFIG.read_bytes().replace(b"\r\n", b"\n"):
        raise RuntimeError("A5 config differs from the committed freeze")
    return config | {"_lineage": lineage}


async def run() -> None:
    config = committed_config()
    if STATUS.exists() or OUTCOMES.exists():
        raise RuntimeError("A5 already attempted; no automatic continuation")
    if json.loads(base.BUDGET.read_bytes()) != {"actual_HTTP_attempts": START_USED, "ceiling": CEILING}:
        raise ValueError("shared counter moved since the A5 freeze")
    user_agent()
    order = base.load_lines(ORDER)
    guard = AuditGuard(base.suspend_clocks, lambda: 0, wall_seconds=WALL)
    status = {"status": "in_progress", "commit": config["_lineage"]["git_commit"],
              "start_UTC": datetime.now(UTC).isoformat(), "resources_recorded": 0}
    session: A5Session | None = None

    def checkpoint(event: dict | None = None) -> None:
        if session:
            status.update(charged=session.charged, throttle_pauses=session.throttle_pauses,
                          short_gateway_retries=session.short_gateway_retries)
        status.update(counter=json.loads(base.BUDGET.read_bytes()), checkpoint_UTC=datetime.now(UTC).isoformat(),
                      wall_seconds=time.monotonic() - guard.started)
        base.atomic_json(STATUS, status)

    checkpoint()
    try:
        async with A5Session({r["URL"] for r in order}, base.BUDGET, PRIVATE, guard, start_used=START_USED,
                             max_pauses=12, limiter=AdaptiveLimiter(gap=START_GAP),
                             on_event=checkpoint) as session:
            for resource in order:
                item, stop = dict(resource), None
                session.current_attempts = []
                try:
                    body = await session.fetch(item["URL"])
                    item["parsed"] = (parse_header(body, item["accession"]) if item["kind"] == "header"
                                      else parse_index(body))
                except MetadataUnknown as exc:
                    item["parsed"] = {"unknown": str(exc)}
                except (DocumentationStop, OSError, ValueError) as exc:
                    item["parsed"] = {"unknown": f"resource_failed:{exc}"}
                    stop = str(exc)
                item["A5_attempts"] = list(session.current_attempts)
                with OUTCOMES.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(item, allow_nan=False) + "\n")
                status["resources_recorded"] += 1
                if stop:
                    raise DocumentationStop(stop)
        status["status"] = "order_complete"
    except (DocumentationStop, OSError, ValueError) as exc:
        status.update(status="stopped_final", stop_reason=str(exc))
    finally:
        if status["status"] == "in_progress":
            error = sys.exception()
            status.update(status="interrupted_final", stop_reason=f"{type(error).__name__}:{error}")
        checkpoint()
    print(json.dumps({k: status.get(k) for k in ("status", "stop_reason", "charged", "resources_recorded")}))


def raw(row: dict) -> bytes:
    good = [a for a in row["A5_attempts"] if a.get("status") == 200 and a.get("body_complete")]
    if not good:
        raise ValueError("no complete recorded body")
    body = (PRIVATE / "raw_metadata" / good[-1]["cache_file"]).read_bytes()
    if hashlib.sha256(body).hexdigest() != good[-1]["SHA256_observed_bytes"]:
        raise ValueError("recorded body hash mismatch")
    return body


def candidates(stored: datetime) -> set[datetime]:
    offset = abs(stored.astimezone(ET).utcoffset())
    return {stored - offset, stored, stored + offset}


def h6a_state(f: pd.DataFrame, times: dict[str, pd.Timestamp]) -> pd.DataFrame:
    """Registered H6a development indicators per base filing under the given time map."""
    f = f.assign(knowledge_time=f["accession"].map(times).fillna(f["knowledge_time"]))
    base_rows = f[f["form"].isin(["10-K", "10-Q"])].copy()
    formal = f[(f["form"] == "10-K/A") | f["items"].fillna("").str.contains(FORMAL)]
    only402 = f[f["items"].fillna("").str.contains(FORMAL)]

    def within(events: pd.DataFrame) -> list[float]:
        by = events.groupby("cik")["knowledge_time"].apply(list).to_dict()
        return [float(any(t < e <= t + timedelta(days=365) for e in by.get(c, [])))
                for c, t in zip(base_rows["cik"], base_rows["knowledge_time"], strict=True)]

    base_rows["in_dev"] = base_rows["knowledge_time"].between(*DEV)
    base_rows["year"] = base_rows["knowledge_time"].dt.year
    base_rows["restate_12m"] = within(formal)
    base_rows["item402_12m"] = within(only402)
    return base_rows.set_index("accession")[["in_dev", "year", "restate_12m", "item402_12m"]]


def report() -> None:
    if REPORT.exists():
        raise RuntimeError("A5 report already exists; preserve it")
    config = committed_config()
    outcomes = base.load_lines(OUTCOMES) if OUTCOMES.exists() else []
    by_accession: dict[str, dict] = {}
    for row in outcomes:
        by_accession.setdefault(row["accession"], {})[row["kind"]] = row
    observations, table = [], []
    for accession, rows in sorted(by_accession.items()):
        header, index = rows.get("header"), rows.get("index")
        obs = {"unknown": "unread"}
        if header and "unknown" not in header["parsed"]:
            try:
                obs = parse_header_dates(raw(header), accession)
            except ValueError as exc:
                obs = {"unknown": f"raw_unavailable:{exc}"}
            observations.append(obs)
        stored = datetime.fromisoformat((header or index)["stored_time"])
        conditional = None
        if (header and index and "unknown" not in header["parsed"] and "unknown" not in index["parsed"]
                and header["parsed"]["header_wall"] == index["parsed"]["index_wall"]):
            conditional = header["parsed"]["UTC_assuming_Eastern"]
        table.append({"accession": accession, "stored": stored, "conditional": conditional,
                      "obs": obs, "reasons": (header or index)["reasons"]})
    replication = clock_basis_test(observations)
    estimable = replication["S1_daylight_16_30_to_17_30_same_day"]["n"] >= 30
    a4_basis = json.loads(A4_R2.read_bytes())["clock_basis"]["basis_accepted_for_qualification"]
    basis = bool(a4_basis) and not (estimable and not replication["passed"])
    qualified, results = {}, []
    for entry in table:
        outside = bool(entry["conditional"]) and datetime.fromisoformat(entry["conditional"]) not in candidates(
            entry["stored"])
        result = qualify({"accession": entry["accession"], "conditional_UTC_assuming_Eastern": entry["conditional"],
                          "outside_frozen_candidate_envelope": outside}, [entry["obs"]], basis)
        if result["qualified_UTC"]:
            qualified[entry["accession"]] = pd.Timestamp(result["qualified_UTC"])
            delta = (datetime.fromisoformat(result["qualified_UTC"]) - entry["stored"]).total_seconds() / 3600
        else:
            delta = None
        results.append({**result, "stored_minus_qualified_hours": None if delta is None else -delta,
                        "reasons": entry["reasons"]})
    filings = load_filings()
    sample = set(pd.read_parquet(SAMPLE)["cik"])
    f = filings[filings["cik"].isin(sample)]
    affected = set(f.loc[f["accession"].isin(qualified), "cik"])
    subset = f[f["cik"].isin(affected)]
    before, after = h6a_state(subset, {}), h6a_state(subset, qualified)
    changed = (before != after).any(axis=1)
    dev_rows = before["in_dev"] | after["in_dev"]
    annual = f[f["form"] == "10-K"]
    swaps = 0
    for _, group in annual[annual["cik"].isin(affected)].groupby("cik"):
        old = list(group.sort_values("knowledge_time", kind="stable")["accession"])
        new = list(group.assign(knowledge_time=group["accession"].map(qualified).fillna(group["knowledge_time"]))
                   .sort_values("knowledge_time", kind="stable")["accession"])
        swaps += old != new
    status = json.loads(STATUS.read_bytes()) if STATUS.exists() else {}
    value = {
        "status": {k: status.get(k) for k in ("status", "stop_reason", "charged", "throttle_pauses",
                                              "short_gateway_retries", "resources_recorded")},
        "config_SHA256": ledger.file_sha256(CONFIG), "report_lineage": config["_lineage"],
        "accessions": len(table), "qualified": len(qualified), "unresolved": len(table) - len(qualified),
        "unresolved_reasons": dict(Counter(x for r in results for x in r["unresolved_reasons"])),
        "stored_minus_qualified_hours": dict(Counter(str(r["stored_minus_qualified_hours"]) for r in results)),
        "clock_basis": {"A4_basis": a4_basis, "CB1R3_on_2012_2018_headers": replication,
                        "CB1R3_estimable": estimable, "basis_accepted_for_qualification": basis},
        "H6a_development_rows_changed": int((changed & dev_rows).sum()),
        "H6a_development_change_details": {
            column: int(((before[column] != after[column]) & dev_rows).sum())
            for column in before.columns},
        "H4_same_company_10K_order_swaps": swaps,
        "counter": json.loads(base.BUDGET.read_bytes()),
        "private_hash_manifest": base.pin([p for p in (ORDER, OUTCOMES, PRIVATE / "requests.jsonl",
                                                        PRIVATE / "waits_and_retries.jsonl") if p.exists()]),
        "limits": "Qualification assumes EDGAR's clock and the Rule 13(a)(2) basis, here tested on "
                  "2022-2024 headers and replicated on these older headers only if estimable. Effects "
                  "use metadata indicators; H6a quiet-revision detection (held companyfacts) was not run.",
    }
    base.atomic_json(REPORT, value)
    print(json.dumps({k: value[k] for k in ("accessions", "qualified", "unresolved", "stored_minus_qualified_hours",
                                            "H6a_development_rows_changed", "H4_same_company_10K_order_swaps")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run", "report"))
    phase = parser.parse_args().phase
    if any(os.environ.get(k) != "1" for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("set numerical library thread caps to 1")
    {"freeze": freeze, "run": lambda: asyncio.run(run()), "report": report}[phase]()
