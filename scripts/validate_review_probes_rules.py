"""Offline: the deterministic source-rule verifier (frozen before the probes were opened) on the 24 fresh probes.

Mapping, fixed in code: an answered candidate becomes a claim sentence; supported -> supported,
contradicted -> unsupported, review -> uncertain. An abstention is unsupported when the verifier can
prove the requested fact from the source; otherwise uncertain, because rules cannot prove non-disclosure.
A post-hoc composition (rules first, recorded AI verdict only when rules are uncertain) is reported
separately and labelled exposed: it uses recorded model outputs and probes already read.
"""

import hashlib
import json
import time
from pathlib import Path

from asof.claim_verifier import Claim, resolve_fact, verify_claim
from asof.reader_ai_review_v3 import load_probes
from asof.runtime import frozen_receipt, peak_rss_bytes, write_receipt

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/reader_ai_review_v3.json"
SOURCES = (FIXTURE, "scripts/validate_review_probes_rules.py", "src/asof/claim_verifier.py",
           "src/asof/financial_notation.py", "src/asof/reader_fields.py", "src/asof/linked_reader.py",
           "src/asof/reader_reliability.py", "src/asof/reader_ai_review_v3.py", "src/asof/runtime.py",
           "results/reader_ai_review_v3.json", "results/reader_ai_review_v3_control.json")
RULE_VERDICT = {"supported": "supported", "contradicted": "unsupported", "review": "uncertain"}


def rule_decision(probe) -> dict:
    case, candidate = probe.task.case, probe.task.candidate
    if candidate.abstain:
        fact = resolve_fact(case.source, Claim(case.issuer, case.metric, "0", "usd million", case.requested_period, False))
        return {"verdict": "unsupported" if fact is not None else "uncertain",
                "reason": "source_fact_proved" if fact is not None else "nondisclosure_not_provable_by_rules"}
    claim = f"{case.issuer}'s {candidate.period} {case.metric} was {candidate.value} {candidate.unit}."
    decision = verify_claim(case.source, claim)
    return {"verdict": RULE_VERDICT[decision["verdict"]], "reason": decision["reason"], "claim": claim,
            "proof_valid": decision["proof_valid"]}


def score(rows: list[dict], key: str) -> dict:
    return {
        "planned": len(rows), "correct_verdicts": sum(row[key] == row["expected"] for row in rows),
        "false_support": sum(row[key] == "supported" and row["expected"] == "unsupported" for row in rows),
        "false_rejection": sum(row[key] == "unsupported" and row["expected"] == "supported" for row in rows),
        "uncertain_or_invalid": sum(row[key] not in ("supported", "unsupported") for row in rows),
        "resolved": sum(row[key] in ("supported", "unsupported") for row in rows),
        "resolved_correct": sum(row[key] == row["expected"] for row in rows if row[key] in ("supported", "unsupported")),
    }


def main():
    destination = ROOT / "results" / "reader_ai_review_v3_rules.json"
    if destination.exists():
        raise FileExistsError("rules receipt exists; never overwrite or retry")
    lineage = frozen_receipt(ROOT, SOURCES)
    started = time.monotonic()
    probes = load_probes(ROOT / FIXTURE)
    recorded = {name: json.loads((ROOT / "results" / f"{name}.json").read_bytes())["records"]
                for name in ("reader_ai_review_v3", "reader_ai_review_v3_control")}
    rows = []
    for probe in probes:
        rule = rule_decision(probe)
        ai = {name: (records.get(probe.task.case.id, {}).get("ai_review_v3") or {}) for name, records in recorded.items()}
        verdicts = {name: row.get("verdict") if row.get("valid") else None for name, row in ai.items()}
        rows.append({"id": probe.task.case.id, "category": probe.category, "expected": probe.task.expected_verdict,
                     "rules": rule["verdict"], "rule_detail": rule,
                     **{f"posthoc_rules_then_{name}": rule["verdict"] if rule["verdict"] != "uncertain"
                        else verdicts[name] for name in verdicts}})
    result = {
        "status": "complete_offline_rules_on_fresh_probes",
        "rules": score(rows, "rules"),
        "posthoc_exposed_compositions": {key: score(rows, key) for key in rows[0] if key.startswith("posthoc_")},
        "rows": rows, "fixture_sha256": hashlib.sha256((ROOT / FIXTURE).read_bytes()).hexdigest(),
        "verifier_code_frozen_before_probes_opened": "a2e57c4 (verifier) precedes daa5219 (probes added)",
        "mapping_note": __doc__, "lineage": lineage, "independent_human_gold": False, "model_calls": 0,
    }
    result["wall_seconds"] = time.monotonic()-started
    result["process_peak_RSS_bytes"] = peak_rss_bytes()
    write_receipt(destination, result)
    print(json.dumps({key: result[key] for key in ("rules", "posthoc_exposed_compositions")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
