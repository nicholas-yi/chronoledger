"""10-K section extraction and Lazy-Prices-style similarity.

Section headers appear twice in most 10-Ks (table of contents, then body). For each item we pick
the header occurrence that yields the longest span before the next item header, which skips the
table of contents. Results include character offsets so every derived claim can cite its source.
"""

from __future__ import annotations

import re
import warnings
from collections import Counter
from dataclasses import dataclass

import numpy as np
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Inline-XBRL 10-Ks are XHTML; the HTML parser handles them correctly for text extraction.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

ITEMS = ["1", "1A", "1B", "1C", "2", "3", "4", "5", "6", "7", "7A", "8", "9", "9A", "9B", "10"]
TARGET_ITEMS = ("1", "1A", "7")
_HEADER = re.compile(r"(?im)^\s*item\s*(\d{1,2}[a-c]?)\s*[\.\:\-\u2013\u2014]?\s*(.{0,200})$")


@dataclass(frozen=True)
class Section:
    item: str
    start: int
    end: int
    text: str


def html_to_text(html: bytes | str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for hidden in soup.select('[style*="display:none"], [style*="display: none"]'):
        hidden.decompose()
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text


def _headers(text: str) -> list[tuple[int, str]]:
    found = []
    for m in _HEADER.finditer(text):
        item = m.group(1).upper()
        if item in ITEMS:
            found.append((m.start(), item))
    return found


def extract_sections(text: str, items: tuple[str, ...] = TARGET_ITEMS) -> dict[str, Section]:
    headers = _headers(text)
    out: dict[str, Section] = {}
    for item in items:
        best: tuple[int, int] | None = None
        for i, (pos, name) in enumerate(headers):
            if name != item:
                continue
            nxt = next((p for p, n in headers[i + 1:] if n != item), len(text))
            if best is None or (nxt - pos) > (best[1] - best[0]):
                best = (pos, nxt)
        if best and best[1] - best[0] > 200:
            out[item] = Section(item, best[0], best[1], text[best[0]:best[1]])
    return out


_TOKEN = re.compile(r"[a-z][a-z\-']+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def cosine_similarity(a: str, b: str) -> float:
    ca, cb = Counter(tokens(a)), Counter(tokens(b))
    if not ca or not cb:
        return float("nan")
    vocab = sorted(set(ca) | set(cb))
    va = np.array([ca[w] for w in vocab], dtype=float)
    vb = np.array([cb[w] for w in vocab], dtype=float)
    return float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))


def jaccard_similarity(a: str, b: str) -> float:
    sa, sb = set(tokens(a)), set(tokens(b))
    if not sa or not sb:
        return float("nan")
    return len(sa & sb) / len(sa | sb)
