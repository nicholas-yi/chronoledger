import pytest

from asof.costs import component_costs, reconcile_net_return, reconcile_turnover


def _costs(**overrides):
    args = {"capital": 100000.0, "currency": "USD", "turnover": 0.4, "turnover_basis": "one_way",
            "half_spread_bps": 10.0, "execution_bps": {"fees": 1.0, "impact": 2.0},
            "holding_bps_of_capital": {"borrow": 3.0, "financing": -1.0, "distributions": 1.0},
            "borrow_available": True, "fills_supported": True, "gross_return": 0.01}
    args.update(overrides)
    return component_costs(**args)


def test_declared_half_l1_and_gross_traded_normalizations_without_double_charge() -> None:
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


def test_long_only_borrow_is_not_applicable_but_fill_and_financing_evidence_remain() -> None:
    result = _costs(exposure="long_only", borrow_available=None,
                    holding_bps_of_capital={"borrow": None, "financing": 3.0, "distributions": 0.0})
    assert result.status == "available" and result.borrow_status == "not_applicable"
    assert result.component_return_costs["borrow"] == 0
    assert _costs(
        exposure="long_only", fills_supported=False,
        holding_bps_of_capital={"borrow": 0.0, "financing": 0.0, "distributions": 0.0},
    ).status == "unavailable"
    with pytest.raises(ValueError, match="short-borrow"):
        _costs(exposure="long_only")


def test_joint_basis_receipt_preserves_frozen_charge_instead_of_halving_turnover() -> None:
    result = reconcile_turnover(capital=10000, traded_notional=2000, frozen_turnover=0.2,
                                half_spread_bps=4, currency="USD")
    assert result.status == "basis_mismatch"
    assert result.frozen_spread_currency == pytest.approx(1.60)
    assert result.observed_spread_currency == pytest.approx(0.80)
    assert result.frozen_one_way_turnover == 0.2
    consistent = reconcile_turnover(
        capital=10000, traded_notional=2000, frozen_turnover=0.1,
        half_spread_bps=4, currency="USD")
    assert consistent.status == "consistent"
    assert consistent.frozen_spread_currency == consistent.observed_spread_currency


def test_total_return_and_price_only_pnl_agree_without_double_distribution_debit() -> None:
    result = _costs(
        capital=10000, turnover=1, turnover_basis="gross_traded", half_spread_bps=4,
        execution_bps={"fees": 1, "impact": 0},
        holding_bps_of_capital={"borrow": 15, "financing": 10, "distributions": 50})
    assert result.total_currency_cost == 80
    price_only = reconcile_net_return(result, gross_return=0, distributions_in_gross=False)
    total_return = reconcile_net_return(result, gross_return=-0.005, distributions_in_gross=True)
    assert price_only.net_return == pytest.approx(-0.008)
    assert total_return.net_return == pytest.approx(-0.008)
    assert total_return.incremental_return_cost == pytest.approx(0.003)
    assert reconcile_net_return(
        result, gross_return=0, distributions_in_gross=None).status == "unavailable"
