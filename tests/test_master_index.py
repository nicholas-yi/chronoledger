import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest


def _script():
    spec = importlib.util.spec_from_file_location(
        "master_index_script", Path(__file__).resolve().parents[1] / "scripts" / "master_index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_master_index_streams_only_elapsed_quarters(tmp_path, monkeypatch) -> None:
    script = _script()
    calls = []

    def fetch(client, year, quarter):
        calls.append((year, quarter))
        return pd.DataFrame({"cik": [year], "quarter": [quarter]})

    monkeypatch.setattr(script, "master_index", fetch)
    output = tmp_path / "master.parquet"
    script.build(None, output, datetime(2012, 5, 1, tzinfo=UTC))
    assert calls == [(2011, q) for q in range(1, 5)] + [(2012, 1), (2012, 2)]
    result = pd.read_parquet(output)
    assert list(zip(result["cik"], result["quarter"], strict=True)) == calls
    assert not output.with_suffix(".tmp").exists()


def test_master_index_failure_preserves_previous_output(tmp_path, monkeypatch) -> None:
    script = _script()
    output = tmp_path / "master.parquet"
    pd.DataFrame({"cik": [123]}).to_parquet(output)

    def fetch(client, year, quarter):
        if quarter == 2:
            raise RuntimeError("SEC unavailable")
        return pd.DataFrame({"cik": [456]})

    monkeypatch.setattr(script, "master_index", fetch)
    with pytest.raises(RuntimeError, match="SEC unavailable"):
        script.build(None, output, datetime(2011, 5, 1, tzinfo=UTC))
    assert pd.read_parquet(output)["cik"].tolist() == [123]
