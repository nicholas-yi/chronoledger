"""One declared four-MiB documentation refetch; preserve the first request verbatim."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.sec_documentation import DocumentationStop, StrictSecDocumentation

CONFIG = PROJECT_ROOT / "results" / "sec_stage1_refetch_config.json"
STATUS = PROJECT_ROOT / "results" / "sec_stage1_refetch_status.json"
REQUESTS = PROJECT_ROOT / "results" / "sec_stage1_refetch_requests.jsonl"
BUDGET = DATA_DIR / "p0_SEC_request_receipt.json"
PRIVATE = DATA_DIR / "sec_stage1_refetch"
URL = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
PROTECTED = [PROJECT_ROOT / "results" / name for name in (
    "sec_stage1_config.json", "sec_stage1_status.json", "sec_stage1_requests.jsonl",
    "sec_stage1_review.json")]
SOURCES = [Path(__file__), PROJECT_ROOT / "src" / "asof" / "sec_documentation.py",
           PROJECT_ROOT / "tests" / "test_sec_documentation.py"]


def freeze() -> None:
    if any(p.exists() for p in (CONFIG, STATUS, REQUESTS)):
        raise RuntimeError("refetch already frozen/attempted")
    if json.loads(BUDGET.read_text()) != {"actual_HTTP_attempts": 47, "ceiling": 150}:
        raise ValueError("refetch must start at47of150")
    value = {
        "kind": "DECLARED SINGLE-URL DOCUMENTATION READ-CAP AMENDMENT",
        "URL": URL, "method": "GET", "historical_attempt": 48,
        "only_operational_change": {"documentation_read_cap_bytes_from": 65536,
                                    "documentation_read_cap_bytes_to": 4 << 20},
        "unchanged": "Same declared ASOF_USER_AGENT, 30s total deadline, <=2starts/s, serial, "
                     "no retries, redirects, encoding/proxy/identity bypass; precharged counter.",
        "scope": "Only this official documentation page. No other URL, filing request or roster.",
        "budget_sha256": ledger.file_sha256(BUDGET),
        "protected_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p)
                             for p in PROTECTED},
        "source_sha256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p) for p in SOURCES},
        "review": "Short verbatim acceptance-field definitions only. Distinguish format, clock/"
                  "time zone and historical applicability. If absent say not defined on this page.",
    }
    CONFIG.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"frozen_config_sha256": ledger.file_sha256(CONFIG)}))


async def run() -> None:
    if STATUS.exists() or REQUESTS.exists():
        raise RuntimeError("refetch already attempted; no retry")
    config = json.loads(CONFIG.read_text())
    if ledger.lineage()["git_dirty"] or ledger.file_sha256(BUDGET) != config["budget_sha256"]:
        raise ValueError("commit freeze and preserve budget before request")
    for path, digest in {**config["source_sha256"], **config["protected_sha256"]}.items():
        if ledger.file_sha256(PROJECT_ROOT / path) != digest:
            raise ValueError("frozen source or original47record changed")
    result = {"status": "in_progress", "config_sha256": ledger.file_sha256(CONFIG),
              "lineage": ledger.lineage([CONFIG]), "field_review": "pending",
              "clock_qualified": False}
    STATUS.write_text(json.dumps(result, indent=2), encoding="utf-8")
    try:
        async with StrictSecDocumentation(
            (URL,), BUDGET, REQUESTS, PRIVATE, read_cap_bytes=4 << 20,
        ) as client:
            body = await client.fetch(URL)
        result.update(status="complete_requires_field_review", complete_bytes=len(body))
    except DocumentationStop as exc:
        result.update(status="stopped", stop_reason=str(exc))
    finally:
        result.update(budget_after=json.loads(BUDGET.read_text()),
                      original47unchanged=all(ledger.file_sha256(PROJECT_ROOT / p) == h
                                             for p, h in config["protected_sha256"].items()),
                      source_unchanged=all(ledger.file_sha256(PROJECT_ROOT / p) == h
                                           for p, h in config["source_sha256"].items()))
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
