"""A5: 2012-2018 H4/H6a filings whose acceptance time could change a registered assignment.

Approved 2026-11-21 (``h6_timestamp_audit=audit_264``, ceiling 35,800), after A4. A filing is
audited when shifting its stored time by up to five hours could move it across the H6a
development-window or calendar-year edge, flip a 365-day restatement-window indicator, or
reorder two same-company 10-Ks. Ancestor modules stay unchanged.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

from asof.filing_timestamp_a1 import BorrowedMeasuredTransport, append_event
from asof.filing_timestamp_a3 import READ_CAP
from asof.filing_timestamp_a4 import A4Session
from asof.filing_timestamp_audit import FullScopedFilingMetadata, guarded_fetch
from asof.sec_documentation import DocumentationStop

PREVIOUS_CEILING = 35000
CEILING = 35800
SHIFT = timedelta(hours=5)
DEV = (pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2018-12-31 23:59:59", tz="UTC"))
FORMAL = r"\b4\.02\b"


def sensitive_accessions(filings: pd.DataFrame, sample: set[int]) -> dict[str, list[str]]:
    """Accessions (with reasons) whose H4/H6a role could change under a <=5h time error."""
    f = filings[filings["cik"].isin(sample)]
    base = f[f["form"].isin(["10-K", "10-Q"]) & f["knowledge_time"].between(DEV[0] - SHIFT, DEV[1] + SHIFT)]
    formal = f[(f["form"] == "10-K/A") | f["items"].fillna("").str.contains(FORMAL)]
    reasons: dict[str, set[str]] = {}

    def flag(accession: str, why: str) -> None:
        reasons.setdefault(accession, set()).add(why)

    for accession, known in zip(base["accession"], base["knowledge_time"], strict=True):
        if abs(known - DEV[0]) <= SHIFT or abs(known - DEV[1]) <= SHIFT:
            flag(accession, "dev_window_edge")
        for year in (known.year, known.year + 1):
            if abs(known - pd.Timestamp(year=year, month=1, day=1, tz="UTC")) <= SHIFT:
                flag(accession, "year_edge")
    events = {c: g for c, g in formal.groupby("cik")}
    for row in base.itertuples():
        group = events.get(row.cik)
        if group is None:
            continue
        for accession, known in zip(group["accession"], group["knowledge_time"], strict=True):
            if (abs(known - row.knowledge_time) <= 2 * SHIFT
                    or abs(known - (row.knowledge_time + timedelta(days=365))) <= 2 * SHIFT):
                flag(row.accession, "restatement_window_edge")
                flag(accession, "restatement_window_edge_event")
    annual = f[f["form"] == "10-K"].sort_values(["cik", "knowledge_time"], kind="stable")
    close = annual.groupby("cik")["knowledge_time"].diff() <= 2 * SHIFT
    for position in annual.index[close.to_numpy()]:
        i = annual.index.get_loc(position)
        for accession in annual["accession"].iloc[[i - 1, i]]:
            flag(accession, "same_company_10K_order")
    return {a: sorted(r) for a, r in sorted(reasons.items())}


class A5OneAttemptMetadata(FullScopedFilingMetadata):
    max_attempts = 1
    historical_ceiling = CEILING
    authorized_total_ceiling = CEILING

    def append(self, row: dict) -> None:
        value = {**row, "A5_retry": self.retry}
        super().append(value)
        self.mirror(value)


class A5Session(A4Session):
    """A4's approved retry policy with the A5 ceiling."""

    async def attempt(self, url: str, retry: bool) -> bytes:
        expected = self.start_used + 1 + self.charged
        if json.loads(self.budget.read_bytes()) != {"actual_HTTP_attempts": expected - 1, "ceiling": CEILING}:
            raise DocumentationStop("A5_shared_budget_changed")
        if expected > CEILING:
            raise DocumentationStop("A5_project_budget_exhausted")
        receipt: Path = self.private / "attempt_receipts" / f"attempt_{expected}.jsonl"
        measured = BorrowedMeasuredTransport(self.inner, self.limiter, self.guard, url, expected)
        client = A5OneAttemptMetadata((url,), self.budget, receipt, self.private / "raw_metadata",
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
                self.window.append(record.get("stop_reason") in ("HTTP_502", "HTTP_504"))
                self.current_attempts.append({
                    **record, "retry": retry, "gap_seconds": self.limiter.gap,
                    "attempt_receipt": str(receipt.relative_to(self.private)), "send": measured.record})
            if receipt.exists():
                self.receipt_bytes += receipt.stat().st_size
            self.current_receipt = None
