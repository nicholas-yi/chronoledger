"""One-shot, aggregate-only coverage cost of the shared guards on real 10-K MD&A text.

Pre-declared protocol (frozen before any filing body is read):
- Population: cached 10-K primary documents in bulk_filings with knowledge_time inside the D13
  development window (every body read passes the EDGAR client's require_eligible_documents check);
  cache only, no network. Filings and issuers in the private review packet are excluded; only the
  packet's accession and CIK fields are read, and neither is printed nor stored.
- Sample: one filing per issuer (lowest sha256(accession)), then the 150 lowest-hash issuers.
- Candidates: MD&A (Item 7) sentences containing a revenue/sales word and a dollar amount.
- Windows: the sentence alone, +/-1 sentence and +/-3 sentences, capped at 8192 characters.
- Measures: share of windows the shared admission guard would defer (split into pre-existing
  checks versus the new text-integrity and dispute/estimate vocabulary), share the notation
  residual guard would defer, and aggregate trigger-term and character-name counts.
- Output: aggregate counts only. No passage, sentence or excerpt is printed or stored. A deferral
  is a coverage cost, not an error; this measures neither accuracy nor correctness.
- Round 2 (declared after round 1, before running it): MD&A text first passes the declared
  normalize_filing_text ingestion step; measured on the round-1 sample (exposed aggregates) and on a
  fresh disjoint sample of the next 150 issuers by the same hash order.
- Round 3 (declared after round 2 exposed an imagin* stem over-match, before running it): normalized,
  on a further fresh disjoint sample (issuers ranked 301-450 by the same hash order).
"""

import argparse
import hashlib
import json
import os
import re
import time
import unicodedata
from collections import Counter
from math import sqrt
from pathlib import Path

import pandas as pd

from asof.document_scope import DocumentDates, HoldoutAccessError
from asof.edgar import EdgarClient, response_cache_path
from asof.financial_notation import RESIDUAL_GUARD
from asof.reader_fields import (
    DISPUTED_OR_NONASSERTED,
    source_admission_issues,
    text_integrity_issues,
)
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt
from asof.sections import extract_sections, html_to_text
from asof.text_normalization import normalize_filing_text

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = 150
SOURCES = ("scripts/measure_guard_coverage_real.py", "src/asof/reader_fields.py", "src/asof/financial_notation.py",
           "src/asof/sections.py", "src/asof/edgar.py", "src/asof/document_scope.py", "src/asof/runtime.py")
ROUND2_SOURCES = (*SOURCES, "src/asof/text_normalization.py", "tests/test_text_normalization.py",
                  "results/guard_coverage_real.json")
ROUND3_SOURCES = (*ROUND2_SOURCES, "results/guard_coverage_real_v2.json")
REVENUE = re.compile(r"\b(?:net\s+)?(?:revenues?|sales)\b", re.IGNORECASE)
DOLLARS = re.compile(r"\$\s?[0-9][0-9,]*(?:\.[0-9]+)?(?:\s*(?:million|billion|thousand))?", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
PRE_EXISTING = (
    re.compile(r"\b(?:hypothetical|illustrative|fictional)\s+example\b|\bnot\s+(?:an?\s+)?actual\s+disclosure\b",
               re.IGNORECASE),
    re.compile(r"\b(?:these|all|the\s+above)\s+(?:amounts|figures|values|data)\b[^.\n]{0,100}"
               r"\b(?:quarter(?:ly)?|year.to.date|forecasts?|illustrative|hypothetical)\b", re.IGNORECASE),
)


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if n == 0:
        return None
    p = k/n
    d = 1+z*z/n
    c = p+z*z/(2*n)
    h = z*sqrt(p*(1-p)/n+z*z/(4*n*n))
    return [round((c-h)/d, 4), round((c+h)/d, 4)]


def sample_rows(excluded_accessions: set[str], excluded_ciks: set[int], start: int = 0) -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data" / "bulk_filings.parquet",
                         columns=["cik", "accession", "form", "report_date", "primary_doc", "knowledge_time"])
    df = df[(df.form == "10-K") & df.primary_doc.notna() & (df.primary_doc != "")]
    df = df[(df.knowledge_time >= pd.Timestamp("2012-01-01", tz="UTC"))
            & (df.knowledge_time <= pd.Timestamp("2018-12-31 23:59:59", tz="UTC"))]
    df = df[~df.accession.isin(excluded_accessions) & ~df.cik.isin(excluded_ciks)].copy()
    df["url"] = [f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{r.accession.replace('-', '')}/{r.primary_doc}"
                 for r in df.itertuples()]
    df = df[[response_cache_path(url, ROOT / "data" / "raw" / "sec").exists() for url in df.url]].copy()
    df["key"] = [hashlib.sha256(acc.encode()).hexdigest() for acc in df.accession]
    df = df.sort_values("key").drop_duplicates("cik", keep="first")
    return df.iloc[start:start+SAMPLE]


def window_flags(window: str, target: str) -> dict:
    shared = source_admission_issues(window, ())
    pre = any(pattern.search(window) for pattern in PRE_EXISTING)
    integrity = bool(text_integrity_issues(window))
    dispute = DISPUTED_OR_NONASSERTED.search(window) is not None
    residual = window.replace(target, " ")
    return {"shared_any": bool(shared), "pre_existing": pre, "integrity": integrity, "dispute_vocabulary": dispute,
            "new_only": (integrity or dispute) and not pre,
            "notation_residual": re.search(RESIDUAL_GUARD, residual, re.IGNORECASE) is not None}


