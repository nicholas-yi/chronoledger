"""A3: approved pilot-then-full continuation with adaptive pacing; ancestors stay immutable."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import threading
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from asof.filing_timestamp_a1 import (
    AmendedSession,
    BorrowedMeasuredTransport,
    QpcLimiter,
    append_event,
)
from asof.filing_timestamp_a2 import retry_kind
from asof.filing_timestamp_audit import FullScopedFilingMetadata, guarded_fetch
from asof.ledger import file_sha256
from asof.sec_documentation import DocumentationStop, MetadataUnknown

CEILING = 34402
START_GAP = 0.667
SLOW_GAP = 1.0
THROTTLE_WAIT = 600
TRANSPORT_WAIT = 60
MAX_THROTTLE_PAUSES = 6
PILOT_ATTEMPTS = 1000
PILOT_MAX_PAUSES = 1
MAX_CONSECUTIVE_UNRESOLVED = 3
READ_CAP = 4 << 20
CAP_UNKNOWNS = ("body_reached_read_cap_unqualified", "declared_body_at_read_cap",
                "cached_metadata_at_read_cap")
ATTEMPT_KEYS = ("request", "A1_attempts", "A2_attempts", "A3_attempts")


class AdaptiveLimiter(QpcLimiter):
    """QPC dispatch spacing whose minimum gap can only grow during a session."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 gap: float = START_GAP) -> None:
        super().__init__(clock, sleep)
        if gap < START_GAP:
            raise ValueError("A3 never paces faster than the A1/A2 gap")
        self.gap = gap

    def slow(self, gap: float) -> None:
        self.gap = max(self.gap, gap)

    async def wait(self, check: Callable[[], None]) -> None:
        while self.last is not None:
            check()
            remaining = self.gap - (self.clock() - self.last)
            if remaining <= 0:
                break
            await self.sleep(remaining)
        check()

    def mark(self) -> float:
        current = self.clock()
        if self.last is not None and current - self.last < self.gap:
            raise DocumentationStop("QPC_minimum_dispatch_gap_violation")
        self.last = current
        return current


def effective_outcomes(chain: list[list[dict]]) -> dict[str, dict]:
    """Merge ordered phase outcomes; only ``resource_failed`` resources may be replaced."""
    result: dict[str, dict] = {}
    for phase in chain:
        if len({r["URL"] for r in phase}) != len(phase):
            raise ValueError("duplicate terminal resource outcome within a phase")
        for row in phase:
            previous = result.get(row["URL"])
            if previous and not (reeligible(previous) or previous.get("request", {}).get("status") == 503):
                raise ValueError("attempt to replace a protected resource outcome")
            result[row["URL"]] = row
    return result


def reeligible(row: dict) -> bool:
    """Failed resources, or unknowns caused only by the earlier 64 KiB project read bound."""
    reason = str(row["parsed"].get("unknown", ""))
    return reason.startswith("resource_failed:") or reason in CAP_UNKNOWNS


def a3_order(inventory: list[dict], a1_order: list[dict], effective: dict[str, dict]) -> list[dict]:
    """Re-eligible prior outcomes first (inventory order), then A1's unrecorded frozen order."""
    first = [{**r, "A3_reeligible_prior_outcome": effective[r["URL"]]["parsed"]["unknown"]}
             for r in inventory if r["URL"] in effective and reeligible(effective[r["URL"]])]
    rest = [{**r, "A3_reeligible_prior_outcome": None} for r in a1_order if r["URL"] not in effective]
    return [{**r, "a3_order": i} for i, r in enumerate(first + rest)]


