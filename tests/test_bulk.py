import json
import zipfile

import pytest

from asof import store
from asof.bulk import iter_submissions


def test_selected_bulk_submissions_preserve_all_forms_and_historical_pages(tmp_path) -> None:
    recent = {"accessionNumber": ["new"], "form": ["S-1"], "filingDate": ["2023-01-03"],
              "reportDate": [""], "acceptanceDateTime": ["2023-01-03T20:01:00Z"],
              "primaryDocument": ["new.htm"], "isXBRL": [1], "size": [123]}
    old = {**recent, "accessionNumber": ["old"], "form": ["10-K"],
           "filingDate": ["2022-01-03"], "acceptanceDateTime": ["2022-01-03T20:01:00Z"]}
    top = {"cik": "1", "name": "Synthetic", "sic": "3500", "tickers": ["SYN"],
           "exchanges": ["NYSE"], "entityType": "operating",
           "filings": {"recent": recent, "files": [{"name": "CIK0000000001-submissions-001.json"}]}}
    path = tmp_path / "submissions.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("CIK0000000001.json", json.dumps(top))
        archive.writestr("CIK0000000001-submissions-001.json", json.dumps({
            k: old[k] + recent[k] for k in old}))
        archive.writestr("CIK0000000002.json", "unrequested malformed member")
    selected = list(iter_submissions({1, 3}, path))
    assert len(selected) == 1
    cik, rows = selected[0]
    assert cik == 1
    assert [r["form"] for r in rows] == ["S-1", "10-K", "S-1"]
    assert rows[0]["_entity"]["tickers"] == ["SYN"]
    con = store.connect()
    try:
        store.ingest_submissions(con, rows)
        result = con.execute("SELECT form, knowledge_time, is_xbrl, size FROM filings ORDER BY accession").fetchall()
        assert [r[0] for r in result] == ["S-1", "10-K"]
        assert result[0][1].isoformat() == "2023-01-03T20:01:00+00:00"
        assert result[0][2:] == (True, 123)
    finally:
        con.close()


def test_requested_malformed_bulk_submissions_are_not_silently_skipped(tmp_path) -> None:
    path = tmp_path / "submissions.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("CIK0000000001.json", "{} broken")
    with pytest.raises(ValueError, match="malformed submissions archive member"):
        list(iter_submissions({1}, path))
