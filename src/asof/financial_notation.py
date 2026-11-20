"""Bounded financial notation for claim proofs: compact currency scales, spelled cardinals, revenue aliases.

Policy (financial-notation-v1), declared before the final measurement:
- ISO codes are an explicit uppercase allowlist; the only accepted symbol is the euro sign. ``$``, ``£`` and
  bare "dollars"/"pounds" stay ambiguous because several currencies share them.
- Scale suffixes are lowercase ``k``/``m``/``mn``/``bn``; ``M``/``MM`` conventions differ, so they are refused.
- Spelled amounts are a cardinal from 1 to 999 followed by exactly one scale word and an explicit currency.
- "Turnover" and "top line" are read as revenue only as the bare head noun directly after the issuer's
  possessive or "said its"; employee/inventory/asset/segment turnover, ratios and net sales never qualify.
- One asserted sentence must bind issuer, metric, amount and fiscal year; any trailing clause, other
  unparsed revenue wording, revision or sub-annual language elsewhere in the source defers to review.
"""

from __future__ import annotations

import hashlib
import re

from asof.extraction import normalize
from asof.linked_reader import EvidenceBundle, EvidenceSpan, _amount

CONTRACT = "financial-notation-v1"
ISO_CODES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD")
SUFFIX_SCALE = {"k": "thousand", "m": "million", "mn": "million", "bn": "billion"}
CURRENCY_WORDS = {"euro": "EUR", "euros": "EUR", "pounds sterling": "GBP", "us dollars": "USD",
                  "u.s. dollars": "USD", "united states dollars": "USD"}
_UNITS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_TEENS = ("ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
          "eighteen", "nineteen")
_TENS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_BELOW_100 = rf"(?:(?:{'|'.join(_TENS)})(?:[- ](?:{'|'.join(_UNITS)}))?|{'|'.join(_TEENS)}|{'|'.join(_UNITS)})"
CARDINAL = rf"(?:(?:{'|'.join(_UNITS)})\s+hundred(?:\s+(?:and\s+)?{_BELOW_100})?|{_BELOW_100})"
NUMBER = r"\d[\d,]*(?:\.\d+)?"
ALIAS = r"revenues?|turnover|top[- ]line"
VERB = r"reached|totall?ed|amounted\s+to|came\s+to|was|were"
PERIOD = r"(?:during|for|in)\s+(?:FY\s?|fiscal\s+year\s+|fiscal\s+|financial\s+year\s+)?(?P<year>\d{4})"
AMOUNT = (
    rf"(?:(?P<code>[A-Za-z]{{3}}|\u20ac)\s?(?P<value>{NUMBER})"
    r"(?:(?P<suffix>mn|bn|m|k)|\s+(?P<scale_word>thousand|million|billion))"
    rf"|(?P<words>{CARDINAL})\s+(?P<spelled_scale>thousand|million|billion)\s+"
    r"(?P<currency_words>euros?|pounds\s+sterling|U\.S\.\s+dollars|US\s+dollars|United\s+States\s+dollars))"
)
RESIDUAL_GUARD = (
    r"\b(?:revenues?|turnover|top[- ]line|sales|restat\w*|correct\w*|revis\w*|amend\w*|unreconciled"
    r"|authoritative|quarter\w*|interim|half[- ]year|months|year[- ]to[- ]date|ytd)\b"
)


def cardinal_value(words: str) -> int | None:
    """Exact 1-999 cardinal from words; anything outside the bounded grammar returns None."""
    tokens = [token for token in re.split(r"[\s-]+", normalize(words)) if token != "and"]
    total, index = 0, 0
    if len(tokens) >= 2 and tokens[1] == "hundred":
        if tokens[0] not in _UNITS:
            return None
        total, index = 100*(_UNITS.index(tokens[0])+1), 2
    rest = tokens[index:]
    if not rest:
        return total or None
    if len(rest) == 1 and rest[0] in _UNITS:
        return total+_UNITS.index(rest[0])+1
    if len(rest) == 1 and rest[0] in _TEENS:
        return total+10+_TEENS.index(rest[0])
    if rest[0] in _TENS and len(rest) <= 2:
        tens = 10*(_TENS.index(rest[0])+2)
        if len(rest) == 1:
            return total+tens
        if rest[1] in _UNITS:
            return total+tens+_UNITS.index(rest[1])+1
    return None


