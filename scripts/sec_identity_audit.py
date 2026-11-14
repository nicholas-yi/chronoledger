"""Bounded SEC-only identity/exit candidate evidence, not a survivorship or payoff certification."""

from __future__ import annotations

import json
import re
import sys

import httpx
import pandas as pd
from prepare_audit_rosters import SEED, filings, sample_metadata

from asof import ledger
from asof.config import PROJECT_ROOT
from asof.edgar import EdgarClient
from asof.sections import html_to_text

MAX_REQUESTS = 300


class RequestBudgetExceeded(RuntimeError):
    pass


class BudgetClient(EdgarClient):
    def __init__(self) -> None:
        super().__init__(max_rps=2.0)
        self.http_attempts = 0
        self._http.event_hooks["request"] = [self._count_request]

    def _count_request(self, request: httpx.Request) -> None:
        if self.http_attempts >= MAX_REQUESTS:
            raise RequestBudgetExceeded("SEC HTTP attempt budget exhausted")
        self._throttle()  # Also covers redirects; conservative extra wait before initial requests.
        self.http_attempts += 1


def text_oracle(text: str, stratum: str) -> dict:
    if not text.strip():
        raise ValueError("empty filing text; stop rather than substitute a case")
    scope = text[:50000]
    if stratum in {"cash_acquisition", "stock_mixed_acquisition"}:
        sections = list(re.finditer(
            r"(?is)\bitem\s+2\s*\.\s*01\b(.*?)(?=\bitem\s+\d+\s*\.\s*\d+\b|\bsignatures?\b|\Z)",
            text))
        if not sections:
            return {"oracle_status": "unresolved", "reason": "Item2.01 text not located",
                    "consideration": "unknown", "evidence": []}
        scope = max((m.group(1) for m in sections), key=len)
    patterns = {
        "cash_terms": r"(?i)\bcash consideration\b|\bper share in cash\b|\bcash per share\b",
        "share_terms": r"(?i)\bstock consideration\b|\bexchange ratio\b|\bshares of common stock\b",
        "bankruptcy_language": r"(?i)\bchapter\s+(?:11|7)\b|\bbankruptcy\b|\breceivership\b",
        "common_equity_language": r"(?i)\bcommon stock\b|\bordinary shares\b",
        "multiple_class_language": r"(?i)\bclass\s+[a-z]\s+(?:common stock|ordinary shares)\b",
    }
    matches = {name: list(re.finditer(pattern, scope)) for name, pattern in patterns.items()}
    cash, stock = bool(matches["cash_terms"]), bool(matches["share_terms"])
    consideration = ("cash_and_shares_candidate" if cash and stock else "cash_terms_candidate"
                     if cash else "share_terms_candidate" if stock else "unknown")
    wanted = {
        "continuing": ["common_equity_language"],
        "cash_acquisition": ["cash_terms", "share_terms"],
        "stock_mixed_acquisition": ["share_terms", "cash_terms"],
        "OTC_bankruptcy": ["bankruptcy_language"],
        "multiple_classes": ["multiple_class_language"],
    }[stratum]
    evidence = []
    for kind in wanted:
        for match in matches[kind][:1]:
            snippet = " ".join(scope[max(0, match.start() - 50):match.end() + 80].split())[:180]
            evidence.append({"kind": kind, "quote": snippet})
    return {
        "oracle_status": "partial_text_support" if evidence else "unresolved",
        "consideration": consideration if "acquisition" in stratum else "not_assessed",
        "evidence": evidence[:2],
        "reason": "Literal documentary hints only: issuer/security mapping, completion, "
                  "per-share entitlement, elections, CVRs, successor/recovery and final "
                  "economic payoff are not independently certified; no case is gold.",
    }


def main() -> None:
    meta = filings("2023-01-01", "2024-06-30 23:59:59")
    annual = meta[meta["form"] == "10-K"]
    acquisition = meta[(meta["form"] == "8-K") & meta["items"].fillna("").str.contains(r"\b2\.01\b")]
    distress = meta[(meta["form"] == "8-K") & meta["items"].fillna("").str.contains(r"\b1\.03\b")]
    pools = pd.concat([
        annual.assign(category="continuing"), acquisition.assign(category="cash_acquisition"),
        acquisition.assign(category="stock_mixed_acquisition"),
        distress.assign(category="OTC_bankruptcy"), annual.assign(category="multiple_classes"),
    ], ignore_index=True)
    allocations = {name: 4 for name in (
        "continuing", "cash_acquisition", "stock_mixed_acquisition",
        "OTC_bankruptcy", "ticker_change_reuse", "multiple_classes")}
    chosen, shortfalls = sample_metadata(pools, allocations, stream=2)
    records = json.loads(chosen.to_json(orient="records", date_format="iso"))
    for row in records:
        row["oracle_status"] = "not_attempted"
    output = {
        "note": "SEC ONLY development candidate evidence; no vendor/price data, "
                "annotation, independent gold, terminal payoff validation or F2 clearance.",
        "seed": SEED, "spawn_key": [2], "target_cases": 24, "cases": records,
        "selection_shortfalls": shortfalls,
        "infeasible_strata": {"ticker_change_reuse": "No dated historical security master in "
                             "the selected SEC metadata; no substitute roster was drawn."},
        "limits": {"actual_HTTP_attempts": MAX_REQUESTS, "max_requests_per_second": 2},
        "source_vintage": "Current cached/downloaded SEC document at the pre-cutoff accession; "
                          "historical content immutability is not independently established.",
        "status": "incomplete", "stop_reason": "interrupted_or_unexpected_error",
    }
    client = BudgetClient()
    try:
        for row in records:
            row["oracle_status"] = "not_completed"
            accepted = pd.Timestamp(row["knowledge_time"])
            if accepted > pd.Timestamp("2024-07-31 23:59:59", tz="UTC"):
                raise ValueError("evidence accession exceeds the allowed cutoff")
            cik, acc, doc = int(row["cik"]), row["accession"], row["primary_doc"]
            row["evidence_accession"] = acc
            row["source_url"] = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
            try:
                raw = client.filing_document(cik, acc, doc)
            except (httpx.HTTPError, FileNotFoundError, RequestBudgetExceeded) as exc:
                row.update(oracle_status="unresolved_fetch", error=repr(exc))
                output["stop_reason"] = "SEC_fetch_or_budget_failure"
                break
            row.update(text_oracle(html_to_text(raw), row["category"]))
            print(f"{row['category']} {acc}: {row['oracle_status']}", file=sys.stderr, flush=True)
        else:
            output["status"] = "candidate_evidence_only_with_shortfalls"
            output["stop_reason"] = None
    finally:
        output["actual_HTTP_attempts"] = client.http_attempts
        output["lineage"] = ledger.lineage()
        client.close()
        (PROJECT_ROOT / "results" / "sec_identity_oracle.json").write_text(
            json.dumps(output, indent=2), encoding="utf-8")
    print(f"SEC evidence: {len(records)} candidate slots, {client.http_attempts} HTTP attempts")


if __name__ == "__main__":
    main()
