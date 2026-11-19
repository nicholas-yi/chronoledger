import json
from pathlib import Path

from asof.repository import check_repository


def fixture(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text("[guide](docs/guide.md#not-checked)\n[ref][r]\n"
                                      "[r]: <docs/with space.md>\n"
                                      "```\n[example](does-not-exist)\n```\n")
    (docs / "guide.md").write_text("[readme](../README.md)\n[web](https://example.test/a)\n")
    (docs / "with space.md").write_text("# Invented guide\n")
    (docs / "project_index.json").write_text(json.dumps({
        "schema_version": 1, "entrypoints": [{"id": "guide", "path": "README.md",
                                            "status": "active_offline", "command": "invented"}],
        "evidence": [{"id": "invented", "path": "opaque.json", "report": "docs/guide.md",
                      "freeze_revision": None, "supersedes": []}],
    }))
    (tmp_path / "opaque.json").write_text("NOT JSON: this evidence must never be decoded")


def test_link_check_never_decodes_referenced_result_and_handles_spaces(tmp_path, monkeypatch):
    fixture(tmp_path)
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.name != "opaque.json"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert check_repository(tmp_path) == ()


def test_missing_escaping_and_unsafe_held_commands_are_explicit(tmp_path):
    fixture(tmp_path)
    (tmp_path / "docs" / "guide.md").write_text("[gone](missing.md)\n[escape](../../outside.md)")
    path = tmp_path / "docs" / "project_index.json"
    index = json.loads(path.read_text())
    index["entrypoints"][0].update(status="hard_held", command="run")
    path.write_text(json.dumps(index))
    errors = check_repository(tmp_path)
    assert any("missing link missing.md" in error for error in errors)
    assert any("escapes repository" in error for error in errors)
    assert any("must not advertise" in error for error in errors)
