"""A4: approved continuation with short gateway retries, a raised ceiling and F7 identity fetches.

Approved 2026-11-20 after the A3 pause-cap stop (``gateway_policy=short_retry``,
``ceiling=35000``, ``f7_identity=true``). Ancestor modules and records stay unchanged.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path

from asof.filing_timestamp_a1 import BorrowedMeasuredTransport, append_event
from asof.filing_timestamp_a2 import retry_kind
from asof.filing_timestamp_a3 import (
    GATEWAY,
    READ_CAP,
    SLOW_GAP,
    START_GAP,
    THROTTLE_WAIT,
    TRANSPORT_WAIT,
    A3Session,
)
from asof.filing_timestamp_audit import FullScopedFilingMetadata, guarded_fetch
from asof.sec_documentation import DocumentationStop, MetadataUnknown

PREVIOUS_CEILING = 34402
CEILING = 35000
GATEWAY_WAIT = 60
MAX_COUNTED_PAUSES = 12
RATE_WINDOW = 500
RATE_LIMIT = 15
CONTINUABLE = ("A4_wall_cap", "host_sleep_or_suspend_no_automatic_resume",
               "transport_unresolved_streak")


class A4OneAttemptMetadata(FullScopedFilingMetadata):
    max_attempts = 1
    historical_ceiling = CEILING
    authorized_total_ceiling = CEILING
    mirror: Callable[[dict], None]
    retry: bool

    def append(self, row: dict) -> None:
        value = {**row, "A4_retry": self.retry}
        super().append(value)
        self.mirror(value)


class A4Session(A3Session):
    """Gateway errors get one short uncounted retry; repeats and 503/429 use counted pauses.

    A rolling window of the last 500 charged attempts stops the session once it holds more
    than 15 gateway errors (3%).
    """

    def __init__(self, allowed_urls: set[str], budget: Path, private: Path, guard, *,
                 start_used: int, max_pauses: int, **kwargs) -> None:
        # A3Session validates against its own 6-pause cap; A4 applies its approved cap here.
        super().__init__(allowed_urls, budget, private, guard, start_used=start_used,
                         max_pauses=0, **kwargs)
        if not 0 <= max_pauses <= MAX_COUNTED_PAUSES:
            raise ValueError("counted-pause allowance outside the approved A4 cap")
        self.max_pauses = max_pauses
        self.window: deque[bool] = deque(maxlen=RATE_WINDOW)
        self.short_gateway_retries = 0

    async def attempt(self, url: str, retry: bool) -> bytes:
        expected = self.start_used + 1 + self.charged
        if json.loads(self.budget.read_bytes()) != {"actual_HTTP_attempts": expected - 1,
                                                    "ceiling": CEILING}:
            raise DocumentationStop("A4_shared_budget_changed")
        if expected > CEILING:
            raise DocumentationStop("A4_project_budget_exhausted")
        receipt = self.private / "attempt_receipts" / f"attempt_{expected}.jsonl"
        measured = BorrowedMeasuredTransport(self.inner, self.limiter, self.guard, url, expected)
        client = A4OneAttemptMetadata((url,), self.budget, receipt, self.private / "raw_metadata",
                                      transport=measured, read_cap_bytes=READ_CAP)
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
                self.window.append(record.get("stop_reason") in GATEWAY)
                self.current_attempts.append({
                    **record, "retry": retry, "gap_seconds": self.limiter.gap,
                    "attempt_receipt": str(receipt.relative_to(self.private)),
                    "send": measured.record})
            if receipt.exists():
                self.receipt_bytes += receipt.stat().st_size
            self.current_receipt = None

    def refuse(self, url: str, kind: str, reason: str, exc: Exception) -> None:
        self.event({"event": "wait_not_started", "url": url, "trigger": kind, "reason": reason,
                    "throttle_pauses": self.throttle_pauses,
                    "gateway_errors_in_window": sum(self.window)})
        raise DocumentationStop(reason) from exc

    async def fetch(self, url: str) -> bytes:
        if (self.stopped or self.active or threading.get_ident() != self.thread
                or url not in self.allowed_urls or url in self.primary_seen):
            self.stopped = True
            raise DocumentationStop("A4_scope_duplicate_or_stopped_session")
        self.guard.check()
        self.primary_seen.add(url)
        self.current_attempts = []
        self.active = True
        gateway_retry_used = transport_retry_used = retry = False
        try:
            while True:
                try:
                    return await self.attempt(url, retry=retry)
                except MetadataUnknown:
                    raise
                except DocumentationStop as exc:
                    kind = retry_kind(exc) or (str(exc) if str(exc) in GATEWAY else None)
                    if kind is None:
                        raise
                    if kind in GATEWAY and sum(self.window) > RATE_LIMIT:
                        self.refuse(url, kind, "A4_gateway_error_rate", exc)
                    if kind in GATEWAY and not gateway_retry_used:
                        gateway_retry_used = True
                        self.waits_used += 1
                        self.short_gateway_retries += 1
                        await self.pause(url, kind, GATEWAY_WAIT)
                    elif kind.startswith("HTTP_"):
                        if self.throttle_pauses >= self.max_pauses:
                            self.refuse(url, kind, "A4_counted_pause_cap", exc)
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


def segment_allowance(prior: list[dict]) -> dict:
    """Counted pauses already used and the start gap for the next A4 segment."""
    if prior and prior[-1].get("stop_reason") not in CONTINUABLE:
        raise RuntimeError("A4 continues only after a wall, sleep or transport-streak stop")
    used = sum(s["throttle_pauses"] for s in prior)
    if used >= MAX_COUNTED_PAUSES:
        raise RuntimeError("A4 counted-pause cap already used")
    return {"pauses_before": used, "max_pauses": MAX_COUNTED_PAUSES - used,
            "start_gap": START_GAP if used == 0 else SLOW_GAP}


def a4_raw_bytes(row: dict, segment_dirs: dict[str, Path],
                 fallback: Callable[[dict], bytes]) -> bytes:
    """Recorded body of an A4 outcome, hash-checked; cache hits and earlier phases use ``fallback``."""
    if "A4_attempts" not in row or row.get("cache_hit"):
        return fallback(row)
    good = [a for a in row["A4_attempts"] if a.get("status") == 200 and a.get("body_complete")]
    if not good:
        raise ValueError("no complete recorded body")
    raw = (segment_dirs[row["A4_segment"]] / "raw_metadata" / good[-1]["cache_file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != good[-1]["SHA256_observed_bytes"]:
        raise ValueError("recorded body hash mismatch")
    return raw


def identity_decision(pair: int, bulk: int, header_ciks: set[int] | None, listed: set[int]) -> str:
    """Declared F7 rule: which stored CIK names the traded security of a co-filed accession."""
    if header_ciks is None:
        return "header_unread"
    if not {pair, bulk} <= header_ciks:
        return "header_lacks_a_stored_CIK"
    traded = [c for c in (pair, bulk) if c in listed]
    if traded == [pair]:
        return "qualified_pair_CIK_is_the_listed_security"
    if traded == [bulk]:
        return "bulk_CIK_is_the_listed_security"
    return "both_listed_ambiguous" if traded else "neither_listed"
