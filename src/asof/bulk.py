"""SEC bulk readers; fact values require an explicit declared frozen development window.

Filtering constrains returned values, not bytes accessed: a company ZIP member
is still decompressed and decoded in memory. This is not holdout isolation.
Legacy H4/H6 file-backed stages remain independently hard held.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd

from asof.config import RAW_DIR
from asof.document_scope import DateValue, parse_document_date, require_development_dates
from asof.periods import HoldoutAccessError

BULK = RAW_DIR / "bulk"
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "NT 10-K", "NT 10-Q"}


@dataclass(frozen=True)
class FrozenFactWindow:
    fact_start: DateValue
    fact_end: DateValue
    filing_start: DateValue
    filing_end: DateValue
    freeze_ref: str

    def bounds(self) -> dict[str, date]:
        if not isinstance(self.freeze_ref, str) or re.fullmatch(r"[a-f0-9]{40}", self.freeze_ref) is None:
            raise HoldoutAccessError("a frozen source/config revision reference is required")
        dates = require_development_dates({
            "fact_start": self.fact_start, "fact_end": self.fact_end,
            "filing_start": self.filing_start, "filing_end": self.filing_end,
        })
        if dates["fact_start"] > dates["fact_end"] or dates["filing_start"] > dates["filing_end"]:
            raise HoldoutAccessError("dataset date windows must be ordered")
        return dates


def require_fact_window(scope: FrozenFactWindow | None) -> FrozenFactWindow:
    if not isinstance(scope, FrozenFactWindow):
        raise HoldoutAccessError("explicit frozen development fact-date and filing-date windows required")
    scope.bounds()
    return scope


def load_fact_window(path: Path | None) -> FrozenFactWindow:
    if path is None:
        raise HoldoutAccessError("supply a frozen development --scope-file before any data access")
    with path.open("rb") as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError("scope metadata exceeds 16 KiB")
    return require_fact_window(FrozenFactWindow(**json.loads(raw)))


def hold_outcome_stage(name: str) -> None:
    raise HoldoutAccessError(
        f"CL-HARDEN-1 HARD HOLD: {name}; no reads permitted until a new explicit user decision. "
        "A supplied date window does not lift this hold.")


def _record_rejection(record: dict, bounds: dict[str, date]) -> str | None:
    if not isinstance(record, dict):
        return "malformed_record"
    filing_keys = [k for k in ("filed", "accepted", "accepted_at", "acceptanceDateTime",
                              "knowledge_time") if k in record]
    if not filing_keys or "end" not in record:
        return "unknown_dates"
    try:
        filing_dates = [parse_document_date(record[k], k) for k in filing_keys]
        period_end = parse_document_date(record["end"], "end")
        start = parse_document_date(record["start"], "start") if "start" in record else period_end
        require_development_dates({
            "period_start": start, "period_end": period_end,
            **dict(zip(filing_keys, filing_dates, strict=True)),
        })
    except HoldoutAccessError:
        return "unknown_unparseable_or_reserved_dates"
    if any(not bounds["filing_start"] <= d <= bounds["filing_end"] for d in filing_dates):
        return "outside_filing_window"
    if not bounds["fact_start"] <= start <= period_end <= bounds["fact_end"]:
        return "outside_or_reversed_fact_window"
    if period_end > min(filing_dates):
        return "period_after_filing"
    return None


def filter_companyfacts(
    data: dict, scope: FrozenFactWindow | None, *,
    source_kind: Literal["zip_member", "api_response"] = "zip_member",
) -> dict:
    window = require_fact_window(scope)
    if source_kind not in ("zip_member", "api_response"):
        raise ValueError("unknown companyfacts source kind")
    bounds = window.bounds()
    if not isinstance(data, dict) or not isinstance(data.get("facts"), dict):
        raise TypeError("companyfacts member must contain a facts object")
    result = {k: data[k] for k in ("cik", "entityName") if k in data}
    facts = {}
    omitted: Counter[str] = Counter()
    seen = returned = 0
    for namespace, tags in data["facts"].items():
        if not isinstance(tags, dict):
            raise TypeError("malformed companyfacts namespace")
        selected_tags = {}
        for tag, definition in tags.items():
            if not isinstance(definition, dict) or not isinstance(definition.get("units"), dict):
                raise TypeError("malformed companyfacts tag/units")
            units = {}
            for unit, records in definition["units"].items():
                if not isinstance(records, list):
                    raise TypeError("companyfacts unit must contain fact records")
                kept = []
                for record in records:
                    seen += 1
                    reason = _record_rejection(record, bounds)
                    if reason is None:
                        kept.append(record)
                        returned += 1
                    else:
                        omitted[reason] += 1
                if kept:
                    units[unit] = kept
            if units:
                selected_tags[tag] = {k: v for k, v in definition.items() if k != "units"} | {
                    "units": units}
        if selected_tags:
            facts[namespace] = selected_tags
    result["facts"] = facts
    result["_scope_filter"] = {
        "input_records": seen, "returned_records": returned, "omitted_by_reason": dict(omitted),
        "window": {k: v.isoformat() for k, v in bounds.items()}, "freeze_ref": window.freeze_ref,
        "raw_member_decompressed_in_memory": source_kind == "zip_member",
        "raw_response_decoded_in_memory": True, "byte_level_isolation": False,
    }
    return result


def filter_submissions(rows: list[dict], scope: FrozenFactWindow | None) -> tuple[list[dict], dict]:
    """Constrain metadata returned to scoped ingestion; raw API metadata is still decoded."""
    window = require_fact_window(scope)
    bounds = window.bounds()
    kept = []
    omitted: Counter[str] = Counter()
    for row in rows:
        reason = _record_rejection({
            "filed": row.get("filingDate"), "accepted": row.get("acceptanceDateTime"),
            "end": row.get("reportDate"),
        }, bounds)
        if reason is None:
            kept.append(row)
        else:
            omitted[reason] += 1
    return kept, {"input_records": len(rows), "returned_records": len(kept),
                  "omitted_by_reason": dict(omitted), "freeze_ref": window.freeze_ref}


def _rows(block: dict, cik: int) -> list[dict]:
    keys = ("accessionNumber", "form", "filingDate", "reportDate", "acceptanceDateTime",
            "primaryDocument", "items")
    n = len(block.get("accessionNumber", []))
    out = []
    for i in range(n):
        if block["form"][i] in FORMS and block["acceptanceDateTime"][i]:
            out.append({"cik": cik, **{k: block.get(k, [None] * n)[i] for k in keys}})
    return out


def _load_metadata(zf: zipfile.ZipFile, name: str) -> dict | None:
    """Parse one archive member; malformed or empty members return None (and are counted)."""
    raw = zf.read(name)
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _load(
    zf: zipfile.ZipFile, name: str, *, scope: FrozenFactWindow | None = None,
) -> dict:
    require_fact_window(scope)
    data = _load_metadata(zf, name)
    if data is None:
        raise ValueError(f"malformed companyfacts archive member: {name}")
    return filter_companyfacts(data, scope)


def read_submissions(path: Path = BULK / "submissions.zip") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (entities, filings) for every filer that ever filed a form in ``FORMS``."""
    entities, filings = [], []
    bad = 0
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        tops = [n for n in names if "-submissions-" not in n]
        pages = {n for n in names if "-submissions-" in n}
        for i, name in enumerate(tops):
            data = _load_metadata(zf, name)
            if data is None:
                bad += 1
                continue
            cik = int(data.get("cik") or name[3:13])
            rows = _rows(data.get("filings", {}).get("recent", {}), cik)
            for page in data.get("filings", {}).get("files", []):
                if page["name"] in pages:
                    pdata = _load_metadata(zf, page["name"])
                    if pdata is None:
                        bad += 1
                        continue
                    rows += _rows(pdata, cik)
            if rows:
                filings += rows
                entities.append({"cik": cik, "name": data.get("name"), "sic": data.get("sic"),
                                 "entity_type": data.get("entityType"),
                                 "tickers": ",".join(data.get("tickers") or []),
                                 "exchanges": ",".join(e for e in (data.get("exchanges") or []) if e)})
            if i % 100_000 == 0:
                print(f"submissions: {i}/{len(tops)}, {bad} malformed", file=sys.stderr, flush=True)
    print(f"submissions: done, {bad} malformed members skipped", file=sys.stderr, flush=True)
    f = pd.DataFrame(filings).rename(columns={
        "accessionNumber": "accession", "filingDate": "filing_date", "reportDate": "report_date",
        "primaryDocument": "primary_doc"})
    f["knowledge_time"] = pd.to_datetime(f.pop("acceptanceDateTime"), utc=True)
    return pd.DataFrame(entities), f.drop_duplicates("accession")


