from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from asof.labels import LabelEvidence, validate_label


def test_verified_positive_does_not_require_mature_followup() -> None:
    start = datetime(2016, 1, 1, tzinfo=UTC)
    label = LabelEvidence("formal_365d", "positive", True, ("synthetic-event",),
                          positive_verified=True, signal_time=start,
                          event_time=datetime(2016, 7, 1, tzinfo=UTC))
    assert validate_label(label) == label
    with pytest.raises(ValueError, match="complete observation"):
        validate_label(replace(label, status="negative", value=False, positive_verified=False,
                               event_time=None))
    with pytest.raises(ValueError, match="complete follow-up"):
        validate_label(replace(label, status="negative", value=False, positive_verified=False,
                               observation_complete=True, event_time=None))
    negative = replace(label, status="negative", value=False, positive_verified=False,
                       observation_complete=True, followup_complete=True, event_time=None,
                       observation_end=start + timedelta(days=365))
    assert validate_label(negative).value is False
    with pytest.raises(ValueError, match="observation envelope"):
        validate_label(replace(negative, observation_end=start + timedelta(days=364)))


@pytest.mark.parametrize(("offset", "valid"), [(0, False), (365, True), (366, False)])
def test_formal_event_interval_is_open_left_closed_right(offset, valid) -> None:
    start = datetime(2016, 1, 1, tzinfo=UTC)
    label = LabelEvidence("formal_365d", "positive", True, ("synthetic-event",),
                          positive_verified=True, signal_time=start,
                          event_time=start + timedelta(days=offset))
    if valid:
        assert validate_label(label) == label
    else:
        with pytest.raises(ValueError, match="formal positive"):
            validate_label(label)


def test_absent_impairment_is_unknown_not_automatic_zero() -> None:
    unknown = LabelEvidence("impairment", "unknown", None, (), reason="tag_not_observed")
    assert validate_label(unknown).value is None
    negative = replace(unknown, status="negative", value=False, evidence_refs=("statement",),
                       observation_complete=True)
    with pytest.raises(ValueError, match="absent impairment"):
        validate_label(negative)
    assert validate_label(replace(negative, explicit_zero=True)).value is False
    assert validate_label(replace(negative, complete_statement=True)).value is False


@pytest.mark.parametrize("status", ["unknown", "censored"])
def test_unknown_states_require_null_and_reason(status) -> None:
    label = LabelEvidence("income_decline", status, None, (), reason="report_unavailable")
    assert validate_label(label).status == status
    with pytest.raises(ValueError, match="null value"):
        validate_label(replace(label, value=False))
    with pytest.raises(ValueError, match="explicit reason"):
        validate_label(replace(label, reason=None))
