import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def _script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_finqa_years.py"
    spec = importlib.util.spec_from_file_location("check_finqa_years", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_documented_identity_field_is_read():
    script = _script()

    class OnlyIdentity(dict):
        def get(self, key, default=None):
            assert key == "id", "nonidentity field was inspected"
            return super().get(key, default)

        def items(self):
            pytest.fail("record fields were traversed")

        def values(self):
            pytest.fail("record values were traversed")

    records = [OnlyIdentity(id="AAA/2019/page_1.pdf-0", qa="not_to_be_read"),
               OnlyIdentity(id="BBB/2020/page_2.pdf-1", table="not_to_be_read")]
    assert script.identity_summary(records) == {
        "item_count": 2, "year_histogram": {"2019": 1, "2020": 1}, "nonmatching": 0}
    assert script.identity_summary([{"filename": "AAA/2019/page_1.pdf", "id": "unknown"}])[
        "nonmatching"] == 1  # undocumented alternative is not guessed


@pytest.mark.parametrize(("identity", "kept"), [
    ("AAA/2020/page_1.pdf-0", True), ("AAA/2021/page_1.pdf-0", False),
    ("AAA/2022/page_1.pdf-0", False), ("unparseable", False),
])
def test_unsafe_year_or_format_deletes_before_any_scoring(tmp_path, monkeypatch, identity, kept):
    script = _script()
    path = tmp_path / "quarantine.json"
    raw = json.dumps([{"id": identity, "qa": {"answer": "not_inspected"}}]).encode()
    path.write_bytes(raw)
    expected = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    monkeypatch.setattr(script, "EXPECTED_BLOB", expected)
    summary, safe = script.check_quarantine(path)
    assert safe is kept and path.exists() is kept
    assert set(summary) == {"item_count", "year_histogram", "nonmatching"}


def test_blob_mismatch_never_parses_and_deletes(tmp_path, monkeypatch):
    script = _script()
    path = tmp_path / "quarantine.json"
    path.write_bytes(b'{"question":"forbidden"}')
    monkeypatch.setattr(script.json, "loads", lambda _: pytest.fail("unverified bytes parsed"))
    summary, safe = script.check_quarantine(path)
    assert not safe and not path.exists() and summary["nonmatching"] == 1