def iter_submissions(ciks: set[int], path: Path = BULK / "submissions.zip"):
    """Yield the same complete per-CIK rows as EdgarClient.submissions from the bulk archive."""
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        for cik in sorted(ciks):
            name = f"CIK{cik:010d}.json"
            if name not in names:
                continue  # The caller can fetch CIKs absent from this archive through the API.
            data = _load_metadata(zf, name)
            if data is None:
                raise ValueError(f"malformed submissions archive member: {name}")
            blocks = [data["filings"]["recent"]]
            for page in data["filings"].get("files", []):
                block = _load_metadata(zf, page["name"])
                if block is None:
                    raise ValueError(f"malformed submissions archive member: {page['name']}")
                blocks.append(block)
            meta = {k: data.get(k) for k in ("cik", "name", "tickers", "exchanges", "sic", "entityType")}
            rows = []
            for block in blocks:
                for i in range(len(block["accessionNumber"])):
                    rows.append({**{k: block[k][i] for k in block}, "_entity": meta})
            yield cik, rows


def iter_companyfacts(
    ciks: set[int] | None, path: Path = BULK / "companyfacts.zip", *,
    scope: FrozenFactWindow | None = None,
):
    """Yield (cik, facts JSON) one firm at a time, keeping memory flat."""
    require_fact_window(scope)
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            try:
                cik = int(name[3:13])
            except ValueError:
                continue
            if ciks is None or cik in ciks:
                yield cik, _load(zf, name, scope=scope)


def read_companyfacts(
    ciks: set[int], path: Path = BULK / "companyfacts.zip", *,
    scope: FrozenFactWindow | None = None,
) -> dict[int, dict]:
    """Load facts for a small set of CIKs. Prefer ``iter_companyfacts`` for large sets."""
    return dict(iter_companyfacts(ciks, path, scope=scope))


def max_public_float(
    path: Path = BULK / "companyfacts.zip", *, scope: FrozenFactWindow | None = None,
) -> pd.Series:
    """Maximum reported dei:EntityPublicFloat (USD) per CIK across all filings."""
    vals = {}
    require_fact_window(scope)
    for cik, data in iter_companyfacts(None, path, scope=scope):
        facts = data.get("facts", {}).get("dei", {}).get("EntityPublicFloat", {}).get("units", {})
        usd = [f["val"] for f in facts.get("USD", []) if f.get("val") is not None]
        if usd:
            vals[cik] = max(usd)
    return pd.Series(vals, name="max_public_float")
