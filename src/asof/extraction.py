"""Evidence-grounded extraction of business relationships from 10-K text.

The LLM only reads and quotes. Every returned link must pass deterministic grounding:

1. the evidence quote occurs verbatim (after whitespace/quote normalization) in the source chunk;
2. the partner name occurs in the evidence quote;
3. a revenue percentage, if given, occurs in the evidence quote.

Links failing any check are rejected and counted, so the raw hallucination rate is measurable
without human labels. All model calls are cached by a hash of (model, prompt, schema) so runs replay.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from asof.config import RAW_DIR

OLLAMA_URL = "http://localhost:11434/api/chat"
RELATIONS = ("customer", "supplier", "competitor", "other")

SYSTEM_PROMPT = (
    "You extract business relationships that the text states explicitly about the reporting "
    "company ('we', 'our', 'the Company'). Use only the given text, never outside knowledge. "
    "For each relationship return: partner (the other company's name exactly as written), "
    "relation (customer = buys from the reporting company; supplier = sells to or manufactures "
    "for it; competitor; other), revenue_pct (percent of the reporting company's revenue "
    "attributed to that partner if stated, else null), and evidence (one sentence copied "
    "verbatim from the text). Skip relationships whose partner is not named. "
    "Return an empty list if there are none."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "partner": {"type": "string"},
                    "relation": {"type": "string", "enum": list(RELATIONS)},
                    "revenue_pct": {"type": ["number", "null"]},
                    "evidence": {"type": "string"},
                },
                "required": ["partner", "relation", "revenue_pct", "evidence"],
            },
        }
    },
    "required": ["links"],
}

_CANDIDATE = re.compile(
    r"(?i)(customer|client|supplier|vendor|manufactur|foundr|sourc|purchas|distribut|"
    r"competit|compete|accounted for|% of (?:our )?(?:total |net )?(?:revenue|sales))"
)


@dataclass(frozen=True)
class Link:
    partner: str
    relation: str
    revenue_pct: float | None
    evidence: str


@dataclass
class ExtractionResult:
    accepted: list[Link]
    rejected: list[tuple[Link, str]]


def normalize(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def candidate_chunks(section_text: str, max_chars: int = 2500) -> list[str]:
    """Group sentences that may describe relationships into chunks for the model."""
    sentences = re.split(r"(?<=[\.\!\?])\s+", section_text)
    hits = [s.strip() for s in sentences if _CANDIDATE.search(s) and len(s) < 1500]
    chunks, cur = [], ""
    for s in hits:
        if cur and len(cur) + len(s) + 1 > max_chars:
            chunks.append(cur)
            cur = ""
        cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def ground(link: Link, chunk: str) -> str | None:
    """Return a rejection reason, or None if the link is grounded in the chunk."""
    if link.relation not in RELATIONS:
        return "bad_relation"
    ev, src, partner = normalize(link.evidence), normalize(chunk), normalize(link.partner)
    if not ev or ev not in src:
        return "evidence_not_in_source"
    if not partner or partner not in ev:
        return "partner_not_in_evidence"
    if link.revenue_pct is not None:
        pct = f"{link.revenue_pct:g}"
        if not re.search(rf"\b{re.escape(pct)}(?:\.0+)?\s*(?:%|percent)", ev):
            return "pct_not_in_evidence"
    return None


class Extractor:
    def __init__(self, model: str = "qwen3.5:4b", cache_dir: Path | None = None) -> None:
        self.model = model
        self.cache_dir = cache_dir or RAW_DIR / "llm"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _call(self, chunk: str) -> dict:
        body = {
            "model": self.model,
            "stream": False,
            "format": SCHEMA,
            "think": False,
            "options": {"temperature": 0, "seed": 0},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": chunk},
            ],
        }
        key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / key[:2] / f"{key}.json.gz"
        if path.exists():
            return json.loads(gzip.decompress(path.read_bytes()))
        req = urllib.request.Request(
            OLLAMA_URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=900) as resp:
            out = json.load(resp)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(json.dumps(out).encode()))
        return out

    def extract_chunk(self, chunk: str) -> ExtractionResult:
        raw = self._call(chunk)
        try:
            items = json.loads(raw["message"]["content"]).get("links", [])
        except (json.JSONDecodeError, KeyError, AttributeError):
            items = []
        accepted, rejected = [], []
        for it in items:
            try:
                pct = it.get("revenue_pct")
                link = Link(
                    partner=str(it["partner"]).strip(),
                    relation=str(it["relation"]).strip().lower(),
                    revenue_pct=float(pct) if pct is not None else None,
                    evidence=str(it["evidence"]).strip(),
                )
            except (KeyError, TypeError, ValueError):
                continue
            reason = ground(link, chunk)
            (rejected.append((link, reason)) if reason else accepted.append(link))
        return ExtractionResult(accepted, rejected)

    def extract(self, section_text: str) -> ExtractionResult:
        result = ExtractionResult([], [])
        for chunk in candidate_chunks(section_text):
            r = self.extract_chunk(chunk)
            result.accepted += r.accepted
            result.rejected += r.rejected
        return result
