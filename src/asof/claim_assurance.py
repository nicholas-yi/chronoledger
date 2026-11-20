"""Named correctness controls, separate from factual-verdict coverage and independent evaluation."""

from __future__ import annotations

from asof.claim_challenge import boundary_controls, fixture
from asof.claim_verifier import summarize_structured, verify_claim


def controls() -> tuple[dict, ...]:
    records = []
    claim = "FictionTest's 2016 revenue was 18 USD million."
    nonactual = (
        ("negation", "FictionTest never actually reported revenue of 18 USD million for 2016."),
        ("negation", "FictionTest did not actually report revenue of 18 USD million for 2016."),
        ("forecast", "FictionTest forecast revenue of 18 USD million for 2016."),
        ("forecast", "FictionTest would report revenue of 18 USD million for 2016."),
        ("forecast", "FictionTest expected revenue of 18 USD million for 2016."),
        ("illustration", ("FictionTest reported revenue of 18 USD million for 2016. "
                          "This is an illustrative example, not an actual disclosure.")),
        ("annual_scope", ("FictionTest reported revenue of 18 USD million for 2016.\n"
                          "These figures are quarterly, not annual.")),
        ("forecast_scope", ("FictionTest reported revenue of 18 USD million for 2016.\n"
                            "All amounts are forecasts, not actuals.")),
    )
    for kind, source in nonactual:
        records.append({"category": kind, "source": source, "claim": claim, "expected_verdict": "review"})
    records.append({
        "category": "unrelated_customer_forecast",
        "source": "FictionTest reported revenue of 18 USD million for 2016. Its customer may forecast lower costs.",
        "claim": claim, "expected_verdict": "supported"})
    for currency in ("USD", "EUR", "GBP"):
        for value in (0, 18, -23, 123456789012345678901234567890123456789):
            source = f"FictionTest reported revenue of {value} {currency} million for 2016."
            for increment in (0, 1):
                records.append({
                    "category": "exact_equivalence" if increment == 0 else "nearby_inequality",
                    "source": source,
                    "claim": f"FictionTest's 2016 revenue was {value*1000+increment} {currency} thousand.",
                    "expected_verdict": "supported" if increment == 0 else "contradicted"})
    source = "FictionTest: fiscal2016 EPS(diluted)=GBP2.20; EPS(basic)=EUR2.50."
    for text, verdict in (
        ("FictionTest's 2016 diluted earnings per share was 2.20 GBP per share.", "supported"),
        ("FictionTest's 2016 diluted earnings per share was 2.50 GBP per share.", "contradicted"),
        ("FictionTest's 2016 basic earnings per share was 2.50 EUR per share.", "supported"),
        ("FictionTest's 2017 diluted earnings per share was 2.20 GBP per share.", "review"),
    ):
        records.append({"category": "basic_diluted_eps", "source": source,
                        "claim": text, "expected_verdict": verdict})
    return tuple({"id": f"ASSURE-{i:02d}", **row} for i, row in enumerate(records, 1))


def evaluate() -> dict:
    rows = []
    for case in controls():
        decision = verify_claim(case["source"], case["claim"])
        rows.append({
            "id": case["id"], "category": case["category"],
            "expected_verdict": case["expected_verdict"], "decision": decision,
            "policy_correct": decision["verdict"] == case["expected_verdict"],
        })
    current = summarize_structured(fixture(), [])
    boundary = summarize_structured(boundary_controls(), [])
    return {
        "status": "complete_deterministic_source_claim_v2_assurance",
        "contract": "source-claim-v2",
        "policy_controls": {
            "planned": len(rows), "correct": sum(row["policy_correct"] for row in rows),
            "expected_review": sum(row["expected_verdict"] == "review" for row in rows),
            "factual_verdicts_resolved": sum(row["decision"]["verdict"] != "review" for row in rows),
            "review_policy_checks_are_not_resolved_financial_facts": True,
            "records": rows,
        },
        "current_supported_challenge": current,
        "prior_format_boundaries": boundary,
        "overall_30_case_coverage": {
            "planned": current["planned"]+boundary["planned"],
            "correct_including_unresolved_as_misses": current["correct"]+boundary["correct"],
            "resolved": current["resolved"]+boundary["resolved"],
            "requires_review": current["requires_review"]+boundary["requires_review"],
        },
        "no_model_calls": True, "historical_results_rewritten": False,
        "independent_gold": False, "promote": False,
        "limitations": [
            "Finite explicit source-admission rules are not general natural-language entailment.",
            "Mixed illustrative/actual documents may be conservatively deferred.",
            "Turnover/top-line aliases and spelled-out amounts are not silently equated to revenue.",
            "Human-labelled independent real-source accuracy remains unavailable.",
        ],
    }
