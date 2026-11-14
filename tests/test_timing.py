from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from asof.periods import HoldoutAccessError
from asof.timing import plan_return_window


@pytest.fixture
def closes():
    et = ZoneInfo("America/New_York")
    return (
        datetime(2023, 3, 8, 16, tzinfo=et),
        datetime(2023, 3, 9, 16, tzinfo=et),
        datetime(2023, 3, 10, 13, tzinfo=et),  # Synthetic early close, not a calendar assertion.
        datetime(2023, 3, 13, 16, tzinfo=et),
        datetime(2023, 3, 14, 16, tzinfo=et),
        datetime(2023, 3, 15, 16, tzinfo=et),
    )


def _plan(closes, **overrides):
    kwargs = {
        "information_ready": closes[2] - timedelta(minutes=1),
        "observation_cutoff": datetime(2024, 7, 31, 23, 59, tzinfo=UTC),
        "firm_closes": closes, "factor_closes": closes,
        "horizon": 2, "estimation_offsets": (-1, -1),
    }
    kwargs.update(overrides)
    return plan_return_window(closes, **kwargs)


@pytest.mark.parametrize(
    ("ready_minutes", "deadline_minutes", "expected_index"),
    [(-1, None, 2), (0, None, 3), (-11, -10, 2), (-10, -10, 3)],
)
def test_ready_and_supplied_deadline_are_strict(closes, ready_minutes, deadline_minutes,
                                               expected_index) -> None:
    deadline = None if deadline_minutes is None else {
        closes[2]: closes[2] + timedelta(minutes=deadline_minutes)}
    plan = _plan(
        closes, information_ready=(closes[2] + timedelta(minutes=ready_minutes)).astimezone(UTC),
        order_deadlines=deadline,
    )
    assert plan.anchor == closes[expected_index].astimezone(UTC)
    assert plan.order_deadline == (deadline or {}).get(closes[expected_index])
    assert plan.status == "complete"


def test_supplied_early_close_dst_and_post_entry_interval(closes) -> None:
    plan = _plan(closes, estimation_offsets=(-2, -1))
    assert plan.anchor == datetime(2023, 3, 10, 18, tzinfo=UTC)
    assert plan.outcome[0].start == plan.anchor
    assert plan.outcome[0].end == datetime(2023, 3, 13, 20, tzinfo=UTC)
    assert [(s.offset, s.start, s.end) for s in plan.outcome] == [
        (1, closes[2].astimezone(UTC), closes[3].astimezone(UTC)),
        (2, closes[3].astimezone(UTC), closes[4].astimezone(UTC)),
    ]
    assert [s.offset for s in plan.estimation] == [-2, -1]
    assert plan.estimation[0].start is None
    assert plan.estimation[0].end == closes[0].astimezone(UTC)
    assert plan.estimation_support == 1
    assert plan.outcome_support == 2
    assert plan.status == "unavailable"


@pytest.mark.parametrize(
    ("collection", "missing_index", "expected_estimation", "expected_outcome", "reason"),
    [
        ("firm_closes", 2, 1, 1, "missing_firm_start"),
        ("firm_closes", 3, 1, 0, "missing_firm_end"),
        ("factor_closes", 3, 1, 1, "missing_factor_row"),
        ("factor_closes", 1, 0, 2, "missing_factor_row"),
        ("firm_closes", 0, 0, 2, "missing_firm_start"),
    ],
)
def test_missing_support_keeps_anchor_and_scheduled_slots(
    closes, collection, missing_index, expected_estimation, expected_outcome, reason,
) -> None:
    plan = _plan(closes, **{collection: tuple(t for i, t in enumerate(closes) if i != missing_index)})
    assert plan.anchor == closes[2].astimezone(UTC)
    assert [s.end for s in plan.outcome] == [t.astimezone(UTC) for t in closes[3:5]]
    assert plan.estimation[0].start == closes[0].astimezone(UTC)
    assert plan.estimation_support == expected_estimation
    assert plan.outcome_support == expected_outcome
    assert plan.status == "missing"
    assert reason in {r for slot in (*plan.estimation, *plan.outcome) for r in slot.reasons}
    if collection == "firm_closes" and missing_index == 2:
        assert plan.anchor_reasons == ("missing_anchor_close",)


@pytest.mark.parametrize("case", ["tail", "empty", "no_eligible_close"])
def test_missing_schedule_retains_requested_offsets(closes, case) -> None:
    schedule = () if case == "empty" else closes[:3]
    ready = closes[2] if case == "no_eligible_close" else closes[2] - timedelta(minutes=1)
    plan = plan_return_window(
        schedule, ready,
        observation_cutoff=datetime(2024, 7, 31, tzinfo=UTC),
        firm_closes=schedule, factor_closes=schedule, horizon=2, estimation_offsets=(-1, -1),
    )
    assert plan.status == "unavailable"
    assert [s.offset for s in plan.outcome] == [1, 2]
    assert all(s.end is None for s in plan.outcome)
    assert plan.anchor == (closes[2].astimezone(UTC) if case == "tail" else None)
    if case != "tail":
        assert plan.anchor_reasons == ("no_eligible_close",)
    else:
        assert "end_outside_schedule" in plan.outcome[0].reasons


def test_cutoff_censors_known_schedule_without_reading_later_observations() -> None:
    schedule = tuple(datetime(2024, 7, day, 20, tzinfo=UTC) for day in (26, 29, 30, 31))
    schedule += (datetime(2024, 8, 1, 20, tzinfo=UTC),)
    plan = _plan(schedule, information_ready=schedule[2] - timedelta(minutes=1),
                 firm_closes=schedule[:4], factor_closes=schedule[:4])
    assert plan.status == "censored"
    assert plan.outcome_support == 1
    assert plan.outcome[1].offset == 2
    assert plan.outcome[1].end == schedule[4]
    assert plan.outcome[1].reasons == ("after_observation_cutoff",)
    later_anchor = _plan(
        schedule, information_ready=plan.observation_cutoff,
        firm_closes=schedule[:4], factor_closes=schedule[:4],
    )
    assert later_anchor.anchor == schedule[4]
    assert later_anchor.status == "censored"
    assert later_anchor.anchor_reasons == ("anchor_after_observation_cutoff",)
    with pytest.raises(ValueError, match="after observation_cutoff"):
        _plan(schedule, information_ready=schedule[2] - timedelta(minutes=1),
              firm_closes=schedule, factor_closes=schedule[:4])
    with pytest.raises(HoldoutAccessError):
        _plan(schedule, observation_cutoff=datetime(2024, 8, 1, 23, tzinfo=UTC))


@pytest.mark.parametrize("invalid", ["naive", "order", "duplicate", "deadline", "horizon", "estimation"])
def test_invalid_inputs_raise_instead_of_success_shaped_plan(closes, invalid) -> None:
    kwargs = {}
    if invalid == "naive":
        kwargs["information_ready"] = closes[2].replace(tzinfo=None)
    elif invalid == "order":
        closes = tuple(reversed(closes))
    elif invalid == "duplicate":
        closes = (closes[0], *closes)
    elif invalid == "deadline":
        kwargs["order_deadlines"] = {closes[2]: closes[2] + timedelta(seconds=1)}
    elif invalid == "horizon":
        kwargs["horizon"] = 0
    else:
        kwargs["estimation_offsets"] = (-1, 0)
    with pytest.raises(ValueError):
        _plan(closes, **kwargs)
