"""Parallel, cached per-filing text features.

Downloads run in a thread pool sharing one SEC rate limiter; HTML parsing runs in a process pool.
Each filing is parsed once into ``data/features/<accession>.json.gz``: token counts for the full
document and Items 1A and 7, plus Item 1A paragraphs. Pairwise comparisons are computed later from
these features without re-parsing.
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    wait,
)
from pathlib import Path

import numpy as np

from asof.config import DATA_DIR
from asof.document_scope import DocumentDates, require_eligible_documents

FEATURE_DIR = DATA_DIR / "features"


def feature_path(accession: str) -> Path:
    return FEATURE_DIR / accession[:10] / f"{accession}.json.gz"


def extract_features(raw: bytes, form: str) -> dict:
    from asof.changes import paragraphs
    from asof.sections import extract_sections, html_to_text, tokens

    text = html_to_text(raw)
    items = ("1", "1A", "7") if form.startswith("10-K") else ("2", "1A")
    secs = extract_sections(text, items=items)
    out = {"form": form, "len_full": len(text), "full": dict(Counter(tokens(text)))}
    for k, s in secs.items():
        out[f"sec_{k}"] = dict(Counter(tokens(s.text)))
        out[f"len_{k}"] = len(s.text)
    if "1A" in secs:
        out["paras_1A"] = paragraphs(secs["1A"].text)
    return out


def _parse_job(accession: str, raw: bytes, form: str) -> tuple[str, str | None]:
    try:
        feats = extract_features(raw, form)
    except Exception as exc:  # noqa: BLE001 - recorded per accession
        return accession, f"parse error: {exc!r}"
    path = feature_path(accession)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(gzip.compress(json.dumps(feats).encode()))
    tmp.replace(path)
    return accession, None


def load(accession: str, *, dates: DocumentDates | None = None) -> dict | None:
    require_eligible_documents(None if dates is None else (dates,))
    path = feature_path(accession)
    return json.loads(gzip.decompress(path.read_bytes())) if path.exists() else None


def build(jobs: Iterable[tuple[int, str, str, str]], download_threads: int = 6,
          parse_workers: int = 14, max_inflight: int = 64, *,
          dates_by_accession: Mapping[str, DocumentDates] | None = None) -> dict[str, str]:
    """jobs: (cik, accession, primary_doc, form). Returns {accession: error} for failures."""
    from asof.edgar import EdgarClient

    jobs = list(jobs)
    if not jobs:
        return {}
    require_eligible_documents(
        [dates_by_accession[j[1]] for j in jobs if j[1] in dates_by_accession]
        if dates_by_accession is not None else None)
    if dates_by_accession is None or any(j[1] not in dates_by_accession for j in jobs):
        raise ValueError("D13 requires dates for every feature source, including cached jobs")
    todo = [j for j in jobs if not feature_path(j[1]).exists()]
    client = EdgarClient()
    errors: dict[str, str] = {}
    done = 0

    def fetch(job):
        cik, acc, doc, form = job
        try:
            return acc, client.filing_document(
                cik, acc, doc, dates=dates_by_accession[acc]), form, None
        except Exception as exc:  # noqa: BLE001 - recorded per accession, never dropped
            return acc, None, form, f"download error: {exc!r}"

    with ThreadPoolExecutor(download_threads) as dl, ProcessPoolExecutor(parse_workers) as pp:
        pending_dl: set[Future] = set()
        pending_parse: set[Future] = set()
        it = iter(todo)
        exhausted = False
        while not exhausted or pending_dl or pending_parse:
            while not exhausted and len(pending_dl) + len(pending_parse) < max_inflight:
                try:
                    pending_dl.add(dl.submit(fetch, next(it)))
                except StopIteration:
                    exhausted = True
            finished, _ = wait(pending_dl | pending_parse, return_when=FIRST_COMPLETED, timeout=60)
            for f in finished:
                if f in pending_dl:
                    pending_dl.discard(f)
                    acc, raw, form, err = f.result()
                    if err:
                        errors[acc] = err
                    else:
                        pending_parse.add(pp.submit(_parse_job, acc, raw, form))
                else:
                    pending_parse.discard(f)
                    acc, err = f.result()
                    done += 1
                    if err:
                        errors[acc] = err
                    if done % 250 == 0:
                        print(f"features: {done}/{len(todo)} parsed, {len(errors)} errors",
                              file=sys.stderr, flush=True)
    client.close()
    return errors


def cosine(a: dict[str, int] | None, b: dict[str, int] | None) -> float:
    if not a or not b:
        return float("nan")
    common = set(a) & set(b)
    dot = float(sum(a[w] * b[w] for w in common))
    na = float(np.sqrt(sum(v * v for v in a.values())))
    nb = float(np.sqrt(sum(v * v for v in b.values())))
    return dot / (na * nb) if na and nb else float("nan")


def jaccard(a: dict[str, int] | None, b: dict[str, int] | None) -> float:
    if not a or not b:
        return float("nan")
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb)
