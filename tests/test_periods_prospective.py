from datetime import date

import pytest

from asof.periods import HoldoutAccessError, prospective_cohort_allowed


def test_prospective_holdout_refuses_early_evaluation_and_exposed_filings():
    with pytest.raises(HoldoutAccessError):
        prospective_cohort_allowed("H4", date(2027, 1, 5), today=date(2028, 1, 1))
    assert prospective_cohort_allowed("H6a", date(2027, 1, 5), today=date(2029, 1, 1))
    assert not prospective_cohort_allowed("H6a", date(2024, 1, 5), today=date(2029, 1, 1))
    assert not prospective_cohort_allowed("H4", date(2026, 11, 21), today=date(2030, 1, 1))
    with pytest.raises(ValueError):
        prospective_cohort_allowed("H0", date(2027, 1, 5), today=date(2030, 1, 1))
