"""Exploratory cached-text diagnostics, not semantic gold, public novelty or alpha."""

from __future__ import annotations

import gzip
import hashlib
import io
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lxml import etree, html

from asof.document_scope import (
    filing_document_dates,
    parse_document_date,
    require_eligible_documents,
)
from asof.edgar import response_cache_path
from asof.ledger import file_sha256
from asof.periods import HoldoutAccessError
from asof.sections import cosine_similarity, html_to_text, jaccard_similarity, tokens

SEED = 2026111702
MAX_CASES = 64
MAX_BODY = 16 << 20
MAX_TOTAL_BODY = 512 << 20
METRICS = {
    "backlog": r"\b(?:order\s+)?backlog\b",
    "same_store_sales": r"\b(?:same[\s\-\u2010-\u2014]+store|comparable[\s\-]+store)"
                        r"\s+sales\b",
    "subscribers": r"\bsubscribers?\b",
    "active_users": r"\b(?:monthly|daily)\s+active\s+users?\b",
    "net_revenue_retention": r"\b(?:net\s+(?:dollar|revenue)[\s\-]+retention"
                             r"|(?:dollar|revenue)[\s\-]+based\s+net\s+retention)\b",
    "customer_retention": r"\bcustomer\s+retention\b",
    "churn": r"\b(?:customer|subscriber)\s+churn\b",
    "capacity_utilization": r"\bcapacity\s+utili[sz]ation\b",
}
CUES = re.compile(
    r"\b(?:no longer|ceased|discontinued|divest\w*|sold|redefin\w*|renamed"
    r"|not comparable|changed (?:our|the) (?:definition|methodology))\b", re.IGNORECASE)
NUMBER = re.compile(r"\d")


@dataclass(frozen=True)
class CachedText:
    status: str
    text: str | None
    body_bytes: int
    provenance: dict
    reason: str | None = None


def filing_url(row: dict) -> str:
    return (f"https://www.sec.gov/Archives/edgar/data/{int(row['cik'])}/"
            f"{row['accession'].replace('-', '')}/{row['primary_doc']}")


def pin_filing(row: dict, cache: Path) -> dict:
    require_eligible_documents((filing_document_dates(row),))
    url = filing_url(row)
    path = response_cache_path(url, cache)
    present = path.is_file()
    return {
        **row, "url": url, "cache_present": present,
        "cache_SHA256": file_sha256(path) if present else None,
    }


def assert_development_disclosures(refs: list[dict]) -> None:
    require_eligible_documents(tuple(filing_document_dates(ref) for ref in refs))


def normalized_inline_period(value: str) -> str | None:
    try:
        return parse_document_date(value, "inline_period").isoformat()
    except HoldoutAccessError:
        return None


