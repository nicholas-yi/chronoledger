import importlib
from pathlib import Path

import pandas as pd
import pytest

from asof.periods import HoldoutAccessError


@pytest.mark.parametrize("module_name,function", [
    ("run_benchmark_diagnostic", "verified_assets"),
    ("run_reader_real3", "native_pins"),
    ("check_finqa_years", "check_quarantine"),
])
def test_legacy_financial_readers_without_dates_stop_before_source_access(
    monkeypatch, tmp_path, module_name: str, function: str,
) -> None:
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    module = importlib.import_module(module_name)
    with pytest.raises(HoldoutAccessError, match="dated documents"):
        getattr(module, function)(tmp_path / "not_to_be_read.json") if (
            function == "check_quarantine") else getattr(module, function)()


def test_feature_build_checks_dates_before_client_or_cached_skip(monkeypatch) -> None:
    from asof import features

    monkeypatch.setattr(features, "feature_path", lambda _: pytest.fail("no source lookup"))
    with pytest.raises(HoldoutAccessError):
        features.build([(1, "fake", "a.htm", "10-K")])


def test_development_inventory_counts_only_metadata_and_file_existence(tmp_path, monkeypatch) -> None:
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    module = importlib.import_module("count_kpi_development_cache")
    rows = []
    for cik in (1, 2):
        for year in (2014, 2015, 2016):
            rows.append({
                "cik": cik, "accession": f"{cik:010d}-{year+1}-fake", "form": "10-K",
                "knowledge_time": pd.Timestamp(f"{year+1}-02-01", tz="UTC"),
                "report_date": f"{year}-12-31", "primary_doc": "a.htm", "items": "",
            })
    pd.DataFrame(rows).to_parquet(tmp_path / "bulk_filings.parquet")

    class ExistenceOnly:
        def is_file(self):
            return True

        def read_bytes(self):
            pytest.fail("metadata inventory must not open a cached body")

    monkeypatch.setattr(module, "response_cache_path", lambda *args: ExistenceOnly())
    report, candidates = module.inventory(tmp_path)
    assert report["eligible_issuer_triples"] == 2
    assert report["status"] == "stopped_insufficient_cache"
    assert report["document_bodies_read"] == 0
    assert len(candidates) == 2
