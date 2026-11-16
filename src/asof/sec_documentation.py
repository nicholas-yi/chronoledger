"""Strict, documentation-only SEC requests. Not an EdgarClient replacement."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from asyncio import sleep as rate_sleep
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit

import httpx

from asof.config import user_agent

MAX_BYTES = 65536
TIMEOUT_SECONDS = 30
MIN_INTERVAL_SECONDS = 0.5
MAX_ATTEMPTS = 8
HISTORICAL_CEILING = 150


class DocumentationStop(RuntimeError):
    pass


class MetadataUnknown(DocumentationStop):
    """A bounded/missing resource, explicitly unqualified rather than a client-wide stop."""


class StrictSecDocumentation:
    max_attempts = MAX_ATTEMPTS
    authorized_total_ceiling = HISTORICAL_CEILING

    def __init__(
        self, allowed_urls: tuple[str, ...], budget_path: Path, receipt_path: Path,
        cache_dir: Path, *, transport: httpx.AsyncBaseTransport | None = None,
        read_cap_bytes: int = MAX_BYTES,
    ) -> None:
        if type(read_cap_bytes) is not int or read_cap_bytes not in (MAX_BYTES, 4 << 20):
            raise ValueError("documentation read cap must be the frozen64KiB or approved4MiB")
        if not allowed_urls or len(allowed_urls) > self.max_attempts:
            raise ValueError("URL count exceeds scoped request allowance")
        if receipt_path.exists():
            raise DocumentationStop("receipt_already_exists_no_automatic_resume")
        self.allowed_urls = frozenset(allowed_urls)
        self.read_cap_bytes = read_cap_bytes
        self.budget_path, self.receipt_path, self.cache_dir = budget_path, receipt_path, cache_dir
        self.attempts = 0
        self.stopped = False
        self.active = False
        self.thread = threading.get_ident()
        self.last_started: float | None = None
        self.requested: set[str] = set()
        self.last_record: dict | None = None
        self.client = httpx.AsyncClient(
            headers={"User-Agent": user_agent(), "Accept-Encoding": "identity"},
            follow_redirects=False, timeout=TIMEOUT_SECONDS, trust_env=False,
            transport=transport or httpx.AsyncHTTPTransport(retries=0),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        await self.client.aclose()

    def budget(self) -> dict:
        value = json.loads(self.budget_path.read_text())
        used, ceiling = value.get("actual_HTTP_attempts"), value.get("ceiling")
        if type(used) is not int or used < 0 or ceiling != HISTORICAL_CEILING or used > ceiling:
            raise DocumentationStop("invalid_historical_budget")
        return value

    def append(self, row: dict) -> None:
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with self.receipt_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()

    def path_allowed(self, path: str) -> bool:
        return not path.lower().startswith("/archives/")

    def unknown_resource(self, reason: str) -> bool:
        return False

    async def fetch(self, url: str) -> bytes:
        if self.stopped:
            raise DocumentationStop("adapter_already_stopped")
        info = urlsplit(url)
        reason = None
        if self.active or threading.get_ident() != self.thread:
            reason = "single_thread_serial_scope_failure"
        elif (
            url not in self.allowed_urls or url in self.requested or info.scheme != "https"
            or info.netloc != "www.sec.gov" or info.query or info.fragment
            or not self.path_allowed(info.path)
        ):
            reason = "URL_scope_failure_or_duplicate_no_retry"
        if reason:
            self.stopped = True
            self.append({"event": "not_sent", "url": url, "reason": reason,
                         "UTC": datetime.now(UTC).isoformat()})
            raise DocumentationStop(reason)
        self.active = True
        record = {"event": "finished", "url": url, "status": None, "bytes": 0,
                  "SHA256_observed_bytes": hashlib.sha256(b"").hexdigest(),
                  "body_complete": False, "attempted": False, "stop_reason": None}
        body = bytearray()
        started = time.monotonic()
        try:
            budget = self.budget()
            if budget["actual_HTTP_attempts"] >= self.authorized_total_ceiling or (
                self.attempts >= self.max_attempts
            ):
                raise DocumentationStop("request_budget_exhausted")
            if self.last_started is not None:
                await rate_sleep(max(0, MIN_INTERVAL_SECONDS - (time.monotonic() - self.last_started)))
            budget = self.budget()
            if budget["actual_HTTP_attempts"] >= self.authorized_total_ceiling:
                raise DocumentationStop("request_budget_exhausted")
            budget["actual_HTTP_attempts"] += 1
            partial = self.budget_path.with_suffix(".stage1.tmp")
            partial.write_text(json.dumps(budget), encoding="utf-8")
            partial.replace(self.budget_path)
            self.attempts += 1
            self.requested.add(url)
            self.last_started = time.monotonic()
            record.update(attempted=True, historical_attempt=budget["actual_HTTP_attempts"],
                          request_UTC=datetime.now(UTC).isoformat(), charged_before_send=True)
            self.append({**record, "event": "started"})
            async with asyncio.timeout(TIMEOUT_SECONDS):
                async with self.client.stream("GET", url, follow_redirects=False) as response:
                    record.update(status=response.status_code,
                                  content_type=response.headers.get("content-type"),
                                  content_length=response.headers.get("content-length"))
                    if not 200 <= response.status_code < 300:
                        raise DocumentationStop(f"HTTP_{response.status_code}")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise DocumentationStop("unsupported_content_encoding")
                    length = response.headers.get("content-length")
                    if length is not None and not length.isdecimal():
                        raise DocumentationStop("declared_body_invalid_length")
                    if length is not None and int(length) >= self.read_cap_bytes:
                        raise DocumentationStop("declared_body_at_read_cap")
                    async for chunk in response.aiter_raw(chunk_size=4096):
                        body.extend(chunk)
                        if len(body) >= self.read_cap_bytes:
                            raise DocumentationStop("body_reached_read_cap_unqualified")
                    record["body_complete"] = True
            return bytes(body)
        except (DocumentationStop, httpx.HTTPError, TimeoutError) as exc:
            record["stop_reason"] = str(exc) if isinstance(exc, DocumentationStop) else type(exc).__name__
            if self.unknown_resource(record["stop_reason"]):
                raise MetadataUnknown(record["stop_reason"]) from exc
            self.stopped = True
            raise DocumentationStop(record["stop_reason"]) from exc
        finally:
            self.active = False
            record.update(bytes=len(body), SHA256_observed_bytes=hashlib.sha256(body).hexdigest(),
                          elapsed_seconds=time.monotonic() - started,
                          finished_UTC=datetime.now(UTC).isoformat())
            if record["attempted"]:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                path = self.cache_dir / f"request_{record['historical_attempt']}.bin"
                with path.open("xb") as stream:
                    stream.write(body)
                record["cache_file"] = path.name
            self.append(record)
            self.last_record = record