def read_cached(ref: dict, cache: Path) -> CachedText:
    require_eligible_documents((filing_document_dates(ref),))
    path = response_cache_path(ref["url"], cache)
    provenance = {
        "url": ref["url"], "accession": ref["accession"],
        "stored_knowledge_time_unqualified": ref["knowledge_time"],
        "metadata_report_date": ref["report_date"], "metadata_cik": ref["cik"],
    }
    if not ref["cache_present"]:
        return CachedText("unavailable", None, 0, provenance, "not_cached_at_freeze")
    if not path.is_file():
        return CachedText("unavailable", None, 0, provenance, "cache_missing_after_freeze")
    with path.open("rb") as stream:
        compressed = stream.read((32 << 20) + 1)
    if len(compressed) > 32 << 20:
        return CachedText("unavailable", None, 0, provenance, "compressed_cache_cap")
    if hashlib.sha256(compressed).hexdigest() != ref["cache_SHA256"]:
        raise ValueError(f"frozen cache changed: {ref['accession']}")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            body = stream.read(MAX_BODY + 1)
    except (OSError, EOFError) as exc:
        return CachedText("unavailable", None, 0, provenance, f"cache_decode:{type(exc).__name__}")
    if len(body) > MAX_BODY:
        return CachedText("unavailable", None, len(body), provenance, "body_cap_not_read_complete")
    provenance["body_SHA256"] = hashlib.sha256(body).hexdigest()
    try:
        root = html.fromstring(body)
    except (etree.ParserError, etree.XMLSyntaxError) as exc:
        return CachedText("unavailable", None, len(body), provenance,
                          f"html_parse:{type(exc).__name__}")
    identities: set[int] = set()
    periods: set[str] = set()
    forms: set[str] = set()
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        name = element.get("name", "").rsplit(":", 1)[-1].lower()
        if name in {"entitycentralindexkey", "documentperiodenddate", "documenttype"}:
            value = "".join(element.itertext()).strip()
            if name == "entitycentralindexkey" and value.isdigit():
                identities.add(int(value))
            elif name == "documentperiodenddate":
                periods.add(value)
            elif name == "documenttype":
                forms.add(value)
    provenance.update(inline_ciks=sorted(identities), inline_periods=sorted(periods),
                      inline_forms=sorted(forms))
    if identities and identities != {int(ref["cik"])}:
        return CachedText("unavailable", None, len(body), provenance, "inline_CIK_conflict")
    normalized = {normalized_inline_period(value) for value in periods}
    if None in normalized:
        return CachedText("unavailable", None, len(body), provenance, "inline_period_uninterpretable")
    if normalized and normalized != {ref["report_date"][:10]}:
        return CachedText("unavailable", None, len(body), provenance, "inline_period_conflict")
    if forms and ref["form"] not in forms:
        return CachedText("unavailable", None, len(body), provenance, "inline_form_conflict")
    text = html_to_text(body)
    if not text.strip():
        return CachedText("unavailable", None, len(body), provenance, "empty_text_representation")
    provenance.update(
        text_SHA256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        identity_status="inline_CIK_agrees" if identities else "metadata_only_not_qualified",
        representation="full_cached_primary_document_visible_text_not_semantic_exhaustiveness")
    return CachedText("available", text, len(body), provenance)


def metric_mentions(text: str, pattern: str) -> dict:
    hits = list(re.finditer(pattern, text, flags=re.IGNORECASE))
    evidence = []
    numeric = 0
    for hit in hits:
        start, end = max(0, hit.start() - 150), min(len(text), hit.end() + 350)
        context = text[start:end]
        numeric += bool(NUMBER.search(context))
        if len(evidence) < 3:
            evidence.append({
                "match_start": hit.start(), "match_end": hit.end(),
                "context_start": start, "context_end": end, "context": context,
                "numeric_context_only_not_value_extraction": bool(NUMBER.search(context)),
                "explanation_cues_for_review": sorted({
                    m.group(0).lower() for m in CUES.finditer(context)}),
            })
    return {"alias_mentions": len(hits), "numeric_context_mentions": numeric, "evidence": evidence}


