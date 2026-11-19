import importlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from asof import cli
from asof.bulk import FrozenFactWindow, filter_submissions
from asof.edgar import EdgarClient
from asof.periods import HoldoutAccessError

SCOPE = FrozenFactWindow("2014-01-01", "2017-12-31", "2014-01-01", "2017-12-31", "a" * 40)


def submissions():
    return [{"filingDate": f"{year}-02-01", "acceptanceDateTime": f"{year}-02-01T10:00:00Z",
             "reportDate": f"{year-1}-12-31", "accessionNumber": f"INVENTED-{year}"}
            for year in (2015, 2025)]


def facts():
    return {"cik": 1, "facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"end": f"{year-1}-12-31", "filed": f"{year}-02-01", "val": year,
         "accn": f"INVENTED-{year}", "form": "10-K"} for year in (2015, 2025)
    ]}}}}}


def test_missing_or_reserved_scope_refuses_before_client_database_or_directory(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("scope refusal must precede client, database and directory access")

    monkeypatch.setattr(cli, "EdgarClient", forbidden)
    monkeypatch.setattr(cli.store, "connect", forbidden)
    db = tmp_path / "not-created" / "example.duckdb"
    for scope in (None, replace(SCOPE, filing_end="2025-01-01")):
        with pytest.raises(HoldoutAccessError):
            cli.ingest([1], str(db), scope=scope)
    with pytest.raises(SystemExit) as exc:
        cli.main(["ingest", "1", "--db", str(db)])
    assert exc.value.code == 2 and not db.parent.exists()
    invalid = tmp_path / "reserved.json"
    invalid.write_text(json.dumps({**SCOPE.__dict__, "fact_end": "2025-01-01"}))
    with pytest.raises(SystemExit):
        cli.main(["ingest", "1", "--scope-file", str(invalid), "--db", str(db)])
    assert not db.parent.exists()


def test_api_scope_refuses_before_cache_transport_and_filters_returned_facts(monkeypatch):
    client = EdgarClient.__new__(EdgarClient)
    calls = []

    def get_json(*args, **kwargs):
        calls.append(args)
        return facts()

    monkeypatch.setattr(client, "get_json", get_json)
    with pytest.raises(HoldoutAccessError):
        client.companyfacts(1)
    assert not calls
    result = client.companyfacts(1, scope=SCOPE)
    assert result["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["val"] == 2015
    assert result["_scope_filter"]["returned_records"] == 1
    assert not result["_scope_filter"]["raw_member_decompressed_in_memory"]
    assert result["_scope_filter"]["raw_response_decoded_in_memory"]


def test_valid_cli_scope_reaches_only_filtered_database_boundaries(monkeypatch, tmp_path, capsys):
    captured, closed = {}, []
    client = EdgarClient.__new__(EdgarClient)
    monkeypatch.setattr(client, "get_json", lambda *a, **k: facts())
    monkeypatch.setattr(client, "submissions", lambda *a: submissions())
    monkeypatch.setattr(client, "close", lambda: closed.append("client"))
    monkeypatch.setattr(cli, "EdgarClient", lambda: client)

    class Connection:
        def close(self):
            closed.append("connection")

    monkeypatch.setattr(cli.store, "connect", lambda _: Connection())

    def ingest_submissions(connection, rows):
        captured["submissions"] = rows
        return len(rows)

    def ingest_facts(connection, frame):
        captured["facts"] = frame
        return len(frame)

    monkeypatch.setattr(cli.store, "ingest_submissions", ingest_submissions)
    monkeypatch.setattr(cli.store, "ingest_facts", ingest_facts)
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps(SCOPE.__dict__))
    cli.main(["ingest", "1", "--scope-file", str(scope), "--db", ":memory:"])
    assert len(captured["submissions"]) == len(captured["facts"]) == 1
    assert captured["facts"]["filed"].tolist() == ["2015-02-01"]
    assert closed == ["connection", "client"]
    receipt = json.loads(capsys.readouterr().err)
    assert sum(receipt["submission_scope"]["omitted_by_reason"].values()) == 1
    assert sum(receipt["fact_scope"]["omitted_by_reason"].values()) == 1


def test_undated_metadata_is_not_ingested_and_client_closes_if_database_open_fails(monkeypatch):
    rows, receipt = filter_submissions([*submissions(), {"filingDate": "unknown"}], SCOPE)
    assert len(rows) == 1 and sum(receipt["omitted_by_reason"].values()) == 2
    closed = []

    class Client:
        def close(self):
            closed.append(True)

    def fail(_):
        raise OSError("invented database failure")

    monkeypatch.setattr(cli, "EdgarClient", Client)
    monkeypatch.setattr(cli.store, "connect", fail)
    with pytest.raises(OSError, match="invented"):
        cli.ingest([1], ":memory:", scope=SCOPE)
    assert closed == [True]


@pytest.mark.parametrize("module_name,stages", [("h4_fundamentals", ["outcomes"]), ("h6_quiet", [])])
def test_valid_scope_file_does_not_lift_held_cli_or_touch_study_inputs(
    monkeypatch, tmp_path, module_name, stages,
):
    from asof import ledger

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    module = importlib.import_module(module_name)
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps(SCOPE.__dict__))

    def forbidden(*args, **kwargs):
        pytest.fail("held CLI touched source data, transport or trial logging")

    monkeypatch.setattr(module.pd, "read_parquet", forbidden)
    monkeypatch.setattr(ledger, "log_trial", forbidden)
    monkeypatch.setattr(ledger, "development_trial", forbidden)
    monkeypatch.setattr(cli, "EdgarClient", forbidden)
    with pytest.raises(HoldoutAccessError, match="HARD HOLD"):
        module.main(["--scope-file", str(scope), *stages])
