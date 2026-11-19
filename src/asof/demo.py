"""Deterministic invented onboarding example; no data, model services, network or file writes."""

from __future__ import annotations

from datetime import date

from asof.accounting import AccountingContext, ReportedFact, reconcile
from asof.research.identification import OutcomeBound, payoff_bounds
from asof.research.trajectories import signature2


def demo() -> dict:
    context = AccountingContext("INVENTED-ISSUER", "iso4217:USD",
                                date(2016, 12, 31), date(2016, 1, 1))
    facts = [ReportedFact(concept, context, value, f"invented-{concept}", decimals=1)
             for concept, value in (("revenue", "1.0"), ("cost", "0.3"), ("profit", "0.8"))]
    check = reconcile(facts, context=context, total="profit",
                      contributions=(("revenue", "1"), ("cost", "-1")))
    first = signature2([[0, 0], [1, 0], [1, -1]])
    reverse = signature2([[0, 0], [0, -1], [1, -1]])
    unknown_short = payoff_bounds([-1], [OutcomeBound(-1, float("inf"), False,
                                                      "no supported upper equity return bound")])
    return {
        "evidence_kind": "invented_fixture_not_market_evidence",
        "accounting": {"status": check.status, "reasons": check.reasons,
                       "truth_certified": False},
        "order": {"same_endpoint": bool((first.increment == reverse.increment).all()),
                  "first_area": float(first.area()[0, 1]),
                  "reverse_area": float(reverse.area()[0, 1])},
        "identification": {"unknown_short_lower_bound": "-infinity"
                           if unknown_short.unbounded else str(unknown_short.lower)},
        "network_requests": 0, "source_reads": 0, "trial_rows_written": 0,
    }
