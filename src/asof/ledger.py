"""Locked append-only ledger with an anchored legacy prefix and chained new rows.

Autonomous agents generate many backtest variants. Every evaluation is logged here so the
Deflated Sharpe Ratio and PBO use the true number of trials. Entries are never edited or removed.
The first new row references the provided whole-file SHA256 of the 74 legacy rows;
those rows are not retroactively rewritten. Canonical row hashes detect edits, not
malicious recomputation of an unanchored tail. Locks serialize cooperating writers.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from asof.config import PROJECT_ROOT

LEDGER_PATH = PROJECT_ROOT / "results" / "trial_ledger.jsonl"
ANCHORED_LEDGER_PATH = LEDGER_PATH.resolve()
ANCHOR_PATH = PROJECT_ROOT / "results" / "trial_ledger_chain_anchor.json"
ALLOWED_PERIODS = {"development", "validation", "holdout"}


class LedgerIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class LedgerAnchor:
    prefix_bytes: int
    legacy_rows: int
    sha256: str


@dataclass(frozen=True)
class ChainVerification:
    legacy_rows: int
    chained_rows: int
    tip_hash: str
    anchor_sha256: str


def _anchor(path: Path, supplied: LedgerAnchor | None) -> LedgerAnchor:
    if supplied is not None:
        return supplied
    if path.resolve() == ANCHORED_LEDGER_PATH:
        data = json.loads(ANCHOR_PATH.read_text(encoding="utf-8"))
        return LedgerAnchor(data["prefix_bytes"], data["legacy_rows"], data["sha256"])
    return LedgerAnchor(0, 0, hashlib.sha256(b"").hexdigest())


def _row_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "row_hash"}
    return hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _verify(raw: bytes, anchor: LedgerAnchor) -> tuple[list[dict], ChainVerification]:
    if anchor.prefix_bytes < 0 or anchor.legacy_rows < 0 or len(anchor.sha256) != 64:
        raise LedgerIntegrityError("invalid anchor or truncated legacy prefix")
    physical_lines = raw.splitlines(keepends=True)
    if len(physical_lines) < anchor.legacy_rows:
        raise LedgerIntegrityError("truncated legacy prefix")
    prefix = b"".join(physical_lines[:anchor.legacy_rows])
    lf_prefix = prefix.replace(b"\r\n", b"\n")
    variants = (prefix, lf_prefix, lf_prefix.replace(b"\n", b"\r\n"))
    if not any(len(candidate) == anchor.prefix_bytes
               and hashlib.sha256(candidate).hexdigest() == anchor.sha256
               for candidate in variants):
        raise LedgerIntegrityError("legacy prefix differs from the committed anchor")
    if prefix and not prefix.endswith(b"\n"):
        raise LedgerIntegrityError("legacy anchor must end on a complete row")
    try:
        rows = [json.loads(line) for line in prefix.splitlines() if line]
        tail = raw[len(prefix):]
        if tail and not tail.endswith(b"\n"):
            raise LedgerIntegrityError("incomplete appended row; preserve evidence, do not auto-repair")
        chained = [json.loads(line) for line in tail.splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerIntegrityError("ledger contains an unreadable row") from exc
    if len(rows) != anchor.legacy_rows or any(not isinstance(row, dict) for row in rows):
        raise LedgerIntegrityError("legacy row count/schema differs from anchor")
    tip = anchor.sha256
    for row in chained:
        if (not isinstance(row, dict) or row.get("chain_version") != 1
                or row.get("previous_hash") != tip or row.get("row_hash") != _row_hash(row)):
            raise LedgerIntegrityError("appended row hash chain is invalid")
        tip = row["row_hash"]
    return rows + chained, ChainVerification(len(rows), len(chained), tip, anchor.sha256)


@contextmanager
def _locked(path: Path, *, append: bool) -> Iterator[Any]:
    if append:
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b" if append else "rb") as stream:
        deadline = time.monotonic() + 30
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("exclusive ledger lock timed out") from None
                time.sleep(0.05)
            except OSError as exc:
                if os.name != "nt" or exc.errno not in (13, 36):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError("exclusive ledger lock timed out") from exc
                time.sleep(0.05)
        try:
            yield stream
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def input_key(path: Path) -> str:
    resolved = (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        return Path(os.path.relpath(resolved, PROJECT_ROOT)).as_posix()
    except ValueError:
        return resolved.as_uri()


def config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def lineage(inputs: list[Path] | None = None) -> dict[str, Any]:
    """Code version and input fingerprints so every logged result is reproducible and auditable."""
    import subprocess

    def git(*args: str) -> str:
        r = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        return r.stdout.strip()

    fingerprints = {}
    statuses = {}
    for supplied in inputs or []:
        path = Path(supplied)
        path = PROJECT_ROOT / path if not path.is_absolute() else path
        key = input_key(path)
        present = path.is_file()
        fingerprints[key] = file_sha256(path) if present else None
        statuses[key] = "present" if present else "missing_or_not_regular_file"
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain", "--untracked-files=normal")),
        "inputs": fingerprints, "input_status": statuses,
        "missing_inputs": [key for key, value in fingerprints.items() if value is None],
        "environment": {
            "python": platform.python_version(),
            **{name: version(name) for name in (
                "duckdb", "pandas", "pyarrow", "httpx", "numpy", "scipy", "statsmodels", "lxml")},
        },
    }


def log_trial(
    hypothesis: str,
    config: dict[str, Any],
    period: str,
    metrics: dict[str, Any],
    path: Path = LEDGER_PATH,
    inputs: list[Path] | None = None,
    *, anchor: LedgerAnchor | None = None,
) -> str:
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"period must be one of {ALLOWED_PERIODS}")
    entry = {
        "logged_at": datetime.now(UTC).isoformat(),
        "hypothesis": hypothesis,
        "config_hash": config_hash(config),
        "config": config,
        "period": period,
        "metrics": metrics,
        "lineage": lineage(inputs),
    }
    path = Path(path)
    selected_anchor = _anchor(path, anchor)
    if selected_anchor.legacy_rows and not path.exists():
        raise LedgerIntegrityError("anchored ledger is missing; do not create a replacement")
    with _locked(path, append=True) as stream:
        stream.seek(0)
        rows, checked = _verify(stream.read(), selected_anchor)
        if period == "holdout" and any(
            e.get("period") == "holdout" and e.get("hypothesis") == hypothesis for e in rows
        ):
            raise PermissionError(f"holdout for {hypothesis} was already opened; it is single-use")
        entry.update(chain_version=1, previous_hash=checked.tip_hash)
        entry["row_hash"] = _row_hash(entry)
        stream.write((json.dumps(entry, sort_keys=True) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    return entry["config_hash"]


@contextmanager
def development_trial(
    hypothesis: str,
    config: dict[str, Any],
    *,
    inputs: list[Path] | None = None,
    path: Path = LEDGER_PATH,
) -> Iterator[dict[str, Any]]:
    """Log partial metrics even when development execution raises; never open a holdout."""
    metrics: dict[str, Any] = {}
    completed = False
    try:
        yield metrics
        completed = True
    finally:
        metrics["execution_status"] = "completed" if completed else "failed"
        log_trial(hypothesis, config, "development", metrics, path=path, inputs=inputs)


def read_ledger(
    path: Path = LEDGER_PATH, *, anchor: LedgerAnchor | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        if path.resolve() == ANCHORED_LEDGER_PATH:
            raise LedgerIntegrityError("anchored project ledger is missing")
        return []
    with _locked(path, append=False) as stream:
        stream.seek(0)
        rows, _ = _verify(stream.read(), _anchor(path, anchor))
    return rows


def verify_chain(
    path: Path = LEDGER_PATH, *, anchor: LedgerAnchor | None = None,
) -> ChainVerification:
    with _locked(path, append=False) as stream:
        stream.seek(0)
        _, checked = _verify(stream.read(), _anchor(path, anchor))
    return checked


def n_trials(hypothesis: str, path: Path = LEDGER_PATH) -> int:
    return len({e["config_hash"] for e in read_ledger(path) if e["hypothesis"] == hypothesis})
