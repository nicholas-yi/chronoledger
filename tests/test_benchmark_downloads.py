import hashlib
import importlib.util
from pathlib import Path

import httpx
import pytest

from asof.document_scope import DocumentDates

SYNTHETIC_DATES = (DocumentDates("2017-02-01", "2017-02-01", "2016-12-31"),)


def _script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("benchmark_downloads", scripts / "benchmark_downloads.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_byte_integrity_before_any_parse_and_bad_download_cleanup(monkeypatch, tmp_path):
    script = _script(monkeypatch)
    raw = b"synthetic bytes"
    expected = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    client = httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, content=raw, headers={"content-type": "text/plain"})))
    with client:
        target = tmp_path / "file.json"
        result = script.fetch(
            client, "https://example.test/file", target, expected, documents=SYNTHETIC_DATES)
        assert result["sha256"] == hashlib.sha256(raw).hexdigest()
        assert target.read_bytes() == raw
        with pytest.raises(ValueError, match="blob"):
            script.fetch(client, "https://example.test/file", tmp_path / "bad.json", "0" * 40,
                         documents=SYNTHETIC_DATES)
        assert not (tmp_path / "bad.json").exists()
        assert not (tmp_path / "bad.json.part").exists()


def test_declared_and_actual_limits_are_enforced_without_install_or_login(monkeypatch, tmp_path):
    script = _script(monkeypatch)
    monkeypatch.setattr(script, "MAX_BYTES", 4)
    for headers in ({"content-length": "5"}, {"content-type": "text/html"}, {}):
        with (
            httpx.Client(transport=httpx.MockTransport(
                lambda _, h=headers: httpx.Response(200, content=b"12345", headers=h))) as client,
            pytest.raises(ValueError),
        ):
            script.fetch(client, "https://example.test/file", tmp_path / "bad", "0" * 40,
                         documents=SYNTHETIC_DATES)
    assert not (tmp_path / "bad").exists()
    assert not (tmp_path / "bad.part").exists()
