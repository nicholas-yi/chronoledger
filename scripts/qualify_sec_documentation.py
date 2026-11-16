"""Freeze and execute the first official documentation probe; never requests filings."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.sec_documentation import DocumentationStop, StrictSecDocumentation

CONFIG = PROJECT_ROOT / "results" / "sec_stage1_config.json"
STATUS = PROJECT_ROOT / "results" / "sec_stage1_status.json"
REQUESTS = PROJECT_ROOT / "results" / "sec_stage1_requests.jsonl"
BUDGET = DATA_DIR / "p0_SEC_request_receipt.json"
PLAN = PROJECT_ROOT / "results" / "timestamp_authority_plan.json"
PRIVATE = DATA_DIR / "sec_stage1"
URLS = ("https://www.sec.gov/search-filings/edgar-application-programming-interfaces",)
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "sec_documentation.py",
           PROJECT_ROOT / "tests" / "test_sec_documentation.py"]


def freeze() -> None:
    if any(p.exists() for p in (CONFIG, STATUS, REQUESTS)):
        raise RuntimeError("Stage1 already frozen/attempted; no overwrite")
    budget = json.loads(BUDGET.read_text())
    if budget != {"actual_HTTP_attempts": 46, "ceiling": 150}:
        raise ValueError("request baseline differs; reconcile before freezing")
    config = {
        "kind": "APPROVED STAGE1 DOCUMENTATION ONLY; no accession pilot",
        "URLs_in_order": URLS,
        "selection": "One primary official API field-documentation page already cited by the "
                     "project. Eight is an upper bound, not a request quota. Do not fetch known "
                     "large manuals under this64KiBread cap or invent replacement URLs.",
        "plan_sha256": ledger.file_sha256(PLAN),
        "budget_before": budget, "budget_before_sha256": ledger.file_sha256(BUDGET),
        "source_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
        "scope": "Official documentation definitions only, not issuers or financial observations. "
                 "No real benchmark, filing body/header/index, 48-item roster, source correction, "
                 "price, return, sealed data, model or trial-ledger append.",
        "HTTP_contract": {"max_approved_attempts": 8, "frozen_requests": len(URLS),
                          "historical_ceiling": 150, "timeout_seconds_total_per_request": 30,
                          "max_retained_body_bytes": 65536, "minimum_start_interval_seconds": 0.5,
                          "parallelism": 1, "retries": 0, "redirects": False,
                          "UA": "Existing ASOF_USER_AGENT through asof.config.user_agent()",
                          "read_cap_boundary": "Conservative: body reaching64KiB is unqualified; "
                                               "do not read an extra byte or call it complete."},
        "receipt_semantics": "Append-only started/finished events. Charge the ignored historical "
                             "counter before sending. Status and SHA256 refer to observed bytes; "
                             "an unread error response has zero observed bytes, not a full-body "
                             "hash. Crash/unfinished attempts require review, never automatic resume.",
        "stop": "Any redirect, non2xx,403,429,5xx,transport/deadline,read cap,unsupported encoding,"
                "scope/budget failure. No alternate identity/header/proxy or replacement URL. "
                "If the complete document is unclear, blocked or a JS shell, report the gap. "
                "No accession pilot follows without a new decision.",
        "review": "Record short exact field definitions only, with retrieval/version applicability "
                  "separate from any clock guarantee. General business hours or Z syntax does not "
                  "certify historical JSON/header/index clock accuracy. No automatic qualification.",
        "adapter_negative_tests": "Must pass and be committed before live request; final full-suite "
                                  "result is reported separately after both parts.",
    }
    CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps({"frozen_requests": len(URLS), "config_sha256": ledger.file_sha256(CONFIG)}))


async def run() -> None:
    if STATUS.exists() or REQUESTS.exists():
        raise RuntimeError("Stage1 already attempted; no retry or automatic resume")
    config = json.loads(CONFIG.read_text())
    if ledger.lineage()["git_dirty"] or any(
        ledger.file_sha256(PROJECT_ROOT / p) != h for p, h in config["source_sha256"].items()
    ):
        raise ValueError("commit frozen adapter/tests/URLs before live HTTP")
    if ledger.file_sha256(BUDGET) != config["budget_before_sha256"] or (
        ledger.file_sha256(PLAN) != config["plan_sha256"] or list(URLS) != config["URLs_in_order"]
    ):
        raise ValueError("budget/plan/scope changed since freeze; no request")
    started = time.monotonic()
    result = {"status": "in_progress", "config_sha256": ledger.file_sha256(CONFIG),
              "lineage": ledger.lineage([CONFIG]), "budget_before": config["budget_before"],
              "sources": [], "filing_requests": 0, "roster_drawn": False}
    STATUS.write_text(json.dumps(result, indent=2), encoding="utf-8")
    try:
        async with StrictSecDocumentation(URLS, BUDGET, REQUESTS, PRIVATE) as client:
            for url in URLS:
                body = await client.fetch(url)
                result["sources"].append({"url": url, "complete_bytes": len(body),
                                          "review_status": "awaiting_field_definition_review",
                                          "clock_qualified": False})
        result["status"] = "retrieved_requires_review_no_clock_clearance"
    except DocumentationStop as exc:
        result.update(status="stopped", stop_reason=str(exc))
    finally:
        result.update(budget_after=json.loads(BUDGET.read_text()),
                      wall_seconds=time.monotonic() - started,
                      source_unchanged=all(ledger.file_sha256(PROJECT_ROOT / p) == h
                                           for p, h in config["source_sha256"].items()),
                      clock_certification="BLOCKED",
                      stage2_authorized=False)
        STATUS.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze()
    else:
        asyncio.run(run())
