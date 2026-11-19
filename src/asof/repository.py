"""Read-only source-documentation/index checks; result/data payloads are never decoded."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def _local(root: Path, parent: Path, link: str) -> Path:
    target = (parent / unquote(link)).resolve()
    if not target.is_relative_to(root):
        raise ValueError("local link escapes repository")
    return target


def check_repository(root: Path) -> tuple[str, ...]:
    """Check index structure and local Markdown target existence, not external URLs/anchors.

    Only README, docs/*.md (recursively) and the navigation JSON are read. A referenced
    result or private path is checked for existence, not opened or fingerprinted.
    """
    root = root.resolve()
    errors = []
    index_path = root / "docs" / "project_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema_version") != 1:
        errors.append("project_index.json: expected schema_version=1")
    for section in ("entrypoints", "evidence"):
        ids = set()
        for item in index[section]:
            identity = item["id"]
            if identity in ids:
                errors.append(f"{section}: duplicate id {identity}")
            ids.add(identity)
            for key in ("path", "report") if section == "evidence" else ("path",):
                try:
                    target = _local(root, root, item[key])
                except ValueError as exc:
                    errors.append(f"{identity}: {exc}")
                    continue
                if not target.is_file():
                    errors.append(f"{identity}: missing {key} {item[key]}")
            if section == "evidence":
                revision = item["freeze_revision"]
                if revision is not None and re.fullmatch(r"[a-f0-9]{7,40}", revision) is None:
                    errors.append(f"{identity}: malformed freeze revision")
            elif (item["status"] in ("hard_held", "retired_historical")
                  or item["status"].startswith("historical_")) and item["command"] is not None:
                errors.append(f"{identity}: held/historical entry must not advertise a run command")
    evidence_ids = {item["id"] for item in index["evidence"]}
    for item in index["evidence"]:
        if any(other not in evidence_ids or other == item["id"] for other in item["supersedes"]):
            errors.append(f"{item['id']}: invalid supersession target")
    documents = [root / "README.md", *sorted((root / "docs").rglob("*.md"))]
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
            if not target.exists():
                errors.append(f"{document.relative_to(root)}: missing link {link}")
    return tuple(errors)
