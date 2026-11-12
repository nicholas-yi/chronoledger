"""Project-wide configuration."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("ASOF_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("ASOF_DB_PATH", DATA_DIR / "asof.duckdb"))


def user_agent() -> str:
    """SEC requires a declared User-Agent with contact information."""
    ua = os.environ.get("ASOF_USER_AGENT")
    if not ua:
        raise RuntimeError(
            "Set ASOF_USER_AGENT, e.g. 'Your Name your.email@example.com' (required by SEC EDGAR)."
        )
    return ua
