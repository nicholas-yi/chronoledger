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
) -> CostBreakdown:
    """Execution rates apply per absolute traded notional; holding costs per capital/period.

    Capital and the returned currency cost use one caller-declared currency, with no FX
    conversion. Holding inputs are already period-accrued (positive cost, negative credit);
    no annual-rate/day-count convention is inferred. Caller flags are evidence assertions,
    not historical borrow/fill verification. Break-even is all-in one-way execution bps after
    holding costs, not an additional charge.
    """
    if (not math.isfinite(capital) or capital <= 0 or not math.isfinite(turnover)
            or turnover < 0 or not math.isfinite(half_spread_bps) or half_spread_bps < 0):
        raise ValueError("capital must be positive; turnover and half-spread finite/nonnegative")
    if not currency or not currency.strip():
        raise ValueError("an explicit common capital/cost currency is required")
    if turnover_basis not in {"one_way", "gross_traded"}:
        raise ValueError("unknown turnover basis")
    if set(execution_bps) != {"fees", "impact"} or set(holding_bps_of_capital) != {
        "borrow", "financing", "distributions",
    }:
        raise ValueError("exact component keys required; spread/total cannot be charged twice")
    for values, nonnegative in ((execution_bps, True), (holding_bps_of_capital, False)):
        if any(v is not None and (not math.isfinite(v) or (nonnegative and v < 0))
               for v in values.values()):
            raise ValueError("component costs must be finite; execution rates nonnegative")
    if gross_return is not None and not math.isfinite(gross_return):
        raise ValueError("gross_return must be finite or unknown")
    traded = turnover * 2 if turnover_basis == "one_way" else turnover
    components: dict[str, float | None] = {"spread": half_spread_bps * traded / 10000}
    components.update({k: None if v is None else v * traded / 10000 for k, v in execution_bps.items()})
    components.update({k: None if v is None else v / 10000
                       for k, v in holding_bps_of_capital.items()})
    reasons = [f"unknown_{k}" for k, v in components.items() if v is None]
    if borrow_available is not True:
        reasons.append("borrow_availability_not_supported")
    if fills_supported is not True:
        reasons.append("fills_not_supported")
    if reasons:
        return CostBreakdown("unavailable", currency, traded / 2, traded, components, None, None, None,
                             tuple(reasons))
    total = sum(v for v in components.values() if v is not None)
    holding = sum(v for v in holding_bps_of_capital.values() if v is not None) / 10000
    break_even = None if gross_return is None or traded == 0 else (
        (gross_return - holding) / traded * 10000)
    return CostBreakdown("available", currency, traded / 2, traded, components, total, total * capital,
                         break_even, ())
