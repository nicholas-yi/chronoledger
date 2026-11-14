"""Prospective component arithmetic, separate from the frozen backtest cost path."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CostBreakdown:
    status: Literal["available", "unavailable"]
    currency: str
    one_way_turnover: float
    gross_traded_fraction: float
    component_return_costs: dict[str, float | None]
    total_return_cost: float | None
    total_currency_cost: float | None
    break_even_one_way_bps: float | None
    reasons: tuple[str, ...]
    borrow_status: Literal["supported", "unavailable", "not_applicable"] = "supported"


def component_costs(
    *,
    capital: float,
    currency: str,
    turnover: float,
    turnover_basis: Literal["one_way", "gross_traded"],
    half_spread_bps: float,
    execution_bps: Mapping[str, float | None],
    holding_bps_of_capital: Mapping[str, float | None],
    borrow_available: bool | None,
    fills_supported: bool | None,
    gross_return: float | None,
    exposure: Literal["long_short", "long_only"] = "long_short",
) -> CostBreakdown:
    """Execution rates apply per absolute traded notional; holding costs per capital/period.

    Capital and the returned currency cost use one caller-declared currency, with no FX
    conversion. Holding inputs are already period-accrued (positive cost, negative credit);
    no annual-rate/day-count convention is inferred. Caller flags are evidence assertions,
    not historical borrow/fill verification. Break-even is all-in one-way execution bps after
    holding costs, not an additional charge. ``one_way`` explicitly declares half-L1 turnover;
    this does not certify the basis of an externally supplied frozen turnover. This is a
    component ledger, not net P&L: distributions already included in a gross total-return P&L
    must not be deducted from that P&L a second time. Reconcile the gross/holding cashflow basis
    before using the legacy break-even output; use ``reconcile_net_return`` for explicit
    distribution-basis netting. Declared long-only exposure makes borrow not applicable,
    but never waives fill evidence or financing costs.
    """
    if (not math.isfinite(capital) or capital <= 0 or not math.isfinite(turnover)
            or turnover < 0 or not math.isfinite(half_spread_bps) or half_spread_bps < 0):
        raise ValueError("capital must be positive; turnover and half-spread finite/nonnegative")
    if not currency or not currency.strip():
        raise ValueError("an explicit common capital/cost currency is required")
    if turnover_basis not in {"one_way", "gross_traded"}:
        raise ValueError("unknown turnover basis")
    if exposure not in {"long_short", "long_only"}:
        raise ValueError("unknown exposure")
    if set(execution_bps) != {"fees", "impact"} or set(holding_bps_of_capital) != {
        "borrow", "financing", "distributions",
    }:
        raise ValueError("exact component keys required; spread/total cannot be charged twice")
    for values, nonnegative in ((execution_bps, True), (holding_bps_of_capital, False)):
        if any(v is not None and (not math.isfinite(v) or (nonnegative and v < 0))
               for v in values.values()):
            raise ValueError("component costs must be finite; execution rates nonnegative")
    if exposure == "long_only" and holding_bps_of_capital["borrow"] not in (None, 0):
        raise ValueError("declared long-only exposure cannot incur short-borrow costs")
    if gross_return is not None and not math.isfinite(gross_return):
        raise ValueError("gross_return must be finite or unknown")
    traded = turnover * 2 if turnover_basis == "one_way" else turnover
    components: dict[str, float | None] = {"spread": half_spread_bps * traded / 10000}
    components.update({k: None if v is None else v * traded / 10000 for k, v in execution_bps.items()})
    components.update({k: None if v is None else v / 10000
                       for k, v in holding_bps_of_capital.items()})
    if exposure == "long_only":
        components["borrow"] = 0.0
    borrow_status: Literal["supported", "unavailable", "not_applicable"] = (
        "not_applicable" if exposure == "long_only" else
        "supported" if borrow_available is True else "unavailable")
    reasons = [f"unknown_{k}" for k, v in components.items() if v is None]
    if borrow_status == "unavailable":
        reasons.append("borrow_availability_not_supported")
    if fills_supported is not True:
        reasons.append("fills_not_supported")
    if reasons:
        return CostBreakdown("unavailable", currency, traded / 2, traded, components, None, None, None,
                             tuple(reasons), borrow_status)
    total = sum(v for v in components.values() if v is not None)
    holding_values = [components[k] for k in ("borrow", "financing", "distributions")]
    holding = sum(v for v in holding_values if v is not None)
    break_even = None if gross_return is None or traded == 0 else (
        (gross_return - holding) / traded * 10000)
    return CostBreakdown("available", currency, traded / 2, traded, components, total, total * capital,
                         break_even, (), borrow_status)


@dataclass(frozen=True)
class TurnoverReceipt:
    status: Literal["consistent", "basis_mismatch"]
    frozen_one_way_turnover: float
    observed_half_l1_turnover: float
    frozen_spread_currency: float
    observed_spread_currency: float
    currency: str


def reconcile_turnover(
    *, capital: float, traded_notional: float, frozen_turnover: float,
    half_spread_bps: float, currency: str,
) -> TurnoverReceipt:
    """Compare observed Q/(2*capital) with frozen T; never renormalize or add charges."""
    if (not currency.strip() or not math.isfinite(capital) or capital <= 0
            or any(not math.isfinite(v) or v < 0
                   for v in (traded_notional, frozen_turnover, half_spread_bps))):
        raise ValueError("positive capital, common currency and finite nonnegative cost inputs required")
    implied = traded_notional / (2 * capital)
    consistent = math.isclose(frozen_turnover, implied, rel_tol=1e-12, abs_tol=1e-15)
    return TurnoverReceipt(
        "consistent" if consistent else "basis_mismatch", frozen_turnover, implied,
        2 * half_spread_bps / 10000 * frozen_turnover * capital,
        half_spread_bps / 10000 * traded_notional, currency)


@dataclass(frozen=True)
class NetCostReturn:
    status: Literal["available", "unavailable"]
    incremental_return_cost: float | None
    net_return: float | None
    break_even_one_way_bps: float | None
    reasons: tuple[str, ...]


def reconcile_net_return(
    costs: CostBreakdown, *, gross_return: float, distributions_in_gross: bool | None,
) -> NetCostReturn:
    """Dimensionless per-period P&L reconciliation; do not debit distributions twice."""
    if not math.isfinite(gross_return):
        raise ValueError("gross_return must be finite")
    if distributions_in_gross is not None and not isinstance(distributions_in_gross, bool):
        raise ValueError("distribution inclusion must be explicitly true, false or unknown")
    if costs.status != "available" or costs.total_return_cost is None:
        return NetCostReturn("unavailable", None, None, None, costs.reasons)
    if distributions_in_gross is None:
        return NetCostReturn("unavailable", None, None, None, ("gross_distribution_basis_unknown",))
    distribution = costs.component_return_costs["distributions"]
    borrow, financing = (costs.component_return_costs[k] for k in ("borrow", "financing"))
    if distribution is None or borrow is None or financing is None:
        return NetCostReturn("unavailable", None, None, None, ("holding_component_unknown",))
    included = distribution if distributions_in_gross else 0.0
    incremental = costs.total_return_cost - included
    holding = borrow + financing + distribution - included
    break_even = (None if costs.gross_traded_fraction == 0 else
                  (gross_return - holding) / costs.gross_traded_fraction * 10000)
    return NetCostReturn("available", incremental, gross_return - incremental, break_even, ())
