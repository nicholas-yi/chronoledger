import gzip
import importlib.util
from pathlib import Path

import httpx

from asof.edgar import response_cache_path


def _script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("audit_cached_timestamps", scripts / "audit_cached_timestamps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cached_audit_never_constructs_network_client_and_preserves_missing(monkeypatch, tmp_path):
    module = _script(monkeypatch)
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    missing = module.cached_evidence(1, "0000000001-20-000001", tmp_path)
    assert missing == {"header_cached": False, "index_cached": False, "assets": []}


def test_cached_fields_match_own_index_without_promoting_clock_authority(monkeypatch, tmp_path):
    module = _script(monkeypatch)
    acc = "0000000001-20-000001"
    base = f"https://www.sec.gov/Archives/edgar/data/1/{acc.replace('-', '')}/{acc}"
    fixtures = {
        "-index-headers.html": "<ACCEPTANCE-DATETIME>20200102163000\nCENTRAL INDEX KEY: 0000000001",
        "-index.html": 'Accepted</div><div>2020-01-02 16:30:00',
    }
    for suffix, text in fixtures.items():
        path = response_cache_path(base + suffix, tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(text.encode()))
    result = module.cached_evidence(1, acc, tmp_path)
    assert result["header_index_wall_match"] is True
    assert result["UTC_if_header_ET"] == "2020-01-02T21:30:00+00:00"
    assert len(result["assets"]) == 2


def test_ambiguous_cached_clock_is_explicit_not_a_chosen_UTC(monkeypatch, tmp_path):
    module = _script(monkeypatch)
    acc = "0000000001-20-000001"
    url = f"https://www.sec.gov/Archives/edgar/data/1/{acc.replace('-', '')}/{acc}-index-headers.html"
    path = response_cache_path(url, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(gzip.compress(b"<ACCEPTANCE-DATETIME>20241103013000"))
    result = module.cached_evidence(1, acc, tmp_path)
    assert result["UTC_if_header_ET"] is None
    assert "ambiguous" in result["header_clock_issue"]
