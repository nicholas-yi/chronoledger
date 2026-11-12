"""Time-travel invariance: the core guard against look-ahead bias.

For any research function ``fn(con, as_of)``, running it on the full store must give exactly the
same result as running it on a store that only contains what was public at ``as_of``. If not,
``fn`` reads information from the future.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import duckdb
import pandas as pd

from asof.store import SCHEMA

ResearchFn = Callable[[duckdb.DuckDBPyConnection, datetime], pd.DataFrame]


def truncated_copy(con: duckdb.DuckDBPyConnection, cutoff: datetime) -> duckdb.DuckDBPyConnection:
    """A new in-memory store holding only rows whose knowledge time is <= cutoff."""
    out = duckdb.connect(":memory:")
    out.execute("SET TimeZone='UTC'")
    out.execute(SCHEMA)
    for table in ("filings", "xbrl_facts"):
        df = con.execute(f"SELECT * FROM {table} WHERE knowledge_time <= ?", [cutoff]).df()
        out.register("_src", df)
        out.execute(f"INSERT INTO {table} SELECT * FROM _src")
        out.unregister("_src")
    return out


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(list(df.columns), kind="mergesort").reset_index(drop=True)
    return df


def invariance_violation(
    con: duckdb.DuckDBPyConnection, fn: ResearchFn, as_of: datetime
) -> str | None:
    """Return a description of the violation, or None if ``fn`` is invariant at ``as_of``."""
    full = _normalize(fn(con, as_of))
    truncated_con = truncated_copy(con, as_of)
    try:
        partial = _normalize(fn(truncated_con, as_of))
    finally:
        truncated_con.close()
    try:
        pd.testing.assert_frame_equal(full, partial, check_dtype=False)
    except AssertionError as exc:
        return f"{getattr(fn, '__name__', fn)} differs at {as_of.isoformat()}: {exc}"
    return None
