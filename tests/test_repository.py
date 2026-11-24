import json
from pathlib import Path

from asof.repository import check_repository


def fixture(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.py").write_text("")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "opaque.json").write_text("NOT JSON: evidence must never be decoded")
    (tmp_path / "results" / "linked.json").write_text("NOT JSON either")
    (tmp_path / "README.md").write_text("[guide](docs/guide.md#not-checked)\n[ref][r]\n"
                                      "[r]: <docs/with space.md>\n"
                                      "[run](results/linked.json)\n"
                                      "```\n[example](does-not-exist)\n```\n")
    (docs / "guide.md").write_text("[readme](../README.md)\n[web](https://example.test/a)\n")
    (docs / "with space.md").write_text("# Invented guide\n")
    (docs / "project_index.json").write_text(json.dumps({
        "schema_version": 2,
        "entrypoints": [{"path": "scripts/run.py", "status": "pipeline", "purpose": "invented",
                         "command": "python scripts/run.py"}],
        "evidence": [{"path": "results/opaque.json", "report": "docs/guide.md",
                      "status": "current", "freeze_revision": None}],
    }))


def test_link_check_never_decodes_results_and_handles_spaces(tmp_path, monkeypatch):
    fixture(tmp_path)
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.parent.name != "results"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert check_repository(tmp_path) == ()


def test_missing_escaping_and_unsafe_held_commands_are_explicit(tmp_path):
    fixture(tmp_path)
    (tmp_path / "docs" / "guide.md").write_text("[gone](missing.md)\n[escape](../../outside.md)")
    path = tmp_path / "docs" / "project_index.json"
    index = json.loads(path.read_text())
    index["entrypoints"][0].update(status="held")
    path.write_text(json.dumps(index))
    errors = check_repository(tmp_path)
    assert any("missing link missing.md" in error for error in errors)
    assert any("escapes repository" in error for error in errors)
    assert any("must not advertise" in error for error in errors)


def test_orphaned_scripts_results_and_free_text_statuses_are_rejected(tmp_path):
    fixture(tmp_path)
    (tmp_path / "scripts" / "one_off.py").write_text("")
    (tmp_path / "results" / "forgotten.json").write_text("{}")
    path = tmp_path / "docs" / "project_index.json"
    index = json.loads(path.read_text())
    index["evidence"][0]["status"] = "historical_complete_17of24_not_promoted"
    path.write_text(json.dumps(index))
    errors = check_repository(tmp_path)
    assert "unindexed script scripts/one_off.py" in errors
    assert "orphaned result results/forgotten.json" in errors
    assert any("status must be one of" in error for error in errors)
