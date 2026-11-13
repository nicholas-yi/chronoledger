"""Bitemporal store.

Every fact has two time axes:

* valid time: the economic period the fact describes (``period_start``..``period_end``)
* knowledge time: when the fact became public (EDGAR acceptance, UTC)

All research code must read through ``*_as_of`` functions so that nothing published after the
as-of instant can influence a result. ``tests/test_invariance.py`` enforces this property.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import duckdb
import pandas as pd

from asof.timeutil import ET, parse_acceptance_utc

SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    cik BIGINT NOT NULL,
    accession VARCHAR PRIMARY KEY,
    form VARCHAR NOT NULL,
    filing_date DATE,
    report_date DATE,
    knowledge_time TIMESTAMPTZ NOT NULL,
    primary_doc VARCHAR,
    items VARCHAR,
    is_xbrl BOOLEAN,
    size BIGINT
);
CREATE TABLE IF NOT EXISTS xbrl_facts (
    cik BIGINT NOT NULL,
    taxonomy VARCHAR NOT NULL,
    tag VARCHAR NOT NULL,
    unit VARCHAR NOT NULL,
    period_start DATE,
    period_end DATE NOT NULL,
    value DOUBLE NOT NULL,
    accession VARCHAR NOT NULL,
    form VARCHAR,
    fy INTEGER,
    fp VARCHAR,
    filed DATE NOT NULL,
    frame VARCHAR,
    knowledge_time TIMESTAMPTZ NOT NULL,
    knowledge_time_source VARCHAR NOT NULL
);
"""


def connect(path: str = ":memory:", read_only: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(path, read_only=read_only)
    con.execute("SET TimeZone='UTC'")
    if not read_only:
        con.execute(SCHEMA)
    return con


def _date_or_none(value: str | None) -> str | None:
    return value or None


def ingest_submissions(con: duckdb.DuckDBPyConnection, rows: Iterable[dict[str, Any]]) -> int:
    records = []
    for r in rows:
        if not r.get("acceptanceDateTime"):
            continue
        records.append(
            {
                "cik": int(r["_entity"]["cik"]) if r.get("_entity") else int(r["cik"]),
                "accession": r["accessionNumber"],
                "form": r["form"],
                "filing_date": _date_or_none(r.get("filingDate")),
                "report_date": _date_or_none(r.get("reportDate")),
                "knowledge_time": parse_acceptance_utc(r["acceptanceDateTime"]),
                "primary_doc": r.get("primaryDocument"),
                "items": r.get("items") or None,
                "is_xbrl": bool(r.get("isXBRL")),
                "size": r.get("size"),
            }
        )
    if not records:
        return 0
    df = pd.DataFrame.from_records(records).drop_duplicates("accession")
    con.register("_new_filings", df)
    con.execute(
        "INSERT INTO filings SELECT * FROM _new_filings "
        "WHERE accession NOT IN (SELECT accession FROM filings)"
    )
    con.unregister("_new_filings")
    return len(df)


def _conservative_knowledge_time(filed: str) -> datetime:
    """Fallback when an accession is unknown: end of the filed date in US/Eastern.

    EDGAR assigns the next business day as filing date for late-evening acceptances, so the true
    acceptance is never later than the end of the filed date. Using it can only delay, never
    leak, information.
    """
    day = datetime.fromisoformat(filed).date()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=ET)
    return end.astimezone(timezone.utc)


def flatten_companyfacts(cf: dict[str, Any]) -> pd.DataFrame:
    cik = int(cf["cik"])
    rows = []
    for taxonomy, tags in cf.get("facts", {}).items():
        for tag, body in tags.items():
            for unit, facts in body.get("units", {}).items():
                for f in facts:
                    if f.get("val") is None or not f.get("accn") or not f.get("filed"):
                        continue
                    rows.append(
                        (
                            cik, taxonomy, tag, unit, f.get("start"), f["end"], float(f["val"]),
                            f["accn"], f.get("form"), f.get("fy"), f.get("fp"), f["filed"],
                            f.get("frame"),
                        )
                    )
    cols = [
        "cik", "taxonomy", "tag", "unit", "period_start", "period_end", "value", "accession",
        "form", "fy", "fp", "filed", "frame",
    ]
    return pd.DataFrame(rows, columns=cols)


