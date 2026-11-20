"""Record the frozen notation challenge before (baseline) and after implementation; never overwrite."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from asof.notation_challenge import evaluate, fixture, grid
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCES = (
    "src/asof/notation_challenge.py", "scripts/validate_notation.py", "src/asof/claim_verifier.py",
    "src/asof/reader_fields.py", "src/asof/linked_reader.py", "src/asof/reader_reliability.py",
    "src/asof/runtime.py",
)
FINAL_SOURCES = (
    "results/notation_baseline.json", "src/asof/financial_notation.py",
    "tests/test_financial_notation.py", "src/asof/claim_assurance.py", "src/asof/claim_challenge.py",
    "src/asof/reader_regression.py", "results/claim_assurance.json",
)


def digest(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def summary(block: dict) -> dict:
    return {key: value for key, value in block.items() if key not in ("rows", "errors", "by_relation")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("baseline", "final"), required=True)
    args = parser.parse_args(argv)
    destination = ROOT / "results" / f"notation_{args.phase}.json"
    if destination.exists():
        raise FileExistsError("notation receipt exists; never overwrite or retry")
    lineage = frozen_receipt(ROOT, BASE_SOURCES if args.phase == "baseline" else (*BASE_SOURCES, *FINAL_SOURCES))
    started = time.monotonic()
    result = {"phase": args.phase, **evaluate(), "lineage": lineage,
              "fixture_sha256": digest(fixture()), "grid_sha256": digest(grid()),
              "author_visible_not_blind": True, "independent_gold": False, "model_calls": 0}
    if args.phase == "final":
        from asof.claim_assurance import evaluate as assurance
        from asof.reader_regression import regression_matrix

        baseline = json.loads((ROOT / "results" / "notation_baseline.json").read_bytes())
        if (baseline["fixture_sha256"], baseline["grid_sha256"]) != (result["fixture_sha256"], result["grid_sha256"]):
            raise ValueError("challenge or grid changed after its frozen baseline")
        result["baseline"] = {"challenge": summary(baseline["challenge"]), "grid": summary(baseline["grid"])}
        current = assurance()
        result["exposed_original_30"] = current["overall_30_case_coverage"]
        result["exposed_policy_controls"] = {key: value for key, value in current["policy_controls"].items()
                                             if key != "records"}
        result["exposed_supported_24"] = current["current_supported_challenge"]["correct"]
        result["current_reader_regressions"] = regression_matrix(ROOT)
        result["checks_passed"] = (
            result["exposed_policy_controls"]["correct"] == result["exposed_policy_controls"]["planned"]
            and all(row["correct"] == row["planned"]
                    for row in result["current_reader_regressions"]["cohorts"].values()))
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    write_receipt(destination, result)
    printed = {"challenge": summary(result["challenge"]), "grid": summary(result["grid"])}
    if args.phase == "final":
        printed.update(exposed_original_30=result["exposed_original_30"],
                       exposed_policy_controls=result["exposed_policy_controls"],
                       checks_passed=result["checks_passed"])
    print(json.dumps(printed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
