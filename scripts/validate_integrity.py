"""Record the frozen source-integrity challenge before (baseline) and after the guards; never overwrite."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from asof.integrity_challenge import cases, evaluate
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCES = (
    "src/asof/integrity_challenge.py", "scripts/validate_integrity.py", "src/asof/claim_verifier.py",
    "src/asof/financial_notation.py", "src/asof/reader_fields.py", "src/asof/linked_reader.py",
    "src/asof/reader_reliability.py", "src/asof/runtime.py",
)
FINAL_SOURCES = (
    "results/integrity_baseline.json", "tests/test_financial_notation.py", "tests/test_claim_verifier.py",
    "src/asof/claim_assurance.py", "src/asof/claim_challenge.py", "src/asof/notation_challenge.py",
    "src/asof/reader_regression.py", "tests/fixtures/notation_adversarial.json",
)


def summary(block: dict) -> dict:
    return {key: value for key, value in block.items() if key not in ("rows", "errors", "by_relation", "records")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("baseline", "final"), required=True)
    args = parser.parse_args(argv)
    destination = ROOT / "results" / f"integrity_{args.phase}.json"
    if destination.exists():
        raise FileExistsError("integrity receipt exists; never overwrite or retry")
    lineage = frozen_receipt(ROOT, BASE_SOURCES if args.phase == "baseline" else (*BASE_SOURCES, *FINAL_SOURCES))
    started = time.monotonic()
    result = {"phase": args.phase, "challenge": evaluate(), "lineage": lineage,
              "cases_sha256": hashlib.sha256(json.dumps(cases(), sort_keys=True).encode()).hexdigest(),
              "author_visible_not_blind": True, "independent_gold": False, "model_calls": 0}
    if args.phase == "final":
        from asof.claim_assurance import evaluate as assurance
        from asof.claim_verifier import verify_claim
        from asof.notation_challenge import evaluate as notation
        from asof.reader_regression import regression_matrix

        baseline = json.loads((ROOT / "results" / "integrity_baseline.json").read_bytes())
        if baseline["cases_sha256"] != result["cases_sha256"]:
            raise ValueError("integrity challenge changed after its frozen baseline")
        result["baseline"] = summary(baseline["challenge"])
        current = assurance()
        frozen = notation()
        adversarial = json.loads((ROOT / "tests" / "fixtures" / "notation_adversarial.json").read_bytes())
        result["exposed"] = {
            "original_30": current["overall_30_case_coverage"],
            "policy_controls": summary(current["policy_controls"]),
            "supported_24": current["current_supported_challenge"]["correct"],
            "notation_challenge": summary(frozen["challenge"]), "notation_grid": summary(frozen["grid"]),
            "notation_adversarial_round1_regression": sum(
                verify_claim(row["source"], row["claim"])["verdict"] == row["expected_verdict"]
                for row in adversarial),
            "reader_regressions": regression_matrix(ROOT),
        }
        exposed = result["exposed"]
        result["checks_passed"] = (
            exposed["policy_controls"]["correct"] == exposed["policy_controls"]["planned"]
            and exposed["original_30"]["correct_including_unresolved_as_misses"] == 30
            and exposed["notation_challenge"]["correct"] == 24 and exposed["notation_grid"]["correct"] == 780
            and exposed["notation_adversarial_round1_regression"] == 72
            and all(row["correct"] == row["planned"] for row in exposed["reader_regressions"]["cohorts"].values()))
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    write_receipt(destination, result)
    printed = {"challenge": summary(result["challenge"]),
               "by_relation": {k: f"{v['correct']}/{v['planned']}" for k, v in result["challenge"]["by_relation"].items()}}
    if args.phase == "final":
        printed["checks_passed"] = result["checks_passed"]
        printed["exposed"] = {k: v if not isinstance(v, dict) else summary(v)
                              for k, v in result["exposed"].items() if k != "reader_regressions"}
    print(json.dumps(printed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
