"""Append-only trial ledger.

Autonomous agents generate many backtest variants. Every evaluation is logged here so the
Deflated Sharpe Ratio and PBO use the true number of trials. Entries are never edited or removed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asof.config import PROJECT_ROOT

LEDGER_PATH = PROJECT_ROOT / "results" / "trial_ledger.jsonl"
ALLOWED_PERIODS = {"development", "validation", "holdout"}


def config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def log_trial(
    hypothesis: str,
    config: dict[str, Any],
    period: str,
    metrics: dict[str, float],
    path: Path = LEDGER_PATH,
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
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry["config_hash"]


def read_ledger(path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def n_trials(hypothesis: str, path: Path = LEDGER_PATH) -> int:
    return len({e["config_hash"] for e in read_ledger(path) if e["hypothesis"] == hypothesis})
