"""A2 fixed-window statistics and bounded retry policy; ancestors remain immutable."""

from __future__ import annotations

import errno
import json
import re
import threading
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime

from scipy.stats import beta

from asof.filing_timestamp_a1 import (
    AmendedSession,
    BorrowedMeasuredTransport,
    append_event,
)
from asof.filing_timestamp_audit import AuditGuard, FullScopedFilingMetadata, guarded_fetch
from asof.sec_documentation import DocumentationStop, MetadataUnknown

START_USED = 3137
WAIT_BUDGET = 7200
MAX_STATUS_WAITS = 20


def bounded_window(order: list[dict], prior: list[dict], size: int = 3000) -> list[dict]:
    if [r["URL"] for r in prior] != [r["URL"] for r in order[:len(prior)]]:
        raise ValueError("A1 outcomes must be the exact frozen prefix")
    previous = {r["accession"] for r in prior if r["priority"] == "random_rest"}
    remaining = [r for r in order[len(prior):]
                 if r["priority"] == "random_rest" and r["accession"] not in previous]
    accessions = list(dict.fromkeys(r["accession"] for r in remaining))[:size]
    if len(accessions) != size:
        raise ValueError("insufficient remaining random-rest accessions")
    selected = set(accessions)
    return [{**r, "a2_order": i} for i, r in enumerate(
        r for r in remaining if r["accession"] in selected)]


def cp_upper(k: int, n: int) -> float | None:
    if type(k) is not int or type(n) is not int or n < 0 or not 0 <= k <= n:
        raise ValueError("integer0<=k<=n required")
    if n == 0:
        return None
    return 1.0 if k == n else float(beta.ppf(0.95, k + 1, n - k))


def error_bounds(
    roster: list[dict], rows: list[dict], selected: list[str], visited: set[str],
) -> dict:
    if len(set(selected)) != len(selected) or not visited <= set(selected):
        raise ValueError("unique fixed sample and visited subset required")
    metadata = {r["accession"]: r for r in roster}
    observed = {r["accession"]: r for r in rows}
    buckets = defaultdict(lambda: {"selected_n": 0, "visited_n": 0, "complete_n": 0, "k": 0})
    excluded = defaultdict(int)
    for accession in selected:
        source, row = metadata[accession], observed[accession]
        pair, bulk = (datetime.fromisoformat(source[k]) for k in ("pair_time", "bulk_time"))
        pool = source["pool"]
        if pool not in ("clock_agreement_sensitive", "candidate_calendar_boundary_or_clock_issue"):
            raise ValueError("sample includes a non-random-rest pool")
        if pair != bulk:
            excluded[pool] += 1
            continue
        value = row["conditional_UTC_assuming_Eastern"]
        complete = accession in visited and bool(value) and not row["outside_frozen_candidate_envelope"]
        error = bool(complete and datetime.fromisoformat(value) != pair
                     and datetime.fromisoformat(value) != bulk)
        for key in (pool, "overall"):
            b = buckets[key]
            b["selected_n"] += 1
            b["visited_n"] += accession in visited
            b["complete_n"] += bool(complete)
            b["k"] += error
    result = {}
    for pool in ("clock_agreement_sensitive", "candidate_calendar_boundary_or_clock_issue", "overall"):
        b = buckets[pool]
        unknown = b["selected_n"] - b["complete_n"]
        result[pool] = {
            **b, "visited_unread_n": b["visited_n"] - b["complete_n"],
            "not_visited_n": b["selected_n"] - b["visited_n"],
            "complete_case_one_sided95_CP_upper": cp_upper(b["k"], b["complete_n"]),
            "all_selected_unknown_n": unknown,
            "all_selected_unread_as_errors_k": b["k"] + unknown,
            "all_selected_unread_as_errors_one_sided95_CP_upper": cp_upper(
                b["k"] + unknown, b["selected_n"]),
        }
    return {
        "predeclared": True, "confidence": 0.95, "method": "exact one-sided Clopper-Pearson",
        "population": "All internally agreeing random-rest strata in the fixed A1+A2 sample; "
                      "exclude108clock/256CIK priority strata and original sorted-prefix cases.",
        "selected_accessions_all_strata": len(selected), "visited_accessions_all_strata": len(visited),
        "excluded_internally_disagreeing_by_pool": dict(excluded), "by_pool_and_overall": result,
        "limits": "Conditional on the Eastern assumption, original parsing and the remaining "
                  "random-rest order, not all EDGAR or the excluded cohort. Complete-case "
                  "bounds condition on readability and need not bound selectively unread "
                  "cases. The separate conservative scenario counts EVERY unread selected "
                  "case, including not-yet-visited cases, as an error. Ordinary CP is not an "
                  "always-valid sequential confidence bound under error-dependent stopping. "
                  "Neither bound certifies historical UTC or financial effects.",
    }


