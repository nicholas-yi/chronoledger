"""One-shot record of separately authored adversarial notation cases against the frozen verifier."""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from asof.claim_verifier import verify_claim
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = {
    1: ("notation_adversarial", 72, "financial-notation-v1"),
    2: ("notation_adversarial_r2", 96, "financial-notation-v2 (v1 plus dispute, modal and text-integrity guards)"),
}
COMMON = ("scripts/validate_notation_adversarial.py", "src/asof/financial_notation.py",
          "src/asof/claim_verifier.py", "src/asof/reader_fields.py", "src/asof/linked_reader.py",
          "src/asof/reader_reliability.py", "src/asof/runtime.py", "results/notation_baseline.json")


def load(path: Path, count: int) -> list[dict]:
    rows = json.loads(path.read_bytes())
    if (len(rows) != count or len({row["id"] for row in rows}) != count
            or any(row["expected_verdict"] not in ("supported", "contradicted", "review") for row in rows)
            or any(len(row["source"]) > 600 for row in rows)):
        raise ValueError("adversarial fixture violates its declared shape")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=int, choices=sorted(ROUNDS), required=True)
    args = parser.parse_args(argv)
    stem, count, policy = ROUNDS[args.round]
    fixture = f"tests/fixtures/{stem}.json"
    destination = ROOT / "results" / f"{stem}.json"
    if destination.exists():
        raise FileExistsError("adversarial receipt exists; never overwrite or retry")
    sources = (fixture, *COMMON) if args.round == 1 else (
        fixture, *COMMON, "results/notation_adversarial.json", "results/integrity_final.json")
    lineage = frozen_receipt(ROOT, sources)
    cases = load(ROOT / fixture, count)
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
        "round": args.round, "fixture_sha256": hashlib.sha256((ROOT / fixture).read_bytes()).hexdigest(),
        "authorship": (f"Separate AI agent instance given only the written {policy} policy and "
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
