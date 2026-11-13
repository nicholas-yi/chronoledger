"""Append-only trial ledger.

Autonomous agents generate many backtest variants. Every evaluation is logged here so the
Deflated Sharpe Ratio and PBO use the true number of trials. Entries are never edited or removed.
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from asof.config import PROJECT_ROOT

LEDGER_PATH = PROJECT_ROOT / "results" / "trial_ledger.jsonl"
ALLOWED_PERIODS = {"development", "validation", "holdout"}


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
        r = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""

    return {
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain", "--", "src", "scripts")),
        "inputs": {str(Path(p).name): file_sha256(p) for p in (inputs or []) if Path(p).exists()},
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
) -> str:
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"period must be one of {ALLOWED_PERIODS}")
    if period == "holdout" and any(
        e["period"] == "holdout" and e["hypothesis"] == hypothesis for e in read_ledger(path)
    ):
        raise PermissionError(f"holdout for {hypothesis} was already opened; it is single-use")
    entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": hypothesis,
        "config_hash": config_hash(config),
        "config": config,
        "period": period,
        "metrics": metrics,
        "lineage": lineage(inputs),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
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


def read_ledger(path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def n_trials(hypothesis: str, path: Path = LEDGER_PATH) -> int:
    return len({e["config_hash"] for e in read_ledger(path) if e["hypothesis"] == hypothesis})
