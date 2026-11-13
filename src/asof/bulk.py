"""Readers for SEC nightly bulk archives (all filers, including later-delisted companies)."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

from asof.config import RAW_DIR

BULK = RAW_DIR / "bulk"
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "NT 10-K", "NT 10-Q"}


def _rows(block: dict, cik: int) -> list[dict]:
    keys = ("accessionNumber", "form", "filingDate", "reportDate", "acceptanceDateTime",
            "primaryDocument", "items")
    n = len(block.get("accessionNumber", []))
    out = []
    for i in range(n):
        if block["form"][i] in FORMS and block["acceptanceDateTime"][i]:
            out.append({"cik": cik, **{k: block.get(k, [None] * n)[i] for k in keys}})
    return out


def read_submissions(path: Path = BULK / "submissions.zip") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (entities, filings) for every filer that ever filed a form in ``FORMS``."""
    entities, filings = [], []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        tops = [n for n in names if "-submissions-" not in n]
        pages = {n for n in names if "-submissions-" in n}
        for i, name in enumerate(tops):
            data = json.loads(zf.read(name))
            cik = int(data.get("cik") or name[3:13])
            rows = _rows(data.get("filings", {}).get("recent", {}), cik)
            for page in data.get("filings", {}).get("files", []):
                if page["name"] in pages:
                    rows += _rows(json.loads(zf.read(page["name"])), cik)
            if rows:
                filings += rows
                entities.append({"cik": cik, "name": data.get("name"), "sic": data.get("sic"),
                                 "entity_type": data.get("entityType"),
                                 "tickers": ",".join(data.get("tickers") or []),
                                 "exchanges": ",".join(e for e in (data.get("exchanges") or []) if e)})
            if i % 100_000 == 0:
                print(f"submissions: {i}/{len(tops)}", file=sys.stderr, flush=True)
    f = pd.DataFrame(filings).rename(columns={
        "accessionNumber": "accession", "filingDate": "filing_date", "reportDate": "report_date",
        "primaryDocument": "primary_doc"})
    f["knowledge_time"] = pd.to_datetime(f.pop("acceptanceDateTime"), utc=True)
    return pd.DataFrame(entities), f.drop_duplicates("accession")


def read_companyfacts(ciks: set[int], path: Path = BULK / "companyfacts.zip") -> dict[int, dict]:
    out = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            try:
                cik = int(name[3:13])
            except ValueError:
                continue
            if cik in ciks:
                out[cik] = json.loads(zf.read(name))
    return out


def max_public_float(path: Path = BULK / "companyfacts.zip") -> pd.Series:
    """Maximum reported dei:EntityPublicFloat (USD) per CIK across all filings."""
    vals = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            data = json.loads(zf.read(name))
            facts = data.get("facts", {}).get("dei", {}).get("EntityPublicFloat", {}).get("units", {})
            usd = [f["val"] for f in facts.get("USD", []) if f.get("val") is not None]
            if usd:
                vals[int(data["cik"])] = max(usd)
    return pd.Series(vals, name="max_public_float")
