"""Prospective A1 pacing/retry policy; original adapters and parsing stay unchanged."""

from __future__ import annotations

import asyncio
import json
import random
import threading
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

import httpx

from asof.filing_timestamp_audit import AuditGuard, FullScopedFilingMetadata, guarded_fetch
from asof.sec_documentation import DocumentationStop, MetadataUnknown

MIN_GAP = 0.667
WAIT_SECONDS = 600
MAX_WAITS = 5
SEED = 2026111603


def remaining_order(inventory: list[dict], prior: list[dict], roster: list[dict]) -> list[dict]:
    if len({r["URL"] for r in prior}) != len(prior):
        raise ValueError("duplicate historical resource outcome")
    allowed = {r["URL"] for r in inventory}
    if not {r["URL"] for r in prior} <= allowed:
        raise ValueError("historical outcome outside original allowlist")
    failed = {r["URL"] for r in prior if r.get("request", {}).get("status") == 503}
    if len(failed) != 1:
        raise ValueError("exactly the previous503 resource must be reeligible")
    protected = {r["URL"] for r in prior} - failed
    pools = {r["accession"]: r["pool"] for r in roster}
    grouped = defaultdict(list)
    for ordinal, row in enumerate(inventory):
        if row["URL"] not in protected:
            grouped[row["accession"]].append({**row, "original_ordinal": ordinal,
                                               "previous503_reeligible": row["URL"] in failed})
    clock = sorted(a for a in grouped if pools[a] in
                   ("clock_disagreement_winter", "clock_disagreement_summer"))
    cik = sorted(a for a in grouped if pools[a] == "CIK_disagreement")
    rest = sorted(grouped.keys() - set(clock) - set(cik))
    random.Random(SEED).shuffle(rest)
    result = []
    for priority, accessions in (("clock108", clock), ("CIK256", cik), ("random_rest", rest)):
        for accession in accessions:
            for row in grouped[accession]:
                result.append({**row, "priority": priority, "pool": pools[accession],
                               "a1_order": len(result)})
    return result


class QpcLimiter:
    def __init__(
        self, clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.clock, self.sleep = clock, sleep
        self.last: float | None = None

    async def wait(self, check: Callable[[], None]) -> None:
        while self.last is not None:
            check()
            remaining = MIN_GAP - (self.clock() - self.last)
            if remaining <= 0:
                break
            await self.sleep(remaining)
        check()

    def mark(self) -> float:
        current = self.clock()
        if self.last is not None and current - self.last < MIN_GAP:
            raise DocumentationStop("QPC_minimum_dispatch_gap_violation")
        self.last = current
        return current


def append_event(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, allow_nan=False) + "\n")


class BorrowedMeasuredTransport(httpx.AsyncBaseTransport):
    """The session owns the connection pool; each scoped client borrows it once."""

    def __init__(self, inner: httpx.AsyncBaseTransport, limiter: QpcLimiter,
                 guard: AuditGuard, url: str, attempt: int) -> None:
        self.inner, self.limiter, self.guard = inner, limiter, guard
        self.url, self.attempt = url, attempt
        self.record: dict | None = None
        self.emit: Callable[[dict], None]

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET" or str(request.url) != self.url or self.record is not None:
            raise DocumentationStop("A1_exact_transport_scope_or_duplicate_violation")
        await self.limiter.wait(self.guard.check)
        utc = datetime.now(UTC).isoformat()
        sent = self.limiter.mark()
        self.record = {"event": "send", "url": self.url, "historical_attempt": self.attempt,
                       "send_perf_counter": sent, "send_UTC": utc,
                       "definition": "Application transport dispatch, not a wire timestamp."}
        try:
            return await self.inner.handle_async_request(request)
        finally:
            self.emit({**self.record,
                       "transport_headers_or_error_perf_counter": self.limiter.clock()})

    async def aclose(self) -> None:
        pass


class OneAttemptMetadata(FullScopedFilingMetadata):
    max_attempts = 1
    mirror: Callable[[dict], None]
    retry: bool

    def append(self, row: dict) -> None:
        value = {**row, "A1_retry": self.retry}
        super().append(value)
        self.mirror(value)


