from datetime import datetime, timedelta, timezone

import pandas as pd

from asof.quiet import quiet_down_revisions

T0 = datetime(2015, 2, 1, tzinfo=timezone.utc)
COLS = ["cik", "tag", "start", "end", "val", "accession", "form"]


def _filings(*rows):
    return pd.DataFrame([{"cik": 1, "accession": a, "form": f, "items": i,
                          "knowledge_time": T0 + timedelta(days=d)} for a, f, i, d in rows])


def test_detects_quiet_downward_revision() -> None:
    facts = pd.DataFrame([
        (1, "NetIncomeLoss", "2014-01-01", "2014-12-31", 100e6, "k1", "10-K"),
        (1, "NetIncomeLoss", "2014-01-01", "2014-12-31", 90e6, "k2", "10-K"),
    ], columns=COLS)
    out = quiet_down_revisions(facts, _filings(("k1", "10-K", None, 0), ("k2", "10-K", None, 365)))
    assert out["accession"].tolist() == ["k2"]
    assert out["rel_change"].iloc[0] == -0.1


def test_upward_or_tiny_revisions_ignored() -> None:
    facts = pd.DataFrame([
        (1, "NetIncomeLoss", "2014-01-01", "2014-12-31", 100e6, "k1", "10-K"),
        (1, "NetIncomeLoss", "2014-01-01", "2014-12-31", 99.5e6, "k2", "10-K"),
        (1, "NetIncomeLoss", "2013-01-01", "2013-12-31", 100e6, "k0", "10-K"),
        (1, "NetIncomeLoss", "2013-01-01", "2013-12-31", 120e6, "k2", "10-K"),
    ], columns=COLS)
    f = _filings(("k0", "10-K", None, -365), ("k1", "10-K", None, 0), ("k2", "10-K", None, 365))
    assert quiet_down_revisions(facts, f).empty


def test_not_quiet_after_recent_amendment_or_402() -> None:
    facts = pd.DataFrame([
        (1, "NetIncomeLoss", "2014-01-01", "2014-12-31", 100e6, "k1", "10-K"),
        (1, "NetIncomeLoss", "2014-01-01", "2014-12-31", 80e6, "k2", "10-K"),
    ], columns=COLS)
    f = _filings(("k1", "10-K", None, 0), ("e1", "8-K", "4.02,9.01", 300), ("k2", "10-K", None, 365))
    assert quiet_down_revisions(facts, f).empty


def test_scale_change_excluded() -> None:
    rows = []
    for tag in ("NetIncomeLoss", "Revenues", "OperatingIncomeLoss"):
        rows += [(1, tag, "2014-01-01", "2014-12-31", 100e6, "k1", "10-K"),
                 (1, tag, "2014-01-01", "2014-12-31", 0.1e6 * 100, "k2", "10-K")]
    facts = pd.DataFrame(rows, columns=COLS)
    f = _filings(("k1", "10-K", None, 0), ("k2", "10-K", None, 365))
    assert quiet_down_revisions(facts, f).empty
