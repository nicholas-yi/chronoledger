"""One-shot: score REVIEW-PIPELINE-02 over all 30 round-5 probes from its two pre-split half runs."""

import hashlib
import json
import time
from pathlib import Path

from asof.reader_ai_review_v3 import load_probes
from asof.review_pipeline_v2 import summarize
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/review_pipeline_v5.json"
HALVES = ("results/review_pipeline_v5a.json", "results/review_pipeline_v5b.json")
SOURCES = (FIXTURE, *HALVES, "scripts/combine_review_pipeline_v5.py", "src/asof/review_pipeline_v2.py",
           "src/asof/review_pipeline.py", "src/asof/reader_ai_review_v3.py", "src/asof/claim_verifier.py",
           "src/asof/runtime.py")


def main():
    destination = ROOT / "results" / "review_pipeline_v5_combined.json"
    if destination.exists():
        raise FileExistsError("combined pipeline receipt exists; never overwrite or retry")
    lineage = frozen_receipt(ROOT, SOURCES)
    started = time.monotonic()
    halves = [json.loads((ROOT / path).read_bytes()) for path in HALVES]
    records = {}
    for half in halves:
        if set(records) & set(half["records"]):
            raise ValueError("half runs overlap")
        records.update(half["records"])
    probes = load_probes(ROOT / FIXTURE, 30)
    result = {
        "status": "complete_combined_pre_split_halves",
        "summary": summarize(probes, records),
        "halves": [{"study": half["study"], "status": half["status"], "stop_reason": half["stop_reason"],
                    "calls": len(half["calls"]), "controller_wall_seconds": half.get("controller_wall_seconds"),
                    "resource_check_passed": half.get("resource_check_passed"),
                    "freeze_commit": half["lineage"]["freeze_commit"]} for half in halves],
        "fixture_sha256": hashlib.sha256((ROOT / FIXTURE).read_bytes()).hexdigest(),
        "lineage": lineage, "model_calls_in_this_script": 0,
    }
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    write_receipt(destination, result)
    print(json.dumps({"summary": result["summary"], "halves": result["halves"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