def analyze_case(case: dict, documents: list[CachedText], context: list[CachedText]) -> dict:
    result = {
        "case_id": case["case_id"], "cik": case["cik"],
        "sources": [d.provenance for d in documents],
        "source_statuses": [{"status": d.status, "reason": d.reason} for d in documents],
        "earlier_context": [d.provenance | {"status": d.status, "reason": d.reason} for d in context],
        "public_history_complete": False, "first_public_observability": None,
        "human_gold": False, "semantic_omissions_adjudicated": False,
        "cashflow_direction": "unadjudicated", "uncertainty_direction": "unadjudicated",
        "return_or_cost_evaluation": False,
    }
    if len(documents) != 3:
        raise ValueError("one case requires exactly two prior annual documents and one current")
    if any(d.status != "available" for d in documents):
        return result | {"status": "incomplete_source_coverage", "metrics": {}, "baselines": None,
                         "candidate_count": None, "persistent_alias_controls": []}
    old, previous, current = (d.text for d in documents)
    if old is None or previous is None or current is None:
        raise ValueError("available cached document lacks its text")
    metrics = {}
    candidates = []
    controls = []
    for name, pattern in METRICS.items():
        observations = [metric_mentions(text, pattern) for text in (old, previous, current)]
        repeated = all(o["alias_mentions"] > 0 for o in observations[:2])
        supported = repeated and all(o["numeric_context_mentions"] > 0 for o in observations[:2])
        omitted = supported and observations[2]["alias_mentions"] == 0
        earlier_mentions = [
            d.provenance["accession"] for d in context
            if d.status == "available" and d.text is not None
            and metric_mentions(d.text, pattern)["alias_mentions"] > 0]
        metrics[name] = {
            "observations": observations, "two_prior_numeric_context_support": supported,
            "lexical_omission_candidate_not_semantic_conclusion": omitted,
            "earlier_cached_primary_mentions": earlier_mentions,
            "market_novelty": "unresolved_incomplete_public_history",
        }
        if omitted:
            candidates.append(name)
        elif supported and observations[2]["alias_mentions"] > 0:
            controls.append(name)
    cosine, jaccard = cosine_similarity(previous, current), jaccard_similarity(previous, current)
    if not math.isfinite(cosine) or not math.isfinite(jaccard):
        raise ValueError("nonempty representation has no usable lexical baseline tokens")
    numbers = [set(re.findall(r"\b\d[\d,.%]*", t)) for t in (previous, current)]
    numeric_union = numbers[0] | numbers[1]
    return result | {
        "status": "exploratory_lexical_screen", "metrics": metrics,
        "candidate_metrics": candidates, "candidate_count": len(candidates),
        "persistent_alias_controls": controls,
        "baselines": {
            "cosine_distance": 1 - cosine, "jaccard_distance": 1 - jaccard,
            "relative_length_change": (len(current) - len(previous)) / len(previous),
            "numeric_token_jaccard_distance": (
                1 - len(numbers[0] & numbers[1]) / len(numeric_union) if numeric_union else None),
            "numeric_baseline_status": "available" if numeric_union else "no_numeric_tokens",
            "current_token_count": len(tokens(current)),
        },
    }


def summarize(results: list[dict]) -> dict:
    usable = [r for r in results if r["candidate_count"] is not None]
    candidates = [r for r in usable if r["candidate_count"] > 0]
    controls = [r for r in usable if not r["candidate_count"] and r["persistent_alias_controls"]]
    selected = sorted(candidates, key=lambda r: (-r["candidate_count"], r["case_id"]))[:6]
    selected += sorted(controls, key=lambda r: r["case_id"])[:3]
    selected += [r for r in results if r["status"] == "incomplete_source_coverage"][:3]
    associations = {}
    for field in ("cosine_distance", "jaccard_distance", "relative_length_change"):
        x = [r["candidate_count"] for r in usable]
        y = [r["baselines"][field] for r in usable]
        if len(usable) < 4 or len(set(x)) < 2 or len(set(y)) < 2:
            associations[field] = {
                "status": "not_estimable", "reason": "insufficient_or_constant_screen",
                "n": len(usable), "rho": None}
        else:
            from scipy.stats import spearmanr

            associations[field] = {
                "status": "descriptive_only", "n": len(usable),
                "rho": float(spearmanr(x, y).statistic),
                "interpretation": "not independent incremental information or economic value"}
    return {
        "case_count": len(results), "usable_three_document_cases": len(usable),
        "incomplete_cases": len(results) - len(usable),
        "cases_with_lexical_candidates": len(candidates),
        "cases_with_supported_persistent_aliases": sum(bool(r["persistent_alias_controls"])
                                                    for r in usable),
        "candidate_metric_counts": dict(Counter(m for r in candidates for m in r["candidate_metrics"])),
        "selected_casebook_ids": [r["case_id"] for r in selected],
        "casebook_selection": "up to 6 largest candidate counts, 3 persistent controls, 3 incomplete; "
                             "ties by case ID; deliberately enriched, not a random accuracy audit",
        "baseline_associations": associations,
        "human_label_count": 0, "validated_precision": None, "validated_recall": None,
        "semantic_omission_rate": None, "market_novelty_established": False,
        "incremental_alpha_established": False, "scientific_acceptance": False,
    }
