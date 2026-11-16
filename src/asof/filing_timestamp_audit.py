"""One-shot metadata audit safety and conditional comparisons, never timestamp repair."""

from __future__ import annotations

import asyncio
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta
from itertools import pairwise

from asof.filing_header_pilot import ScopedFilingMetadata, comparison
from asof.sec_documentation import DocumentationStop

PROJECT_CEILING = 34402
METADATA_ATTEMPTS = 34252
DISK_BYTES = 4 << 30


class AuditGuard:
    def __init__(
        self, clocks: Callable[[], tuple[float, float]], storage: Callable[[], int],
        *, wall_seconds: float = 43200, monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.clocks, self.storage, self.monotonic = clocks, storage, monotonic
        self.previous = clocks()
        self.started = monotonic()
        self.deadline = self.started + wall_seconds
        self.interruptions: list[dict] = []

    def check(self) -> None:
        current = self.clocks()
        asleep = (current[0] - self.previous[0]) - (current[1] - self.previous[1])
        self.previous = current
        if asleep > 2:
            self.interruptions.append({"suspend_seconds_detected": asleep,
                                       "uptime_seconds": current[0],
                                       "awake_uptime_seconds": current[1]})
            raise DocumentationStop("host_sleep_or_suspend_no_automatic_resume")
        if self.monotonic() >= self.deadline:
            raise DocumentationStop("metadata_12h_wall_cap")
        if self.storage() + (256 << 20) >= DISK_BYTES:
            raise DocumentationStop("4GiB_disk_budget_report_reserve")


class FullScopedFilingMetadata(ScopedFilingMetadata):
    max_attempts = METADATA_ATTEMPTS
    historical_ceiling = PROJECT_CEILING
    authorized_total_ceiling = PROJECT_CEILING
    check: Callable[[], None]

    def budget(self) -> dict:
        self.check()
        return super().budget()


async def guarded_fetch(client: FullScopedFilingMetadata, url: str, guard: AuditGuard) -> bytes:
    guard.check()
    task = asyncio.create_task(client.fetch(url))
    try:
        while True:
            done, _ = await asyncio.wait((task,), timeout=1)
            guard.check()
            if done:
                return task.result()
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        elif not task.cancelled():
            task.exception()


def accession_result(record: dict, resources: list[dict]) -> dict:
    headers = [r for r in resources if r["kind"] == "header"]
    indexes = [r for r in resources if r["kind"] == "index"]
    good = [r["parsed"] for r in headers if "unknown" not in r["parsed"]]
    candidates = {h["UTC_assuming_Eastern"] for h in good}
    complete = len(good) == len(headers) and bool(headers)
    if complete and len(candidates) == 1:
        header = good[0]
    else:
        header = {"unknown": "missing_or_conflicting_archive_path_headers"}
    walls = {r["parsed"]["index_wall"] for r in indexes
             if "index_wall" in r["parsed"]}
    index = ({"index_wall": next(iter(walls))}
             if len(walls) == 1 and len(indexes) == sum(
                 "index_wall" in r["parsed"] for r in indexes)
             else {"unknown": "missing_or_conflicting_archive_path_indexes"})
    result = comparison(record, header, index)
    conditional = header.get("UTC_assuming_Eastern")
    if conditional and result["index_header_wall_agree"] is None:
        result["class"] = "index_unread_or_conflicting:" + result["class"]
    if result["index_header_wall_agree"] is not True:
        conditional = None
    outside = bool(conditional and conditional not in record["candidate_times"])
    return {
        "accession": record["accession"], "pool": record["pool"],
        "cik_pair": record["cik_pair"], "cik_bulk": record["cik_bulk"],
        "API_time_stored_pair": record["pair_time"], "bulk_time": record["bulk_time"],
        "header_wall": header.get("header_wall"), "index_wall": index.get("index_wall"),
        "agreement_class": result["class"],
        "pair_offset_hours": result["pair_offset_hours"],
        "bulk_offset_hours": result["bulk_offset_hours"],
        "conditional_UTC_assuming_Eastern": conditional,
        "outside_frozen_candidate_envelope": outside,
        "qualified_UTC": None,
        "unresolved_reasons": [
            "historically_applicable_field_clock_definition_not_established",
            "header_roles_not_issuer_security_identity_certification",
            "registered_nominal_calendar_not_venue_early_close_certified",
            *([] if conditional else ["missing_unread_or_conflicting_metadata"]),
            *(["conditional_candidate_outside_frozen_screen"] if outside else []),
        ],
        "CIK_role_notes": [
            {"path_CIK": r["path_CIK"],
             "observed_roles": r["parsed"].get("header_CIKs_by_role", {}),
             "unknown": r["parsed"].get("unknown")} for r in headers
        ],
        "resource_outcomes": resources,
    }


def assignment_counts(
    universe: list[dict], audited: list[dict], closes: list[datetime],
    formations: list[datetime], start: datetime, end: datetime,
) -> dict:
    if not closes or any(a >= b for a, b in pairwise(closes)):
        raise ValueError("ordered registered close calendar required")
    known = {r["accession"]: datetime.fromisoformat(r["conditional_UTC_assuming_Eastern"])
             for r in audited if r["conditional_UTC_assuming_Eastern"]
             and not r["outside_frozen_candidate_envelope"]}
    required = {r["accession"] for r in audited}
    by_cik = defaultdict(list)
    for row in universe:
        by_cik[row["cik_pair"]].append(row)
    output = {}
    for source in ("pair", "bulk"):
        counts = Counter(dict.fromkeys((
            "conditional_accessions", "UTC_month_changed", "first_close_unassigned",
            "first_close_comparable", "first_registered_close_changed",
            "eligibility_record_month_instances_changed", "eligibility_accessions_changed",
            "latest_filing_firm_months_in_scope", "latest_filing_firm_months_unresolved",
            "latest_filing_firm_months_comparable", "latest_filing_firm_months_changed",
        ), 0))
        changed_eligibility = set()
        for row in universe:
            accession = row["accession"]
            if accession not in known:
                continue
            before, after = datetime.fromisoformat(row[f"{source}_time"]), known[accession]
            counts["conditional_accessions"] += 1
            counts["UTC_month_changed"] += (before.year, before.month) != (after.year, after.month)
            a, b = bisect_right(closes, before), bisect_right(closes, after)
            if a == len(closes) or b == len(closes):
                counts["first_close_unassigned"] += 1
            else:
                counts["first_close_comparable"] += 1
                counts["first_registered_close_changed"] += a != b
            for close in formations:
                lower, upper = max(close - timedelta(days=365), start), min(close, end)
                if (lower <= before < upper) != (lower <= after < upper):
                    counts["eligibility_record_month_instances_changed"] += 1
                    changed_eligibility.add(accession)
        counts["eligibility_accessions_changed"] = len(changed_eligibility)
        for peers in by_cik.values():
            for close in formations:
                lower, upper = max(close - timedelta(days=365), start), min(close, end)
                needed = {r["accession"] for r in peers if any(
                    lower <= datetime.fromisoformat(t) < upper for t in r["candidate_times"])}
                if not needed & required:
                    continue
                counts["latest_filing_firm_months_in_scope"] += 1
                if (needed & required) - known.keys():
                    counts["latest_filing_firm_months_unresolved"] += 1
                    continue
                selections = []
                for replacement in (False, True):
                    eligible = []
                    for order, row in enumerate(peers):
                        original = datetime.fromisoformat(row[f"{source}_time"])
                        stamp = known.get(row["accession"], original) if replacement else original
                        if lower <= stamp < upper:
                            eligible.append((stamp, order, row["accession"]))
                    selections.append(max(eligible)[2] if eligible else None)
                counts["latest_filing_firm_months_comparable"] += 1
                counts["latest_filing_firm_months_changed"] += selections[0] != selections[1]
        output[f"stored_{source}_versus_conditional"] = dict(counts)
    return {
        "qualified_assignment_changes": None,
        "qualified_accession_denominator": 0,
        "reason": "No historically qualified field clock; actual verified changes cannot be established.",
        "conditional_diagnostics_only": output,
        "limits": "Eastern-clock assumption and cached nominal16:00ET calendar only. Unaudited "
                  "competitors are held unchanged in each baseline; incomplete audited competitor "
                  "contexts are unresolved. Stable source order breaks equal-time ties. No "
                  "security remaps, signal values, prices, returns or portfolio results.",
    }
