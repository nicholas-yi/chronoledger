"""Rate-limited, disk-cached SEC EDGAR client.

Every response is cached under ``data/raw/sec`` keyed by URL, so pipelines are replayable and
the SEC is not re-queried. The cache is never committed (data/ is gitignored).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from asof.bulk import FrozenFactWindow, filter_companyfacts, require_fact_window
from asof.config import RAW_DIR, user_agent
from asof.document_scope import DocumentDates, require_eligible_documents

SEC_MAX_RPS = 8.0  # below the commonly cited 10 req/s ceiling


def response_cache_path(url: str, cache_dir: Path) -> Path:
    """Locate a URL's existing cache without creating a client or making a request."""
    digest = hashlib.sha256(url.encode()).hexdigest()
    return cache_dir / digest[:2] / f"{digest}.gz"


class EdgarClient:
    def __init__(self, cache_dir: Path | None = None, max_rps: float = SEC_MAX_RPS) -> None:
        self.cache_dir = cache_dir or RAW_DIR / "sec"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._min_interval = 1.0 / max_rps
        self._lock = threading.Lock()
        self._last = 0.0
        self._http = httpx.Client(
            headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"},
            timeout=60.0,
            follow_redirects=True,
        )

    def _cache_path(self, url: str) -> Path:
        return response_cache_path(url, self.cache_dir)

    def _throttle(self) -> None:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def get_bytes(self, url: str, *, refresh: bool = False) -> bytes:
        path = self._cache_path(url)
        if path.exists() and not refresh:
            return gzip.decompress(path.read_bytes())
        delay = 1.0
        for attempt in range(6):
            self._throttle()
            try:
                resp = self._http.get(url)
            except httpx.TransportError:
                if attempt == 5:
                    raise
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code == 404:
                raise FileNotFoundError(url)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(gzip.compress(resp.content))
            tmp.replace(path)
            return resp.content
        raise RuntimeError(f"giving up on {url}")

    def get_json(self, url: str, *, refresh: bool = False) -> Any:
        return json.loads(self.get_bytes(url, refresh=refresh))

    def submissions(self, cik: int, *, refresh: bool = False) -> list[dict[str, Any]]:
        """All filings for a CIK, merging the 'recent' block with paged history files."""
        base = "https://data.sec.gov/submissions/"
        top = self.get_json(f"{base}CIK{cik:010d}.json", refresh=refresh)
        blocks = [top["filings"]["recent"]]
        for page in top["filings"].get("files", []):
            blocks.append(self.get_json(base + page["name"], refresh=refresh))
        rows: list[dict[str, Any]] = []
        for block in blocks:
            keys = list(block.keys())
            for i in range(len(block["accessionNumber"])):
                rows.append({k: block[k][i] for k in keys})
        meta = {k: top.get(k) for k in ("cik", "name", "tickers", "exchanges", "sic", "entityType")}
        for row in rows:
            row["_entity"] = meta
        return rows

    def companyfacts(
        self, cik: int, *, refresh: bool = False, scope: FrozenFactWindow | None = None,
    ) -> dict[str, Any]:
        """Filter returned facts, not raw response bytes; never authorizes held research."""
        require_fact_window(scope)
        return filter_companyfacts(self.get_json(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", refresh=refresh
        ), scope, source_kind="api_response")

    def filing_document(
        self, cik: int, accession: str, document: str, *,
        dates: DocumentDates | None = None,
    ) -> bytes:
        require_eligible_documents(None if dates is None else (dates,))
        folder = accession.replace("-", "")
        return self.get_bytes(f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{document}")

    def filing_header(self, cik: int, accession: str) -> str:
        folder = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}-index-headers.html"
        return self.get_bytes(url).decode("latin-1")

    def close(self) -> None:
        self._http.close()
