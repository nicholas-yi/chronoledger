import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("project_gap_checks",
                                                 scripts / "check_project_gaps.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_official_link_discovery_cannot_authorize_filings_or_external_hosts(monkeypatch):
    m = module(monkeypatch)
    raw = (b'<a href="/files/edgar/manual.pdf">manual</a>'
           b'<a href="/Archives/edgar/data/123/file.txt">filing</a>'
           b'<a href="https://elsewhere.invalid/spec.pdf">external</a>')
    assert m.official_links(raw, "https://www.sec.gov/example") == [
        "https://www.sec.gov/files/edgar/manual.pdf"]
    assert not m.official_url("https://www.sec.gov:443/files/a.pdf")
    assert not m.official_url("https://www.sec.gov/files/a.pdf?fetch=other")


def test_document_followup_must_be_an_observed_official_link(tmp_path, monkeypatch):
    m = module(monkeypatch)
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"actual_HTTP_attempts": 3248, "ceiling": 34402}))
    monkeypatch.setattr(m.common, "BUDGET", budget)
    report = tmp_path / "prior.json"
    report.write_text(json.dumps({"status": "retrieved_requires_review", "documents": [{"official_links": [
        "https://www.sec.gov/files/edgar/manual.pdf"]}]}))
    args = SimpleNamespace(config=tmp_path / "new.json", check="clock",
                           from_report=report, url=["https://www.sec.gov/files/guessed.pdf"])
    with pytest.raises(ValueError, match="observed links"):
        m.freeze(args)
    assert not args.config.exists()


def test_cleanup_targets_verified_creation_time_and_children_first(monkeypatch):
    m = module(monkeypatch)
    commands = []

    class Process:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def create(*args, **kwargs):
        commands.append(args[-1])
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    asyncio.run(m.stop_owned([
        {"pid": 300, "parent_pid": 1, "creation_filetime": 900},
        {"pid": 100, "parent_pid": 300, "creation_filetime": 901},
    ]))
    assert "Stop-Process -Id 100" in commands[0] and " -ne 901" in commands[0]
    assert "Stop-Process -Id 300" in commands[1] and " -ne 900" in commands[1]
