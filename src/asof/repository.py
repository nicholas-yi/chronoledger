"""Read-only documentation/index checks; result/data payloads are never decoded."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ENTRYPOINT_STATUSES = {"pipeline", "held", "maintenance", "reader"}
EVIDENCE_STATUSES = {"current", "superseded"}


def _local(root: Path, parent: Path, link: str) -> Path:
    target = (parent / unquote(link)).resolve()
    if not target.is_relative_to(root):
        raise ValueError("local link escapes repository")
    return target


def _doc_links(root: Path, documents: list[Path], errors: list[str]) -> set[Path]:
    """Check local Markdown targets and return the files they reference."""
    targets = set()
    for document in documents:
        content = document.read_text(encoding="utf-8")
        # Ignore fenced code so illustrative Markdown/path syntax is not treated as navigation.
        content = re.sub(r"(?ms)^```.*?^```[^\n]*", "", content)
        inline = re.findall(r"\]\((<[^>\n]+>|[^\s)\n]+)(?:\s+\"[^\"]*\")?\)", content)
        references = re.findall(r"(?m)^\[[^\]\n]+\]:\s*(<[^>\n]+>|[^\s]+)", content)
        for raw in (*inline, *references):
            link = raw.removeprefix("<").removesuffix(">")
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            try:
                target = _local(root, document.parent, parsed.path)
            except ValueError as exc:
                errors.append(f"{document.relative_to(root)}: {exc}: {link}")
                continue
            if target.exists():
                targets.add(target)
            else:
                errors.append(f"{document.relative_to(root)}: missing link {link}")
    return targets


def check_repository(root: Path) -> tuple[str, ...]:
    """Check the navigation index and local Markdown links, and flag orphaned scripts/results.

    Only README, docs/*.md (recursively) and the index JSON are read. Result files are checked
    for existence and for being referenced, never opened.
    """
    root = root.resolve()
    errors: list[str] = []
    index = json.loads((root / "docs" / "project_index.json").read_text(encoding="utf-8"))
    if index.get("schema_version") != 2:
        errors.append("project_index.json: expected schema_version=2")
    indexed: set[Path] = set()
    for section, statuses in (("entrypoints", ENTRYPOINT_STATUSES), ("evidence", EVIDENCE_STATUSES)):
        seen = set()
        for item in index[section]:
            path = item["path"]
            if path in seen:
                errors.append(f"{section}: duplicate path {path}")
            seen.add(path)
            if item["status"] not in statuses:
                errors.append(f"{path}: status must be one of {sorted(statuses)}")
            for key in ("path", "report") if section == "evidence" else ("path",):
                try:
                    target = _local(root, root, item[key])
                except ValueError as exc:
                    errors.append(f"{path}: {exc}")
                    continue
                if not target.is_file():
                    errors.append(f"{path}: missing {key} {item[key]}")
                indexed.add(target)
            if section == "evidence":
                revision = item["freeze_revision"]
                if revision is not None and re.fullmatch(r"[a-f0-9]{7,40}", revision) is None:
                    errors.append(f"{path}: malformed freeze revision")
            elif item["status"] == "held" and item["command"] is not None:
                errors.append(f"{path}: held entry must not advertise a run command")
    documents = [root / "README.md", *sorted((root / "docs").rglob("*.md"))]
    linked = _doc_links(root, documents, errors)
    for script in sorted((root / "scripts").glob("*.py")) if (root / "scripts").is_dir() else ():
        if script.resolve() not in indexed:
            errors.append(f"unindexed script {script.relative_to(root).as_posix()}")
    results = root / "results"
    for result in sorted(p for p in results.rglob("*") if p.is_file()) if results.is_dir() else ():
        if result.resolve() not in indexed | linked:
            errors.append(f"orphaned result {result.relative_to(root).as_posix()}")
    return tuple(errors)
