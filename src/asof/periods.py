"""Sample periods (pre-registration v1 as amended by deviation D1) and holdout guards."""

from __future__ import annotations

from datetime import date

DEV_START = date(2023, 1, 1)
DEV_END = date(2024, 6, 30)
HOLDOUT_START = date(2024, 7, 1)
HOLDOUT_END = date(2026, 10, 31)
# Development signals formed by DEV_END earn returns through the following month at most.
DEV_RETURN_CUTOFF = date(2024, 7, 31)


class HoldoutAccessError(PermissionError):
    pass


def price_end_allowed(end: date, holdout_opened: bool = False) -> date:
    """Refuse to request or read market data past the development cutoff unless opened."""
    if end > DEV_RETURN_CUTOFF and not holdout_opened:
        raise HoldoutAccessError(
            f"market data through {end} would expose the sealed holdout "
            f"(development cutoff {DEV_RETURN_CUTOFF})"
        )
    return end
