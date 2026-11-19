from dataclasses import replace
from datetime import date
from decimal import Decimal, localcontext

import pytest

from asof.accounting import AccountingContext, ReportedFact, reconcile

CONTEXT = AccountingContext("INVENTED", "iso4217:USD", date(2016, 12, 31), date(2016, 1, 1))


def fact(concept, value, **kwargs):
    return ReportedFact(concept, CONTEXT, value, f"invented-{concept}", **kwargs)


def check(*facts):
    return reconcile(facts, context=CONTEXT, total="profit",
                     contributions=(("revenue", "1"), ("cost", "-1")))


def test_rounded_total_can_reconcile_when_displayed_numbers_do_not_add_exactly():
    facts = (fact("revenue", "1.0", decimals=1), fact("cost", "0.3", decimals=1),
             fact("profit", "0.8", decimals=1))
    assert Decimal("1.0") - Decimal("0.3") != Decimal("0.8")
    result = check(*facts)
    assert result.status == "consistent"
    assert result.calculated_interval.lower == Decimal("0.60")
    assert result.calculated_interval.upper == Decimal("0.80")
    assert check(facts[0], facts[1], fact("profit", "1.0", decimals=1)).status == "inconsistent"


def test_scale_context_and_nil_are_not_confused_with_exact_numbers():
    scaled = fact("revenue", "1", scale=6)
    assert check(scaled, fact("cost", "250000"), fact("profit", "750000")).status == "consistent"
    for other in (replace(CONTEXT, unit="iso4217:EUR"),
                  replace(CONTEXT, entity="OTHER"),
                  replace(CONTEXT, period_start=None),
                  replace(CONTEXT, dimensions=(("segment", "A"),))):
        result = check(replace(scaled, context=other), fact("cost", "0"), fact("profit", "1"))
        assert result.status == "unavailable"
    assert check(scaled, fact("cost", None), fact("profit", "1")).reasons == ("nil_fact:cost",)


def test_duplicate_intersection_tightens_evidence_and_conflicts_do_not_get_overwritten():
    broad = fact("revenue", "1", decimals=0)
    exact = replace(broad, value="1.2", decimals=1, source_id="second")
    result = check(broad, exact, fact("cost", "0.2"), fact("profit", "1.0"))
    assert result.status == "consistent" and result.duplicate_concepts == ("revenue",)
    assert check(broad, replace(exact, value="2.0"), fact("cost", "0"),
                 fact("profit", "1")).reasons == ("conflicting_duplicates:revenue",)
    with pytest.raises(ValueError, match="duplicate source"):
        check(broad, broad, fact("cost", "0"), fact("profit", "1"))


def test_truncation_open_endpoints_negative_weights_and_zero_are_preserved():
    # 1 truncated to units is [1,2), so it cannot equal the exact point 2.
    assert check(fact("revenue", "1", decimals=0, rounding="truncate"),
                 fact("cost", "0"), fact("profit", "2")).status == "inconsistent"
    negative = fact("cost", "-1", decimals=0, rounding="truncate").interval()
    assert (negative.lower, negative.upper) == (Decimal(-2), Decimal(-1))
    assert not negative.lower_closed and negative.upper_closed
    assert check(fact("revenue", "0"), fact("cost", "-1", decimals=0, rounding="truncate"),
                 fact("profit", "2")).status == "inconsistent"
    zero = fact("cost", "0", decimals=0, rounding="truncate").interval()
    assert zero.lower == -1 and zero.upper == 1
    assert not zero.lower_closed and not zero.upper_closed


def test_decimal_context_does_not_change_results_and_unsupported_precision_is_explicit():
    facts = (fact("revenue", "123456789012345678901234567890"),
             fact("cost", "1"), fact("profit", "123456789012345678901234567889"))
    with localcontext() as context:
        context.prec = 3
        assert check(*facts).status == "consistent"
    with pytest.raises(ValueError, match="beyond declared precision"):
        fact("revenue", "1.23", decimals=1).interval()
    with pytest.raises(TypeError, match="not a float"):
        fact("revenue", 1.23)
    with pytest.raises(ValueError, match="unique"):
        reconcile(facts, context=CONTEXT, total="revenue", contributions=(("revenue", "1"),))