class AmendedSession:
    def __init__(
        self, allowed_urls: set[str], budget: Path, private: Path, guard: AuditGuard,
        *, transport: httpx.AsyncBaseTransport | None = None,
        limiter: QpcLimiter | None = None, on_event: Callable[[dict], None] | None = None,
    ) -> None:
        self.allowed_urls, self.budget, self.private, self.guard = allowed_urls, budget, private, guard
        self.limiter = limiter or QpcLimiter()
        self.inner = transport or httpx.AsyncHTTPTransport(
            retries=0, limits=httpx.Limits(max_connections=1, max_keepalive_connections=1))
        self.on_event = on_event
        self.aggregate = private / "requests.jsonl"
        self.events = private / "waits_and_retries.jsonl"
        if self.aggregate.exists() or self.events.exists():
            raise DocumentationStop("A1_session_already_attempted_no_automatic_resume")
        self.waits_used = 0
        self.charged = 0
        self.body_bytes = 0
        self.receipt_bytes = 0
        self.current_receipt: Path | None = None
        self.current_attempts: list[dict] = []
        self.primary_seen: set[str] = set()
        self.active = False
        self.stopped = False
        self.thread = threading.get_ident()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        await self.inner.aclose()

    @property
    def allocated_bytes(self) -> int:
        return self.body_bytes + self.receipt_bytes + (
            self.current_receipt.stat().st_size
            if self.current_receipt and self.current_receipt.exists() else 0)

    def event(self, row: dict) -> None:
        value = {**row, "UTC": datetime.now(UTC).isoformat(),
                 "perf_counter": self.limiter.clock()}
        append_event(self.events, value)
        if self.on_event:
            self.on_event(value)

    async def attempt(self, url: str, retry: bool) -> bytes:
        expected = 1422 + self.charged
        budget = json.loads(self.budget.read_bytes())
        if budget != {"actual_HTTP_attempts": expected - 1, "ceiling": 34402}:
            raise DocumentationStop("A1_shared_budget_changed")
        if expected > 34402:
            raise DocumentationStop("A1_project_budget_exhausted")
        receipt = self.private / "attempt_receipts" / f"attempt_{expected}.jsonl"
        measured = BorrowedMeasuredTransport(self.inner, self.limiter, self.guard, url, expected)
        client = OneAttemptMetadata((url,), self.budget, receipt,
                                    self.private / "raw_metadata", transport=measured)
        client.check = self.guard.check
        client.retry = retry
        client.mirror = lambda row: append_event(self.aggregate, row)
        measured.emit = client.append
        self.current_receipt = receipt
        try:
            async with client:
                return await guarded_fetch(client, url, self.guard)
        finally:
            record = client.last_record
            if record and record["attempted"]:
                self.charged += 1
                self.body_bytes += record["bytes"]
                self.current_attempts.append({
                    **record, "retry": retry,
                    "attempt_receipt": str(receipt.relative_to(self.private)),
                    "send": measured.record,
                })
            if receipt.exists():
                self.receipt_bytes += receipt.stat().st_size
            self.current_receipt = None

    async def cooldown(self, url: str, status: int) -> None:
        if self.waits_used >= MAX_WAITS:
            raise DocumentationStop("A1_sixth_wait_disallowed")
        self.waits_used += 1
        started = self.limiter.clock()
        self.event({"event": "wait_started", "url": url, "wait_number": self.waits_used,
                    "HTTP_status": status, "wait_seconds": WAIT_SECONDS,
                    "failed_attempt": self.current_attempts[-1]["historical_attempt"]})
        complete = False
        try:
            while True:
                self.guard.check()
                remaining = WAIT_SECONDS - (self.limiter.clock() - started)
                if remaining <= 0:
                    complete = True
                    break
                await self.limiter.sleep(min(1, remaining))
        finally:
            self.event({"event": "wait_finished", "url": url, "wait_number": self.waits_used,
                        "status": "completed" if complete else "interrupted",
                        "elapsed_perf_seconds": self.limiter.clock() - started})

    async def fetch(self, url: str) -> bytes:
        if (self.stopped or self.active or threading.get_ident() != self.thread
                or url not in self.allowed_urls or url in self.primary_seen):
            self.stopped = True
            raise DocumentationStop("A1_scope_duplicate_or_stopped_session")
        self.guard.check()
        self.primary_seen.add(url)
        self.current_attempts = []
        self.active = True
        try:
            try:
                return await self.attempt(url, retry=False)
            except MetadataUnknown:
                raise
            except DocumentationStop as exc:
                if str(exc) not in ("HTTP_503", "HTTP_429"):
                    raise
                await self.cooldown(url, int(str(exc).split("_")[1]))
                self.event({"event": "retry_started", "url": url,
                            "wait_number": self.waits_used,
                            "retry_attempt": 1422 + self.charged})
                return await self.attempt(url, retry=True)
        except MetadataUnknown:
            raise
        except (DocumentationStop, OSError, ValueError):
            self.stopped = True
            raise
        finally:
            self.active = False
