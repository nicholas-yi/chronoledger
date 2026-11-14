import pytest

from asof.costs import component_costs


def _costs(**overrides):
    args = {"capital": 100000.0, "currency": "USD", "turnover": 0.4, "turnover_basis": "one_way",
            "half_spread_bps": 10.0, "execution_bps": {"fees": 1.0, "impact": 2.0},
            "holding_bps_of_capital": {"borrow": 3.0, "financing": -1.0, "distributions": 1.0},
            "borrow_available": True, "fills_supported": True, "gross_return": 0.01}
    args.update(overrides)
    return component_costs(**args)


def test_turnover_bases_match_frozen_normalization_without_double_charge() -> None:
    one_way = _costs()
    gross = _costs(turnover=0.8, turnover_basis="gross_traded")
    assert one_way == gross
    assert one_way.component_return_costs["spread"] == pytest.approx(2 * 10 / 10000 * 0.4)
    assert one_way.total_return_cost == pytest.approx((10 + 1 + 2) / 10000 * 0.8 + 3 / 10000)
    assert one_way.total_currency_cost == pytest.approx(one_way.total_return_cost * 100000)
    assert one_way.break_even_one_way_bps == pytest.approx((0.01 - 0.0003) / 0.8 * 10000)
    with pytest.raises(ValueError, match="charged twice"):
        _costs(execution_bps={"fees": 1.0, "impact": 2.0, "spread": 10.0})


@pytest.mark.parametrize("override", [
    {"borrow_available": None}, {"fills_supported": False},
    {"holding_bps_of_capital": {"borrow": None, "financing": 0.0, "distributions": 0.0}},
])
def test_unknown_execution_evidence_is_not_a_valid_cost_total(override) -> None:
    result = _costs(**override)
    assert result.status == "unavailable"
    assert result.total_return_cost is None and result.total_currency_cost is None
    assert result.break_even_one_way_bps is None and result.reasons
