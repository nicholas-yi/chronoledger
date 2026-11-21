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


# D18: the 2022-2025 H4/H6a holdouts were decoded in memory (D6/D13/D15) and can never count
# as untouched, so their confirmatory evaluation moves to filings accepted on or after this day.
PROSPECTIVE_HOLDOUT_START = date(2026, 11, 22)
PROSPECTIVE_COHORT_END = date(2027, 11, 21)
PROSPECTIVE_EVALUATION_NOT_BEFORE = {"H4": date(2029, 3, 31), "H6a": date(2028, 12, 31)}
EXPOSED_HOLDOUTS = {"H4": (date(2022, 1, 1), date(2025, 6, 30)), "H6a": (date(2022, 1, 1), date(2025, 6, 30))}


def prospective_cohort_allowed(hypothesis: str, accepted: date, today: date) -> bool:
    """True only for a D18 cohort filing, evaluated after its registered outcome window closes."""
    if hypothesis not in PROSPECTIVE_EVALUATION_NOT_BEFORE:
        raise ValueError("D18 covers H4 and H6a only")
    if today < PROSPECTIVE_EVALUATION_NOT_BEFORE[hypothesis]:
        raise HoldoutAccessError(f"{hypothesis} prospective holdout is not evaluable before "
                                 f"{PROSPECTIVE_EVALUATION_NOT_BEFORE[hypothesis]}")
    return PROSPECTIVE_HOLDOUT_START <= accepted <= PROSPECTIVE_COHORT_END


def price_end_allowed(end: date, holdout_opened: bool = False) -> date:
    """Refuse to request or read market data past the development cutoff unless opened."""
    if end > DEV_RETURN_CUTOFF and not holdout_opened:
        raise HoldoutAccessError(
            f"market data through {end} would expose the sealed holdout "
            f"(development cutoff {DEV_RETURN_CUTOFF})"
        )
    return end
