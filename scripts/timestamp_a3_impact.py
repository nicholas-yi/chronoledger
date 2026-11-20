"""Post-report A3 impact: look-ahead direction under nominal and conservative calendars, F7 identity.

Declared before the A3 full report existed (after the pilot-only dry run):
- Population: universe rows whose accession has an A3 ``qualified_UTC``.
- For each stored source (``pair`` = the H0 knowledge time, ``bulk``), compare the first
  registered close after the stored time with the first close after the qualified time.
  ``stored_earlier_lookahead_risk`` means the stored time could trade before publication.
- Calendars: the frozen nominal 16:00 ET calendar, and a conservative variant that moves
  every possible early-close date (Jul 2-3, Dec 23-24, day after Thanksgiving) to 13:00 ET.
  An early close can hide look-ahead that the nominal calendar cannot see.
- F7: header identity classes for the CIK-disagreement pool, plus the count of universe
  CIK disagreements outside the audit roster (never fetched).
Reads only metadata (no prices, returns, signals or ledger) and writes one receipt.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from collections import Counter
from datetime import datetime, time

import run_full_timestamps as base

from asof.config import PROJECT_ROOT
from asof.filing_clock_basis import possible_early_close
from asof.ledger import file_sha256
from asof.runtime import frozen_receipt, write_receipt
from asof.timeutil import ET

REPORT = PROJECT_ROOT / "results" / "timestamp_full_a3_report.json"
TABLE = base.DATA_DIR / "timestamp_full_a3" / "qualified_per_accession.jsonl"
RECEIPT = PROJECT_ROOT / "results" / "timestamp_a3_impact.json"
SOURCES = ("scripts/timestamp_a3_impact.py", "tests/test_timestamp_a3_impact.py")


def conservative_closes(closes: list[datetime]) -> list[datetime]:
    """Move every possible early-close date to 13:00 ET; other closes unchanged."""
    output = []
    for close in closes:
        local = close.astimezone(ET)
        if possible_early_close(local.date()):
            close = datetime.combine(local.date(), time(13), tzinfo=ET).astimezone(close.tzinfo)
        output.append(close)
    return output


def direction(stored: datetime, qualified: datetime, closes: list[datetime]) -> str:
    a, b = bisect_right(closes, stored), bisect_right(closes, qualified)
    if a == len(closes) or b == len(closes):
        return "beyond_registered_calendar"
    return ("same_first_close" if a == b else
            "stored_earlier_lookahead_risk" if a < b else "stored_later_delay_only")


def impact(universe: list[dict], table: list[dict], closes: list[datetime]) -> dict:
    qualified = {r["accession"]: datetime.fromisoformat(r["qualified_UTC"])
                 for r in table if r["qualified_UTC"]}
    calendars = {"nominal_16_00": closes, "conservative_early_close_13_00": conservative_closes(closes)}
    output = {}
    for source in ("pair", "bulk"):
        counts = {name: Counter() for name in calendars}
        hidden = Counter()
        for row in universe:
            truth = qualified.get(row["accession"])
            if truth is None:
                continue
            stored = datetime.fromisoformat(row[f"{source}_time"])
            labels = {name: direction(stored, truth, cal) for name, cal in calendars.items()}
            for name, label in labels.items():
                counts[name][label] += 1
                counts[name]["stored_equals_qualified"] += stored == truth
            if labels["nominal_16_00"] != labels["conservative_early_close_13_00"]:
                hidden[f"{labels['nominal_16_00']}->{labels['conservative_early_close_13_00']}"] += 1
        output[f"stored_{source}"] = {**{k: dict(v) for k, v in counts.items()},
                                      "calendar_sensitive_changes": dict(hidden)}
    return output


def identity(universe: list[dict], table: list[dict]) -> dict:
    roster = {r["accession"] for r in table}
    pool = Counter(r["identity_class"] for r in table if r["pool"] == "CIK_disagreement")
    outside = {r["accession"] for r in universe if not r["CIKs_agree"] and r["accession"] not in roster}
    inside = {r["accession"] for r in universe if not r["CIKs_agree"] and r["accession"] in roster}
    return {"CIK_disagreement_pool_identity_classes": dict(pool),
            "universe_CIK_disagreement_accessions_in_audit": len(inside),
            "universe_CIK_disagreement_accessions_outside_audit_never_fetched": len(outside)}


def main() -> None:
    if RECEIPT.exists():
        raise RuntimeError("A3 impact already recorded; preserve it")
    freeze = frozen_receipt(PROJECT_ROOT, SOURCES)
    report = json.loads(REPORT.read_bytes())
    if file_sha256(TABLE) != report["private_hash_manifest"][str(TABLE.relative_to(PROJECT_ROOT))]:
        raise ValueError("qualified table differs from the A3 report manifest")
    table, universe = base.load_lines(TABLE), base.load_lines(base.UNIVERSE)
    calendar = json.loads(base.CALENDAR.read_bytes())
    closes = [datetime.fromisoformat(t) for t in calendar["closes"]]
    write_receipt(RECEIPT, {
        "scope": "Post-report A3 metadata impact; declared before the full A3 report existed",
        **freeze, "declared_rule": __doc__.split("Declared before")[1].strip(),
        "A3_report_SHA256": file_sha256(REPORT),
        "qualified_accessions": sum(bool(r["qualified_UTC"]) for r in table),
        "universe_rows": len(universe),
        "first_close_direction": impact(universe, table, closes),
        "F7_identity": identity(universe, table),
        "limits": "Nominal and conservative calendars are bounds, not a certified venue "
                  "calendar. Direction counts compare stored inputs with qualified times; they "
                  "are not signal, return or portfolio effects. No input was rewritten.",
    })
    print(RECEIPT.read_text())


if __name__ == "__main__":
    main()
