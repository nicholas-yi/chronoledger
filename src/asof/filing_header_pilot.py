"""Metadata-only, conditional Eastern-clock pilot. Never certifies or repairs an input."""

from __future__ import annotations

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from asof.sec_documentation import StrictSecDocumentation
from asof.timeutil import parse_header_acceptance_et

POOLS = (
    "CIK_disagreement", "candidate_calendar_boundary_or_clock_issue",
    "clock_disagreement_winter", "clock_disagreement_summer",
    "clock_agreement_sensitive", "clock_agreement_insensitive",
)
EXPECTED_POOL_COUNTS = (404, 676, 37, 71, 16335, 3979)
ACCESSION = r"\d{10}-\d{2}-\d{6}"
PATH = re.compile(rf"/Archives/edgar/data/[1-9]\d*/(\d{{18}})/({ACCESSION})-index(-headers)?\.html")


class ScopedFilingMetadata(StrictSecDocumentation):
    max_attempts = 96
    authorized_total_ceiling = 144

    def path_allowed(self, path: str) -> bool:
        match = PATH.fullmatch(path)
        return bool(match and match[1] == match[2].replace("-", ""))

    def unknown_resource(self, reason: str) -> bool:
        return reason in {
            "HTTP_404", "declared_body_at_read_cap",
            "body_reached_read_cap_unqualified",
        }


def pool_for(row: dict) -> str:
    if not row["CIKs_agree"]:
        return POOLS[0]
    candidates = [datetime.fromisoformat(t) for t in row["candidate_times"]]
    if len({(t.year, t.month) for t in candidates}) > 1 or len(row["clock_issues"]) > 0:
        return POOLS[1]
    if not row["source_times_agree"]:
        offset = datetime.fromisoformat(row["pair_time"]).astimezone(
            ZoneInfo("America/New_York")).utcoffset().total_seconds() / 3600
        if offset not in (-4, -5):
            raise ValueError("unrecognized historical season label")
        return POOLS[2] if offset == -5 else POOLS[3]
    return POOLS[4] if row["assignment_sensitive"] else POOLS[5]


def resource_urls(cik: int, accession: str) -> dict[str, str]:
    if type(cik) is not int or cik <= 0 or re.fullmatch(ACCESSION, accession) is None:
        raise ValueError("strict CIK/accession address required; do not repair malformed identity")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{accession}"
    return {"header": base + "-index-headers.html", "index": base + "-index.html"}


def parse_header(raw: bytes, accession: str) -> dict:
    text = html.unescape(raw.decode("latin-1"))
    identities = set(re.findall(rf"ACCESSION\s+NUMBER[^0-9]{{0,100}}({ACCESSION})", text, re.IGNORECASE))
    if identities and identities != {accession}:
        raise ValueError("scope_failure_header_accession_mismatch")
    values = re.findall(r"ACCEPTANCE-DATETIME[^0-9]{0,100}([0-9]+)", text, re.IGNORECASE)
    if not identities or len(values) != 1:
        return {"unknown": "missing_or_nonunique_header_accession_or_acceptance"}
    wall = values[0]
    try:
        candidate = parse_header_acceptance_et(wall)
    except ValueError as exc:
        return {"unknown": str(exc), "header_wall": wall}
    roles: dict[str, list[str]] = {}
    role = "unattributed"
    headings = re.compile(r"^\s*(FILER|FILED BY|SUBJECT COMPANY|ISSUER|REPORTING-OWNER|"
                          r"CO-REGISTRANT|DEPOSITOR|SPONSOR|SUBJECT-COMPANY)\s*:", re.IGNORECASE)
    for line in text.splitlines():
        match = headings.match(line)
        if match:
            role = match[1].upper()
        match = re.search(r"CENTRAL\s+INDEX\s+KEY[^0-9]{0,80}(\d{10})", line, re.IGNORECASE)
        if match:
            roles.setdefault(role, []).append(match[1])
    return {"header_wall": wall, "UTC_assuming_Eastern": candidate.isoformat(),
            "header_CIKs_by_role": {r: sorted(set(ciks)) for r, ciks in roles.items()},
            "role_limit": "Observed header roles only, not issuer/security identity adjudication."}


def parse_index(raw: bytes) -> dict:
    text = html.unescape(raw.decode("latin-1"))
    values = re.findall(
        r"Accepted\s*</div>\s*<div[^>]*>\s*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", text, re.IGNORECASE)
    if len(values) != 1:
        return {"unknown": "index_accepted_missing_or_nonunique"}
    return {"index_wall": re.sub(r"\D", "", values[0])}


def comparison(record: dict, header: dict, index: dict) -> dict:
    result = {"assumption": "Header ACCEPTANCE-DATETIME is an Eastern wall clock, NOT certified.",
              "pair_UTC": record["pair_time"], "bulk_UTC": record["bulk_time"],
              "header": header, "index": index,
              "index_header_wall_agree": None,
              "pair_offset_hours": None, "bulk_offset_hours": None}
    if header.get("header_wall") and index.get("index_wall"):
        result["index_header_wall_agree"] = header["header_wall"] == index["index_wall"]
    conditional = header.get("UTC_assuming_Eastern")
    if not conditional:
        result["class"] = "unknown_header"
        return result
    candidate = datetime.fromisoformat(conditional)
    for source in ("pair", "bulk"):
        result[f"{source}_offset_hours"] = (
            datetime.fromisoformat(record[f"{source}_time"]) - candidate).total_seconds() / 3600
    a, b = result["pair_offset_hours"], result["bulk_offset_hours"]
    result["class"] = ("both_match_assumption" if a == b == 0 else
                       "pair_only_matches_assumption" if a == 0 else
                       "bulk_only_matches_assumption" if b == 0 else "neither_matches_assumption")
    if result["index_header_wall_agree"] is False:
        result["class"] = "header_index_wall_conflict"
    return result
