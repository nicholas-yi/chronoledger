import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from asof import bulk
from asof.periods import HoldoutAccessError

SCOPE = bulk.FrozenFactWindow("2014-01-01", "2017-12-31", "2014-01-01", "2017-12-31", "a" * 40)


def fixture_facts() -> dict:
    return {"cik": 1, "entityName": "INVENTED", "facts": {"us-gaap": {"Assets": {"units": {
        "USD": [
            {"end": "2014-01-01", "filed": "2014-01-01", "val": 1},
            {"end": "2017-12-31", "filed": "2017-12-31", "val": 2},
            {"end": "2018-01-01", "filed": "2018-02-01", "val": 900},
            {"end": "2023-01-01", "filed": "2023-02-01", "val": 901},
            {"end": "2017-01-01", "filed": "2017-02-01", "accepted_at": "2023-01-01", "val": 902},
            {"end": None, "filed": "2017-02-01", "val": 903},
            {"end": "2017-01-01", "val": 904},
            {"end": "2017-01-01", "filed": "unknown", "val": 905},
            {"end": "2013-12-31", "filed": "2014-02-01", "val": 906},
        ],
    }}}}}


def test_scoped_zip_returns_only_dated_window_facts_without_changing_raw_fixture(tmp_path) -> None:
    path = tmp_path / "fictional.zip"
    original = fixture_facts()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("CIK0000000001.json", json.dumps(original))
    result = dict(bulk.iter_companyfacts({1}, path, scope=SCOPE))[1]
    values = result["facts"]["us-gaap"]["Assets"]["units"]["USD"]
    assert [r["val"] for r in values] == [1, 2]
    assert result["_scope_filter"]["omitted_by_reason"]
    assert result["_scope_filter"]["raw_member_decompressed_in_memory"] is True
    with zipfile.ZipFile(path) as archive:
        assert json.loads(archive.read("CIK0000000001.json")) == original
        assert bulk._load(archive, "CIK0000000001.json", scope=SCOPE) == result


def test_all_bulk_fact_entrypoints_refuse_before_archive_access(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(bulk.zipfile, "ZipFile", lambda *a, **k: pytest.fail("no archive access"))
    for action in (
        lambda: list(bulk.iter_companyfacts({1}, tmp_path / "not_to_open.zip")),
        lambda: bulk.read_companyfacts({1}, tmp_path / "not_to_open.zip"),
        lambda: bulk.max_public_float(tmp_path / "not_to_open.zip"),
        lambda: bulk._load(None, "not_to_read"),
    ):
        with pytest.raises(HoldoutAccessError, match="explicit frozen"):
            action()


@pytest.mark.parametrize("scope", [
    bulk.FrozenFactWindow(None, "2018-12-31", "2012-01-01", "2018-12-31", "a" * 40),
    bulk.FrozenFactWindow("2012-01-01", "2022-01-01", "2012-01-01", "2018-12-31", "a" * 40),
    bulk.FrozenFactWindow("2012-01-01", "2018-12-31", "2012-01-01", "2018-12-31", ""),
])
def test_invalid_or_reserved_windows_refuse_before_io(scope, tmp_path) -> None:
    with pytest.raises(HoldoutAccessError):
        list(bulk.iter_companyfacts({1}, tmp_path / "absent.zip", scope=scope))


def test_accepted_only_dates_and_duration_start_are_checked() -> None:
    data = fixture_facts()
    data["facts"]["us-gaap"]["Assets"]["units"]["USD"] = [
        {"end": "2015-01-01", "accepted": "2015-02-01", "val": 1},
        {"start": "2013-12-31", "end": "2015-01-01", "filed": "2015-02-01", "val": 2},
        {"end": "2015-01-01", "filed": None, "accepted": "2015-02-01", "val": 3},
        {"end": "2016-01-01", "filed": "2015-02-01", "val": 4},
    ]
    result = bulk.filter_companyfacts(data, SCOPE)
    assert [r["val"] for r in result["facts"]["us-gaap"]["Assets"]["units"]["USD"]] == [1]
    assert result["_scope_filter"]["returned_records"] == 1


def test_callers_and_outcome_holds_precede_all_reads(monkeypatch) -> None:
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    modules = []
    for name in ("h4_fundamentals", "h6_quiet"):
        spec = importlib.util.spec_from_file_location(name + "_held", scripts / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules.append(module)
    h4, h6 = modules
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: pytest.fail("no parquet access"))
    for fn in (h4.stage_bulk, h4.stage_sample, h4.stage_features, h4.stage_pairs):
        with pytest.raises(HoldoutAccessError, match="explicit frozen"):
            fn()
        with pytest.raises(HoldoutAccessError, match="HARD HOLD"):
            fn(scope=SCOPE)
    for fn in (h4.stage_outcomes, h4.stage_test, h4.build_panel):
        with pytest.raises(HoldoutAccessError, match="HARD HOLD"):
            fn(scope=SCOPE)
    for fn in (h6.part_a, h6.part_b):
        with pytest.raises(HoldoutAccessError, match="HARD HOLD"):
            fn(pd.DataFrame(), scope=SCOPE)
    with pytest.raises(HoldoutAccessError, match="HARD HOLD"):
        h6.detect(set(), pd.DataFrame(), scope=SCOPE)
    with pytest.raises(HoldoutAccessError, match="explicit frozen"):
        h6.detect(set(), pd.DataFrame())
    for module, args in ((h4, ["outcomes"]), (h6, [])):
        with pytest.raises(HoldoutAccessError, match="scope-file"):
            module.main(args)
