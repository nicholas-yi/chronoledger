"""One offline assurance receipt for source-claim-v2; no model, raw-source or outcome-data reads."""

import hashlib
import json
import time
from pathlib import Path

from asof.claim_assurance import controls, evaluate
from asof.reader_regression import regression_matrix
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "src/asof/claim_assurance.py", "src/asof/claim_verifier.py", "src/asof/claim_challenge.py",
    "src/asof/reader_fields.py", "src/asof/linked_reader.py", "src/asof/reader_regression.py",
    "src/asof/runtime.py", "src/asof/focused_reader.py", "src/asof/reader_reliability.py",
    "src/asof/reader_cells.py", "src/asof/reader_field_challenge.py", "src/asof/reader_stress.py",
    "src/asof/verified_reader.py", "src/asof/extraction.py",
    "scripts/validate_claim_assurance.py", "tests/test_claim_verifier.py",
    "tests/fixtures/focused_reader.json", "tests/fixtures/verified_reader.json",
    "tests/fixtures/reader_stress.json", "tests/fixtures/linked_challenge.json",
    "tests/fixtures/reader_fields.json", "tests/fixtures/reader_reliability.json",
    "results/hhem_structured.json", "results/hhem_benchmark.json", "results/reader_ai_review.json",
    "docs/FOCUSED_READER.md",
)


def main():
    destination = ROOT / "results" / "claim_assurance.json"
    if destination.exists():
        raise FileExistsError("assurancereceiptexists;do not overwrite")
    lineage = frozen_receipt(ROOT, SOURCES)
    started = time.monotonic()
    result = evaluate()
    result["current_reader_regressions"] = regression_matrix(ROOT)
    result["lineage"] = lineage
    result["controls_sha256"] = hashlib.sha256(json.dumps(controls(), sort_keys=True).encode()).hexdigest()
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    result["source_unchanged"] = all(
        hashlib.sha256(ROOT.joinpath(*name.split("/")).read_bytes()).hexdigest() == digest
        for name, digest in lineage["source_SHA256"].items())
    result["resource_check_passed"] = result["wall_seconds"] < 30 and result["process_peak_RSS_bytes"] < (512 << 20)
    result["checks_passed"] = (
        result["policy_controls"]["correct"] == result["policy_controls"]["planned"]
        and all(row["correct"] == row["planned"] for row in result["current_reader_regressions"]["cohorts"].values())
        and result["source_unchanged"] and result["resource_check_passed"])
    write_receipt(destination, result)
    print(json.dumps({
        "status": result["status"], "checks_passed": result["checks_passed"],
        "policy_controls": {key: value for key, value in result["policy_controls"].items() if key != "records"},
        "supported_challenge_correct": result["current_supported_challenge"]["correct"],
        "overall_30_case_coverage": result["overall_30_case_coverage"],
        "wall_seconds": result["wall_seconds"], "model_calls": 0,
    }, indent=2))
    return 0 if result["checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
