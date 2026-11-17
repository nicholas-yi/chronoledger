import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from asof.research.prequential import Forecast, ForecastJournal, Settlement

T = datetime(2016, 1, 1, tzinfo=UTC)


def time(day: float) -> datetime:
    return T + timedelta(days=day)


def forecast(name="one", **kwargs) -> Forecast:
    args = {
        "forecast_id": name, "subject": name, "created_at": T, "source_ready": T,
        "artifact_ready": T, "target_start": time(1), "target_end": time(2),
        "artifact_sha256": "a" * 64, "input_sha256": "b" * 64, "target_sha256": "c" * 64,
        "probability": 0.8, "null_probability": 0.5, "stake": 1,
    }
    args.update(kwargs)
    return Forecast(**args)


def test_future_settlements_do_not_change_prior_scores_or_erase_abstentions_and_missing_labels() -> None:
    empty = ForecastJournal()
    pending = empty.append(forecast()).append(
        forecast("abstain", probability=None, stake=0, abstention_reason="unavailable source"))
    pending = pending.append(forecast("unresolved"))
    resolved = pending.append(Settlement("one", time(2), 1))
    resolved = resolved.append(Settlement("abstain", time(2), 0))
    assert resolved.score(time(1)) == pending.score(time(1))
    score = resolved.score(time(3))
    assert (score.forecasts, score.calls, score.abstentions, score.matured,
            score.unresolved_matured, score.scored) == (3, 2, 1, 3, 1, 1)
    assert score.mean_brier == pytest.approx(0.04)
    assert score.mean_log_loss == pytest.approx(-math.log(0.8))
    assert score.log_evalue == pytest.approx(math.log(1.5))
    assert empty.entries == () and pending.digest() != resolved.digest()


def test_conditional_binary_betting_losing_boundary_and_impossible_prediction_are_explicit() -> None:
    book = ForecastJournal().append(forecast(probability=1, stake=2))
    book = book.append(Settlement("one", time(2), 0))
    score = book.score(time(3))
    assert score.mean_brier == 1
    assert score.mean_log_loss == math.inf and score.log_evalue == -math.inf
    assert ForecastJournal().score(time(3)).mean_brier is None


def test_conditional_null_expectation_and_numeric_digest_are_well_defined() -> None:
    f = forecast(probability=np.float32(0.8), null_probability=0.2, stake=3)
    book = ForecastJournal().append(f)
    factors = [math.exp(book.append(Settlement("one", time(2), y)).score(time(3)).log_evalue)
               for y in (0, 1)]
    assert 0.8 * factors[0] + 0.2 * factors[1] == pytest.approx(1)
    assert 0.9 * factors[0] + 0.1 * factors[1] < 1
    assert len(book.digest()) == 64


def test_forecast_version_dates_target_reuse_and_settlement_order_are_enforced() -> None:
    f = forecast()
    for changes in (
        {"source_ready": time(0.5)}, {"artifact_ready": time(0.5)},
        {"target_start": T}, {"probability": None}, {"stake": 3},
        {"artifact_sha256": "short"}, {"created_at": T.replace(tzinfo=None)},
    ):
        with pytest.raises(ValueError):
            replace(f, **changes)
    book = ForecastJournal().append(f)
    with pytest.raises(ValueError, match="duplicate"):
        book.append(replace(f, forecast_id="same-target"))
    with pytest.raises(ValueError, match="before the target"):
        book.append(Settlement("one", time(1.5), 1))
    with pytest.raises(ValueError, match="existing"):
        book.append(Settlement("nonexistent", time(2), 1))
    done = book.append(Settlement("one", time(2), 1))
    with pytest.raises(ValueError, match="unsettled"):
        done.append(Settlement("one", time(3), 0))
    with pytest.raises(ValueError, match="backdated"):
        done.append(forecast("late", created_at=time(0.5), target_start=time(3), target_end=time(4)))
