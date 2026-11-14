"""Quarantine check: inspect documented report IDs only, never question or gold fields."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from asof.config import DATA_DIR

EXPECTED_BLOB = "970f239f591c782b17df420c0d343b780737f3da"
QUARANTINE = DATA_DIR / "bench_1" / "quarantine" / "finqa_dev.json"
SUMMARY = DATA_DIR / "bench_1" / "finqa_years.json"
MAX_BYTES = 50_000_000
# Pinned README: report name plus example index, e.g. ETR/2016/page_23.pdf-2.
REPORT_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]*/([0-9]{4})/page_[0-9]+\.pdf-[0-9]+")


def identity_summary(records: object) -> dict:
    years: Counter[int] = Counter()
    nonmatching = 0
    if not isinstance(records, list) or not records:
        return {"item_count": 0, "year_histogram": {}, "nonmatching": 1}
    for record in records:
        # No traversal/items/values or access to any field other than documented `id`.
        identity = record.get("id") if isinstance(record, dict) else None
        match = REPORT_ID.fullmatch(identity) if isinstance(identity, str) else None
        if match is None or int(match.group(1)) == 0:
            nonmatching += 1
        else:
            years[int(match.group(1))] += 1
    return {"item_count": len(records),
            "year_histogram": {str(y): n for y, n in sorted(years.items())},
            "nonmatching": nonmatching}


def check_quarantine(path: Path) -> tuple[dict, bool]:
    if path.stat().st_size > MAX_BYTES:
        path.unlink()
        return {"item_count": 0, "year_histogram": {}, "nonmatching": 1}, False
    raw = path.read_bytes()
    blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if blob != EXPECTED_BLOB:
        path.unlink()
        return {"item_count": 0, "year_histogram": {}, "nonmatching": 1}, False
    try:
        records = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        path.unlink()
        return {"item_count": 0, "year_histogram": {}, "nonmatching": 1}, False
    summary = identity_summary(records)
    safe = (summary["item_count"] > 0 and summary["nonmatching"] == 0
            and all(int(year) <= 2020 for year in summary["year_histogram"]))
    if not safe:
        path.unlink()
    return summary, safe


def main() -> int:
    summary, safe = check_quarantine(QUARANTINE)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return 0 if safe else 2


if __name__ == "__main__":
    raise SystemExit(main())