def retry_kind(exc: DocumentationStop) -> str | None:
    reason = str(exc)
    if reason in ("HTTP_503", "HTTP_429"):
        return reason
    if reason in ("TimeoutError", "ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout"):
        return "transport_timeout"
    if reason not in ("ReadError", "WriteError", "ConnectError", "CloseError"):
        return None
    pending: list[BaseException] = [exc]
    seen = set()
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        if (isinstance(error, ConnectionResetError)
                or isinstance(error, OSError) and (
                    error.errno == errno.ECONNRESET or getattr(error, "winerror", None) == 10054)
                or re.search(r"\[WinError 10054\]", str(error))):
            return "connection_reset"
        pending.extend(e for e in (error.__cause__, error.__context__) if e is not None)
    return None


class A2Guard(AuditGuard):
    def check(self) -> None:
        try:
            super().check()
        except DocumentationStop as exc:
            if str(exc) == "metadata_12h_wall_cap":
                raise DocumentationStop("A2_4h_wall_cap") from exc
            raise


class A2OneAttemptMetadata(FullScopedFilingMetadata):
    max_attempts = 1
    mirror: Callable[[dict], None]
    retry: bool

    def append(self, row: dict) -> None:
        value = {**row, "A2_retry": self.retry}
        super().append(value)
        self.mirror(value)


class BoundedSession(AmendedSession):
    status_waits_used = 0
    waiting_seconds = 0.0

    async def attempt(self, url: str, retry: bool) -> bytes:
        # A1 hard-codes its historical baseline; preserve that source and override charging only.
        expected = START_USED + 1 + self.charged
        budget = json.loads(self.budget.read_bytes())
        if budget != {"actual_HTTP_attempts": expected - 1, "ceiling": 34402}:
            raise DocumentationStop("A2_shared_budget_changed")
        if expected > 34402:
            raise DocumentationStop("A2_project_budget_exhausted")
        receipt = self.private / "attempt_receipts" / f"attempt_{expected}.jsonl"
        measured = BorrowedMeasuredTransport(self.inner, self.limiter, self.guard, url, expected)
        client = A2OneAttemptMetadata((url,), self.budget, receipt,
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
                    "attempt_receipt": str(receipt.relative_to(self.private)), "send": measured.record})
            if receipt.exists():
                self.receipt_bytes += receipt.stat().st_size
            self.current_receipt = None

    async def backoff(self, url: str, kind: str) -> None:
        seconds = 600 if kind.startswith("HTTP_") else 60
        if (kind.startswith("HTTP_") and self.status_waits_used >= MAX_STATUS_WAITS
                or self.waiting_seconds + seconds > WAIT_BUDGET):
            self.event({"event": "wait_not_started", "url": url, "trigger": kind,
                        "reason": "A2_wait_count_or_cumulative_budget",
                        "cumulative_wait_seconds": self.waiting_seconds})
            raise DocumentationStop("A2_wait_count_or_cumulative_budget")
        self.waits_used += 1
        self.status_waits_used += kind.startswith("HTTP_")
        started = self.limiter.clock()
        self.event({"event": "wait_started", "url": url, "wait_number": self.waits_used,
                    "trigger": kind, "wait_seconds": seconds,
                    "failed_attempt": self.current_attempts[-1]["historical_attempt"]})
        complete = False
        try:
            while True:
                self.guard.check()
                elapsed = self.limiter.clock() - started
                if self.waiting_seconds + elapsed > WAIT_BUDGET:
                    raise DocumentationStop("A2_cumulative_wait_budget")
                remaining = seconds - elapsed
                if remaining <= 0:
                    complete = True
                    break
                await self.limiter.sleep(min(1, remaining))
        finally:
            elapsed = self.limiter.clock() - started
            self.waiting_seconds += elapsed
            self.event({"event": "wait_finished", "url": url, "wait_number": self.waits_used,
                        "trigger": kind, "status": "completed" if complete else "interrupted",
                        "elapsed_perf_seconds": elapsed,
                        "cumulative_wait_seconds": self.waiting_seconds})

    async def fetch(self, url: str) -> bytes:
        if (self.stopped or self.active or threading.get_ident() != self.thread
                or url not in self.allowed_urls or url in self.primary_seen):
            self.stopped = True
            raise DocumentationStop("A2_scope_duplicate_or_stopped_session")
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
                kind = retry_kind(exc)
                if kind is None:
                    raise
                await self.backoff(url, kind)
                self.event({"event": "retry_started", "url": url, "trigger": kind,
                            "wait_number": self.waits_used,
                            "retry_attempt": START_USED + 1 + self.charged})
                return await self.attempt(url, retry=True)
        except MetadataUnknown:
            raise
        except (DocumentationStop, OSError, ValueError):
            self.stopped = True
            raise
        finally:
            self.active = False
