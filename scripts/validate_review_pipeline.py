"""One-shot record of REVIEW-PIPELINE-01 on fresh round-4 probes, after the frozen AI arm has run."""

import hashlib
import json
import time
from pathlib import Path

from asof.reader_ai_review_v3 import load_probes
from asof.review_pipeline import evaluate
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/reader_ai_review_v4.json"
SOURCES = (FIXTURE, "scripts/validate_review_pipeline.py", "src/asof/review_pipeline.py",
           "src/asof/claim_verifier.py", "src/asof/financial_notation.py", "src/asof/reader_fields.py",
           "src/asof/linked_reader.py", "src/asof/reader_reliability.py", "src/asof/reader_ai_review_v3.py",
           "src/asof/runtime.py", "results/reader_ai_review_v4.json", "tests/test_review_pipeline.py")


def main():
    destination = ROOT / "results" / "review_pipeline_v4.json"
    if destination.exists():
        raise FileExistsError("pipeline receipt exists; never overwrite or retry")
    lineage = frozen_receipt(ROOT, SOURCES)
    started = time.monotonic()
    ai = json.loads((ROOT / "results" / "reader_ai_review_v4.json").read_bytes())
    result = {
        "status": "complete_declared_pipeline_on_fresh_probes",
        **evaluate(load_probes(ROOT / FIXTURE), ai["records"]),
        "ai_run_status": ai["status"], "ai_run_freeze": ai["lineage"]["freeze_commit"],
        "fixture_sha256": hashlib.sha256((ROOT / FIXTURE).read_bytes()).hexdigest(),
        "lineage": lineage, "model_calls_in_this_script": 0,
    }
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    write_receipt(destination, result)
    print(json.dumps({key: result[key] for key in ("pipeline", "rules_only", "ai_only", "decided_by")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
