"""Look-ahead guards: invariance holds for correct code and fails for known-leaky code."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import duckdb
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from asof import store
from asof.invariance import invariance_violation

BASE = datetime(2014, 1, 1, tzinfo=UTC)
FACT_COLS = ["cik", "taxonomy", "tag", "unit", "period_start", "period_end", "value",
             "accession", "form", "fy", "fp", "filed", "frame"]


def _build(events: list[tuple[int, int, int, float, int]]) -> duckdb.DuckDBPyConnection:
    """events: (cik, period_index, hours_after_period_end, value, accession_id).

    An accession is one filing with a single acceptance time; facts it reports share it.
    """
    con = store.connect()
    filings: dict[str, dict] = {}
    facts = []
    for cik, period_idx, hours, value, acc_id in events:
        accession = f"{cik:010d}-15-{acc_id:06d}"
        period_end = date(2014, 3, 31) + timedelta(days=91 * period_idx)
        if accession not in filings:
            knowledge = datetime.combine(period_end, datetime.min.time(), tzinfo=UTC)
            knowledge += timedelta(hours=24 + hours)
            filings[accession] = {
                "accessionNumber": accession,
                "form": "10-Q",
                "filingDate": knowledge.date().isoformat(),
                "reportDate": period_end.isoformat(),
                "acceptanceDateTime": knowledge.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "cik": cik,
            }
        filed = filings[accession]["filingDate"]
        facts.append((cik, "us-gaap", "Revenues", "USD", None, period_end.isoformat(), value,
                      accession, "10-Q", None, None, filed, None))
    store.ingest_submissions(con, list(filings.values()))
    store.ingest_facts(con, pd.DataFrame(facts, columns=FACT_COLS))
    return con


def correct_fn(con: duckdb.DuckDBPyConnection, as_of: datetime) -> pd.DataFrame:
    return store.facts_as_of(con, as_of)[["cik", "tag", "period_end", "value"]]


def correct_revisions(con: duckdb.DuckDBPyConnection, as_of: datetime) -> pd.DataFrame:
    return store.revisions_as_of(con, as_of)[["cik", "tag", "period_end", "value", "prev_value"]]


def leaky_period_end_fn(con: duckdb.DuckDBPyConnection, as_of: datetime) -> pd.DataFrame:
    """Classic look-ahead bug: treating data as known at period end, not at filing."""
    return con.execute(
        """
        SELECT cik, tag, period_end, value FROM xbrl_facts
        WHERE period_end <= CAST(? AS DATE)
        QUALIFY row_number() OVER (
            PARTITION BY cik, tag, period_end ORDER BY knowledge_time DESC, accession DESC) = 1
        """,
        [as_of],
    ).df()


def leaky_latest_value_fn(con: duckdb.DuckDBPyConnection, as_of: datetime) -> pd.DataFrame:
    """Another classic bug: filtering periods by date but taking the latest revision ever."""
    known_periods = con.execute(
        "SELECT DISTINCT cik, tag, period_end FROM xbrl_facts WHERE knowledge_time <= ?", [as_of]
    ).df()
    latest = con.execute(
        """
        SELECT cik, tag, period_end, value FROM xbrl_facts
        QUALIFY row_number() OVER (
            PARTITION BY cik, tag, period_end ORDER BY knowledge_time DESC, accession DESC) = 1
        """
    ).df()
    return known_periods.merge(latest, on=["cik", "tag", "period_end"])


event = st.tuples(
    st.integers(1, 3),
    st.integers(0, 8),
    st.integers(0, 24 * 200),
    st.floats(1, 1e9, allow_nan=False),
    st.integers(1, 40),
)


@settings(max_examples=60, deadline=None)
@given(st.lists(event, min_size=1, max_size=40), st.integers(0, 24 * 1200))
def test_store_queries_are_time_invariant(events, hours) -> None:
    con = _build(events)
    as_of = BASE + timedelta(hours=hours)
    assert invariance_violation(con, correct_fn, as_of) is None
    assert invariance_violation(con, correct_revisions, as_of) is None


def test_canary_period_end_leak_is_detected() -> None:
    # Q1 2014 ends 2014-03-31; filed ~31 days later. As of mid-April it is not yet public.
    con = _build([(1, 0, 24 * 30, 100.0, 1)])
    as_of = datetime(2014, 4, 15, tzinfo=UTC)
    assert invariance_violation(con, correct_fn, as_of) is None
    assert invariance_violation(con, leaky_period_end_fn, as_of) is not None


def test_canary_latest_revision_leak_is_detected() -> None:
    # Same period reported (100) then restated (90) in a later filing.
    con = _build([(1, 0, 24, 100.0, 1), (1, 0, 24 * 120, 90.0, 2)])
    as_of = datetime(2014, 5, 15, tzinfo=UTC)
    assert store.facts_as_of(con, as_of)["value"].tolist() == [100.0]
    assert invariance_violation(con, leaky_latest_value_fn, as_of) is not None


def test_revision_detected_only_after_restatement_is_public() -> None:
    con = _build([(1, 0, 24, 100.0, 1), (1, 0, 24 * 120, 90.0, 2)])
    before = datetime(2014, 5, 15, tzinfo=UTC)
    after = datetime(2014, 9, 1, tzinfo=UTC)
    assert store.revisions_as_of(con, before).empty
    rev = store.revisions_as_of(con, after)
    assert rev[["prev_value", "value"]].values.tolist() == [[100.0, 90.0]]


def test_unknown_accession_falls_back_conservatively() -> None:
    con = store.connect()
    facts = pd.DataFrame(
        [(1, "us-gaap", "Revenues", "USD", None, "2014-03-31", 1.0, "X", "10-Q", None, None,
          "2014-05-01", None)],
        columns=FACT_COLS,
    )
    store.ingest_facts(con, facts)
    row = con.execute("SELECT knowledge_time, knowledge_time_source FROM xbrl_facts").fetchone()
    # End of 2014-05-01 in US/Eastern (EDT) is 2014-05-02 04:00 UTC.
    assert row[0] == datetime(2014, 5, 2, 4, tzinfo=UTC)
    assert row[1] == "filed_date_end_et"
