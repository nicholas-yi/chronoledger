"""One-shot record of separately authored adversarial notation cases against the frozen verifier."""

import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from asof.claim_verifier import verify_claim
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/notation_adversarial.json"
SOURCES = (FIXTURE, "scripts/validate_notation_adversarial.py", "src/asof/financial_notation.py",
           "src/asof/claim_verifier.py", "src/asof/reader_fields.py", "src/asof/linked_reader.py",
           "src/asof/reader_reliability.py", "src/asof/runtime.py", "results/notation_baseline.json")


def load(path: Path) -> list[dict]:
    rows = json.loads(path.read_bytes())
    if (len(rows) != 72 or len({row["id"] for row in rows}) != 72
            or any(row["expected_verdict"] not in ("supported", "contradicted", "review") for row in rows)
            or any(len(row["source"]) > 600 for row in rows)):
        raise ValueError("adversarial fixture violates its declared shape")
    return rows


def main():
    destination = ROOT / "results" / "notation_adversarial.json"
    if destination.exists():
        raise FileExistsError("adversarial receipt exists; never overwrite or retry")
    lineage = frozen_receipt(ROOT, SOURCES)
    cases = load(ROOT / FIXTURE)
    started = time.monotonic()
    rows = []
    for case in cases:
        decision = verify_claim(case["source"], case["claim"])
        rows.append({"id": case["id"], "attack": case["attack"], "expected_verdict": case["expected_verdict"],
                     "verdict": decision["verdict"], "reason": decision["reason"],
                     "proof_valid": decision["proof_valid"],
                     "correct": decision["verdict"] == case["expected_verdict"]})
    result = {
        "status": "complete_one_shot_adversarial_record",
        "planned": len(rows), "correct": sum(row["correct"] for row in rows),
        "expected": dict(Counter(row["expected_verdict"] for row in rows)),
        "verdicts": dict(Counter(row["verdict"] for row in rows)),
        "false_support": sum(row["verdict"] == "supported" and row["expected_verdict"] != "supported"
                             for row in rows),
        "false_contradiction": sum(row["verdict"] == "contradicted" and row["expected_verdict"] != "contradicted"
                                   for row in rows),
        "missed_resolution": sum(row["verdict"] == "review" and row["expected_verdict"] != "review"
                                 for row in rows),
        "resolved_without_valid_proof": sum(row["verdict"] != "review" and not row["proof_valid"]
                                            for row in rows),
        "disagreements": [row for row in rows if not row["correct"]], "rows": rows,
        "fixture_sha256": hashlib.sha256((ROOT / FIXTURE).read_bytes()).hexdigest(),
        "authorship": ("Separate AI agent instance given only the written financial-notation-v1 policy and "
                       "claim grammar, instructed not to read repository code; not human, not gold."),
        "verifier_frozen_before_fixture_was_read": True,
        "disagreement_is_not_automatically_verifier_error": True,
        "lineage": lineage, "independent_human_gold": False, "model_calls": 0,
    }
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    write_receipt(destination, result)
    print(json.dumps({key: value for key, value in result.items() if key not in ("rows", "lineage")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