def raw_resource_bytes(row: dict, data_dir: Path, private: dict[str, Path]) -> bytes:
    """Recorded bytes for one resource outcome, hash-checked against its receipt."""
    if row.get("cache_hit"):
        path = data_dir / row["cache"]["path"]
        if file_sha256(path) != row["cache"]["file_SHA256"]:
            raise ValueError("pinned cache changed")
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rb") as stream:
            return stream.read(READ_CAP)
    for key in ATTEMPT_KEYS:
        if key not in row:
            continue
        attempts = row[key] if isinstance(row[key], list) else [row[key]]
        good = [a for a in attempts if a.get("status") == 200 and a.get("body_complete")]
        if not good:
            raise ValueError("no complete recorded body")
        directory = private[row.get("A3_segment", key)] if key == "A3_attempts" else private[key]
        raw = (directory / "raw_metadata" / good[-1]["cache_file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != good[-1]["SHA256_observed_bytes"]:
            raise ValueError("recorded body hash mismatch")
        return raw
    raise ValueError("resource outcome has no recorded body source")


class A3OneAttemptMetadata(FullScopedFilingMetadata):
    max_attempts = 1
    mirror: Callable[[dict], None]
    retry: bool

    def append(self, row: dict) -> None:
        value = {**row, "A3_retry": self.retry}
        super().append(value)
        self.mirror(value)


class A3Session(AmendedSession):
    """One segment: budget baseline read at start, shared throttle-pause cap across segments."""

    def __init__(self, allowed_urls: set[str], budget: Path, private: Path, guard, *,
                 start_used: int, max_pauses: int, attempt_limit: int | None = None,
                 transport=None, limiter: AdaptiveLimiter | None = None,
                 on_event: Callable[[dict], None] | None = None) -> None:
        super().__init__(allowed_urls, budget, private, guard, transport=transport,
                         limiter=limiter or AdaptiveLimiter(), on_event=on_event)
        if not isinstance(self.limiter, AdaptiveLimiter):
            raise TypeError("A3 requires the adaptive limiter")
        if max_pauses < 0 or max_pauses > MAX_THROTTLE_PAUSES:
            raise ValueError("throttle-pause allowance outside the approved cap")
        self.start_used, self.max_pauses, self.attempt_limit = start_used, max_pauses, attempt_limit
        self.throttle_pauses = 0
        self.waiting_seconds = 0.0

    async def attempt(self, url: str, retry: bool) -> bytes:
        expected = self.start_used + 1 + self.charged
        if self.attempt_limit is not None and self.charged >= self.attempt_limit:
            raise DocumentationStop("A3_segment_attempt_limit_reached")
        if json.loads(self.budget.read_bytes()) != {"actual_HTTP_attempts": expected - 1,
                                                    "ceiling": CEILING}:
            raise DocumentationStop("A3_shared_budget_changed")
        if expected > CEILING:
            raise DocumentationStop("A3_project_budget_exhausted")
        receipt = self.private / "attempt_receipts" / f"attempt_{expected}.jsonl"
        measured = BorrowedMeasuredTransport(self.inner, self.limiter, self.guard, url, expected)
        client = A3OneAttemptMetadata((url,), self.budget, receipt,
                                      self.private / "raw_metadata", transport=measured,
                                      read_cap_bytes=READ_CAP)
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
                    **record, "retry": retry, "gap_seconds": self.limiter.gap,
                    "attempt_receipt": str(receipt.relative_to(self.private)),
                    "send": measured.record})
            if receipt.exists():
                self.receipt_bytes += receipt.stat().st_size
            self.current_receipt = None

    async def pause(self, url: str, trigger: str, seconds: float) -> None:
        started = self.limiter.clock()
        self.event({"event": "wait_started", "url": url, "trigger": trigger,
                    "wait_seconds": seconds, "throttle_pauses": self.throttle_pauses,
                    "failed_attempt": self.current_attempts[-1]["historical_attempt"]
                    if self.current_attempts else None})
        complete = False
        try:
            while True:
                self.guard.check()
                remaining = seconds - (self.limiter.clock() - started)
                if remaining <= 0:
                    complete = True
                    break
                await self.limiter.sleep(min(1, remaining))
        finally:
            elapsed = self.limiter.clock() - started
            self.waiting_seconds += elapsed
            self.event({"event": "wait_finished", "url": url, "trigger": trigger,
                        "status": "completed" if complete else "interrupted",
                        "elapsed_perf_seconds": elapsed, "gap_after_seconds": self.limiter.gap})

    async def fetch(self, url: str) -> bytes:
        if (self.stopped or self.active or threading.get_ident() != self.thread
                or url not in self.allowed_urls or url in self.primary_seen):
            self.stopped = True
            raise DocumentationStop("A3_scope_duplicate_or_stopped_session")
        self.guard.check()
        self.primary_seen.add(url)
        self.current_attempts = []
        self.active = True
        transport_retry_used = False
        retry = False
        try:
            while True:
                try:
                    return await self.attempt(url, retry=retry)
                except MetadataUnknown:
                    raise
                except DocumentationStop as exc:
                    kind = retry_kind(exc)
                    if kind is None:
                        raise
                    if kind.startswith("HTTP_"):
                        if self.throttle_pauses >= self.max_pauses:
                            self.event({"event": "wait_not_started", "url": url, "trigger": kind,
                                        "reason": "A3_throttle_pause_cap",
                                        "throttle_pauses": self.throttle_pauses})
                            raise DocumentationStop("A3_throttle_pause_cap") from exc
                        self.throttle_pauses += 1
                        self.waits_used += 1
                        await self.pause(url, kind, THROTTLE_WAIT)
                        self.limiter.slow(SLOW_GAP)
                    else:
                        if transport_retry_used:
                            raise MetadataUnknown(f"transport_unresolved:{kind}") from exc
                        transport_retry_used = True
                        self.waits_used += 1
                        await self.pause(url, kind, TRANSPORT_WAIT)
                    retry = True
                    self.event({"event": "retry_started", "url": url, "trigger": kind,
                                "retry_attempt": self.start_used + 1 + self.charged})
        except MetadataUnknown:
            raise
        except (DocumentationStop, OSError, ValueError):
            self.stopped = True
            raise
        finally:
            self.active = False