def _sentence_pattern(issuer: str) -> re.Pattern:
    entity = r"\s+".join(re.escape(word) for word in issuer.split())
    return re.compile(
        rf"(?:\A|(?<=[.!?])\s+)(?P<sentence>(?P<entity>{entity})(?:'s|\u2019s|\s+said\s+its)\s+"
        rf"(?P<metric>{ALIAS})\s+(?:{VERB})\s+{AMOUNT}\s+{PERIOD}\.)(?=\s|\Z)", re.IGNORECASE)


def _quantity(source: str, match: re.Match) -> tuple[str, str, tuple[EvidenceSpan, ...]] | None:
    if match["code"] is not None:
        code = "EUR" if match["code"] == "\u20ac" else match["code"]
        if code not in ISO_CODES:
            return None
        if match["suffix"] is not None and match["suffix"] not in SUFFIX_SCALE:
            return None
        scale = SUFFIX_SCALE[match["suffix"]] if match["suffix"] else normalize(match["scale_word"])
        value, _ = _amount(source, match["value"], table=False)
        if value is None:
            return None
        scale_group = "suffix" if match["suffix"] else "scale_word"
        spans = (EvidenceSpan("value", *match.span("value")), EvidenceSpan("unit", *match.span("code")),
                 EvidenceSpan("scale", *match.span(scale_group)))
        return value, f"{code.lower()} {scale}", spans
    number = cardinal_value(match["words"])
    currency = CURRENCY_WORDS.get(normalize(match["currency_words"]))
    if number is None or currency is None:
        return None
    spans = (EvidenceSpan("value", *match.span("words")), EvidenceSpan("unit", *match.span("currency_words")),
             EvidenceSpan("scale", *match.span("spelled_scale")))
    return str(number), f"{currency.lower()} {normalize(match['spelled_scale'])}", spans


def year_quantities(source: str, issuer: str, year: str) -> list[tuple[str, str] | None]:
    """Every notation-grammar amount for one issuer-year; None marks an unparseable candidate."""
    if not source or len(source) > 8192:
        return []
    return [None if (quantity := _quantity(source, match)) is None else quantity[:2]
            for match in _sentence_pattern(issuer).finditer(source) if match["year"] == year]


def notation_fact(source: str, issuer: str, metric: str, year: str) -> EvidenceBundle | None:
    """Unique asserted revenue fact for one issuer-year, or None so the claim stays in review."""
    if not source or len(source) > 8192 or normalize(metric) not in ("revenue", "revenues"):
        return None
    matches = list(_sentence_pattern(issuer).finditer(source))
    residual = source
    for match in reversed(matches):
        # Only fully valid sibling sentences are exempt; a near-miss (e.g. GBP20M) keeps blocking the document.
        if _quantity(source, match) is not None:
            residual = residual[:match.start("sentence")]+" "+residual[match.end("sentence"):]
    if re.search(RESIDUAL_GUARD, residual, re.IGNORECASE):
        return None
    selected = [match for match in matches if match["year"] == year]
    if len(selected) != 1:
        return None
    match = selected[0]
    quantity = _quantity(source, match)
    if quantity is None:
        return None
    value, unit, amount_spans = quantity
    spans = (EvidenceSpan("entity", *match.span("entity")), EvidenceSpan("metric", *match.span("metric")),
             *amount_spans, EvidenceSpan("period", *match.span("year")))
    alias = normalize(match["metric"]) not in ("revenue", "revenues")
    return EvidenceBundle(CONTRACT, hashlib.sha256(source.encode()).hexdigest(), issuer, metric, value, unit,
                          year, "declared_revenue_alias" if alias else "bounded_notation", "current", spans)
