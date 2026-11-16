"""Reparse only the pilot's pinned bytes after a duplicate-rendering parser regression."""

import copy
import gzip
import json
import time

from run_header_pilot import BUDGET, CONFIG, PRIVATE, REQUESTS, SOURCES, STATUS, summarize

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.filing_header_pilot import comparison, parse_header, parse_index

OUTPUT = PROJECT_ROOT / "results" / "header_pilot_reconciled.json"


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("offline reconciliation already recorded")
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit parser regression/replay source before offline reconciliation")
    original = json.loads(STATUS.read_text())
    receipt_hash, budget_hash = ledger.file_sha256(REQUESTS), ledger.file_sha256(BUDGET)
    rows = copy.deepcopy(original["items"])
    started = time.monotonic()
    parsed = 0
    for row in rows:
        for kind in ("header", "index"):
            resource = row[kind]
            provenance = resource.get("provenance")
            if provenance is None:
                continue
            if provenance["cache_hit"]:
                path = DATA_DIR / provenance["path"]
                if ledger.file_sha256(path) != provenance["SHA256"]:
                    raise ValueError("pinned cached metadata changed")
                with gzip.open(path, "rb") as stream:
                    raw = stream.read(65536)
            else:
                request = provenance["request"]
                if not request["body_complete"]:
                    raise ValueError("partial body must remain unknown")
                path = PRIVATE / request["cache_file"]
                if ledger.file_sha256(path) != request["SHA256_observed_bytes"]:
                    raise ValueError("pilot raw metadata changed")
                raw = path.read_bytes()
            if len(raw) >= 65536:
                raise ValueError("oversized metadata must remain unknown")
            value = parse_header(raw, row["accession"]) if kind == "header" else parse_index(raw)
            row[kind] = {**value, "URL": resource["URL"], "provenance": provenance}
            parsed += 1
        row["comparison"] = comparison(row, row["header"], row["index"])
    if ledger.file_sha256(BUDGET) != budget_hash or ledger.file_sha256(REQUESTS) != receipt_hash:
        raise ValueError("offline reconciliation altered request history")
    output = {
        "kind": "OFFLINE PARSER CORRECTION ONLY, not a new acquisition or data repair",
        "change": "After observing duplicate SGML/rendered field copies, deduplicate identical "
                  "acceptance values. Conflicting distinct values still unknown; strict14digits/"
                  "civil-clock validation unchanged. Synthetic regression failed before fix.",
        "decision_timing": "After initial all-unknown pilot parse; formatting-only, before "
                           "conditional source-offset results from this corrected parse.",
        "original_status_SHA256": ledger.file_sha256(STATUS),
        "roster_config_SHA256": ledger.file_sha256(CONFIG),
        "request_receipt_SHA256": receipt_hash,
        "source_SHA256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p)
                         for p in [*SOURCES, PROJECT_ROOT / "scripts" / "reconcile_header_pilot.py"]},
        "items": rows, "pool_summary": summarize(rows), "resources_parsed": parsed,
        "new_HTTP_attempts": 0, "counter": json.loads(BUDGET.read_text()),
        "wall_seconds": time.monotonic() - started,
        "assumption": "Header is Eastern wall time; Stage1 did not define its clock. "
                      "Stored API/pair and bulk representations compared conditionally only.",
        "timestamp_repairs": 0, "CIK_remaps": 0, "P0": "BLOCKED",
        "limit": "Six stratified8-item pools cannot certify the cohort or estimate an unweighted "
                 "population error rate. No source promotion, assignment or financial rerun.",
    }
    OUTPUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"parsed_resources": parsed, "new_requests": 0,
                      "counter": output["counter"], "pools": output["pool_summary"]}, indent=2))


if __name__ == "__main__":
    main()