def ingest_facts(con: duckdb.DuckDBPyConnection, facts: pd.DataFrame) -> int:
    """Insert flattened XBRL facts, resolving knowledge time from the filings table."""
    if facts.empty:
        return 0
    facts = facts.drop_duplicates(
        ["cik", "taxonomy", "tag", "unit", "period_start", "period_end", "accession", "value"]
    ).copy()
    known = con.execute("SELECT accession, knowledge_time FROM filings").df()
    merged = facts.merge(known, on="accession", how="left")
    missing = merged["knowledge_time"].isna()
    merged["knowledge_time_source"] = "acceptance"
    merged.loc[missing, "knowledge_time"] = merged.loc[missing, "filed"].map(
        _conservative_knowledge_time
    )
    merged.loc[missing, "knowledge_time_source"] = "filed_date_end_et"
    merged["knowledge_time"] = pd.to_datetime(merged["knowledge_time"], utc=True)
    con.register("_new_facts", merged)
    con.execute(
        """
        INSERT INTO xbrl_facts
        SELECT cik, taxonomy, tag, unit, CAST(period_start AS DATE), CAST(period_end AS DATE),
               value, accession, form, fy, fp, CAST(filed AS DATE), frame, knowledge_time,
               knowledge_time_source
        FROM _new_facts
        """
    )
    con.unregister("_new_facts")
    return len(merged)


def facts_as_of(
    con: duckdb.DuckDBPyConnection,
    as_of: datetime,
    tags: list[str] | None = None,
    ciks: list[int] | None = None,
) -> pd.DataFrame:
    """Latest known value of each (cik, tag, unit, period) as of ``as_of``.

    Ties at identical knowledge time are broken by accession for determinism.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    where = ["knowledge_time <= ?"]
    params: list[Any] = [as_of]
    if tags:
        where.append(f"tag IN ({','.join('?' * len(tags))})")
        params += tags
    if ciks:
        where.append(f"cik IN ({','.join('?' * len(ciks))})")
        params += ciks
    sql = f"""
        SELECT cik, taxonomy, tag, unit, period_start, period_end, value, accession,
               knowledge_time
        FROM xbrl_facts
        WHERE {' AND '.join(where)}
        QUALIFY row_number() OVER (
            PARTITION BY cik, taxonomy, tag, unit, period_start, period_end
            ORDER BY knowledge_time DESC, accession DESC
        ) = 1
        ORDER BY cik, taxonomy, tag, unit, period_end, period_start
    """
    return con.execute(sql, params).df()


def revisions_as_of(
    con: duckdb.DuckDBPyConnection, as_of: datetime, rel_tol: float = 1e-6
) -> pd.DataFrame:
    """Value changes for the same (cik, tag, unit, period) across filings known by ``as_of``.

    These include restatements, reclassifications, and corrections. Interpreting which is which
    is left to downstream analysis.
    """
    sql = """
        WITH known AS (
            SELECT * FROM xbrl_facts WHERE knowledge_time <= ?
        ), ordered AS (
            SELECT cik, taxonomy, tag, unit, period_start, period_end, value, accession,
                   knowledge_time,
                   lag(value) OVER w AS prev_value,
                   lag(accession) OVER w AS prev_accession,
                   lag(knowledge_time) OVER w AS prev_knowledge_time
            FROM known
            WINDOW w AS (
                PARTITION BY cik, taxonomy, tag, unit, period_start, period_end
                ORDER BY knowledge_time, accession
            )
        )
        SELECT * FROM ordered
        WHERE prev_value IS NOT NULL
          AND abs(value - prev_value) > ? * greatest(abs(prev_value), 1.0)
        ORDER BY cik, tag, period_end, knowledge_time
    """
    return con.execute(sql, [as_of, rel_tol]).df()


def filings_as_of(
    con: duckdb.DuckDBPyConnection, as_of: datetime, forms: list[str] | None = None
) -> pd.DataFrame:
    where = ["knowledge_time <= ?"]
    params: list[Any] = [as_of]
    if forms:
        where.append(f"form IN ({','.join('?' * len(forms))})")
        params += forms
    return con.execute(
        f"SELECT * FROM filings WHERE {' AND '.join(where)} ORDER BY cik, knowledge_time",
        params,
    ).df()