def measure(client: EdgarClient, rows: pd.DataFrame, *, normalize: bool) -> dict:
    names = ("sentence", "pm1", "pm3")
    totals = {name: Counter() for name in names}
    per_filing = {name: [] for name in names}
    terms, characters = Counter(), Counter()
    counts = Counter()
    repairs: Counter = Counter()
    for row in rows.itertuples():
        dates = DocumentDates(row.knowledge_time, row.knowledge_time, row.report_date)
        try:
            raw = client.filing_document(int(row.cik), row.accession, row.primary_doc, dates=dates)
        except HoldoutAccessError:
            counts["ineligible_dates"] += 1
            continue
        counts["filings_read"] += 1
        section = extract_sections(html_to_text(raw), items=("7",)).get("7")
        if section is None:
            counts["no_mdna"] += 1
            continue
        body = section.text
        if normalize:
            body, changed = normalize_filing_text(body)
            repairs.update(changed)
        sentences = [s.strip() for s in SENTENCE.split(re.sub(r"\s+", " ", body)) if s.strip()]
        hits = [i for i, s in enumerate(sentences) if REVENUE.search(s) and DOLLARS.search(s)]
        if not hits:
            counts["mdna_without_candidates"] += 1
            continue
        counts["filings_with_candidates"] += 1
        counts["candidate_sentences"] += len(hits)
        filing = {name: Counter() for name in names}
        for i in hits:
            for name, radius in zip(names, (0, 1, 3)):
                window = " ".join(sentences[max(0, i-radius):i+radius+1])[:8192]
                flags = window_flags(window, sentences[i])
                filing[name]["windows"] += 1
                filing[name].update(key for key, value in flags.items() if value)
                if name == "pm1":
                    terms.update(m.group(0).lower() for m in DISPUTED_OR_NONASSERTED.finditer(window))
                    characters.update(unicodedata.name(ch, f"U+{ord(ch):04X}") for ch in window
                                      if text_integrity_issues(ch))
        for name in names:
            totals[name].update(filing[name])
            per_filing[name].append(filing[name]["shared_any"]/filing[name]["windows"])
    keys = ("shared_any", "pre_existing", "integrity", "dispute_vocabulary", "new_only", "notation_residual")
    return {
        "counts": dict(counts), "normalization_repairs": dict(repairs) if normalize else None,
        "windows": {name: {"windows": totals[name]["windows"], **{
            key: {"deferred": totals[name][key], "rate": round(totals[name][key]/totals[name]["windows"], 4),
                  "wilson95": wilson(totals[name][key], totals[name]["windows"])} for key in keys},
            "filing_macro_mean_shared_any": round(sum(per_filing[name])/len(per_filing[name]), 4)
            if per_filing[name] else None} for name in names},
        "top_dispute_terms_pm1": terms.most_common(20),
        "top_integrity_characters_pm1": characters.most_common(10),
        "sample": {"filings_planned": len(rows), "issuers": int(rows.cik.nunique()),
                   "accessions_sha256": hashlib.sha256("\n".join(sorted(rows.accession)).encode()).hexdigest(),
                   "knowledge_time_min": str(rows.knowledge_time.min()), "knowledge_time_max": str(rows.knowledge_time.max())},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args(argv)
    destination = ROOT / "results" / {1: "guard_coverage_real.json", 2: "guard_coverage_real_v2.json",
                                      3: "guard_coverage_real_v3.json"}[args.round]
    if destination.exists():
        raise FileExistsError("coverage receipt exists; never overwrite or retry")
    lineage = frozen_receipt(ROOT, {1: SOURCES, 2: ROUND2_SOURCES, 3: ROUND3_SOURCES}[args.round])
    started = time.monotonic()
    packet = json.loads((ROOT / "data" / "reader_review_v1" / "packet.json").read_bytes())
    excluded_accessions = {item["provenance"]["accession"] for item in packet["items"]}
    excluded_ciks = {int(item["provenance"]["cik"]) for item in packet["items"]}
    os.environ.setdefault("ASOF_USER_AGENT", "Nicholas Yi nicholasyiofficial@gmail.com")
    client = EdgarClient()
    try:
        if args.round == 1:
            measured = {"round1": measure(client, sample_rows(excluded_accessions, excluded_ciks), normalize=False)}
        elif args.round == 3:
            measured = {"second_fresh_disjoint_sample_normalized": measure(
                client, sample_rows(excluded_accessions, excluded_ciks, start=2*SAMPLE), normalize=True)}
        else:
            measured = {
                "same_sample_normalized_exposed": measure(
                    client, sample_rows(excluded_accessions, excluded_ciks), normalize=True),
                "fresh_disjoint_sample_normalized": measure(
                    client, sample_rows(excluded_accessions, excluded_ciks, start=SAMPLE), normalize=True),
            }
    finally:
        client.close()
    result = {
        "status": "complete_aggregate_only_guard_coverage_on_real_mdna", "round": args.round,
        "protocol": __doc__, **(measured["round1"] if args.round == 1 else {"measurements": measured}),
        "exclusions": {"review_accessions": len(excluded_accessions), "review_issuers": len(excluded_ciks),
                       "identifiers_printed_or_stored": False},
        "no_passages_stored": True, "network_requests_expected": 0, "accuracy_or_correctness_measured": False,
        "lineage": lineage,
    }
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    write_receipt(destination, result)
    blocks = [measured["round1"]] if args.round == 1 else list(measured.values())
    print(json.dumps([{key: block[key] for key in ("counts", "normalization_repairs", "top_dispute_terms_pm1",
                                                    "top_integrity_characters_pm1", "sample")}
                      | {"windows": {name: {k: (v["rate"] if isinstance(v, dict) else v) for k, v in w.items()}
                                     for name, w in block["windows"].items()}} for block in blocks], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
