"""I: immutable in-memory forecast accounting, proper scores and conditional-Bernoulli bets.

Dates/hashes are declarations, not authenticated timestamps. This is not a data collector,
model runner, production journal or financial-return e-process.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from numbers import Integral

from asof.timeutil import aware_utc

from ._validation import scalar, text


def _digest_text(value: str, name: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError(f"{name} must be a full lowercase SHA256 digest")


@dataclass(frozen=True)
class Forecast:
    forecast_id: str
    subject: str
    created_at: datetime
    source_ready: datetime
    artifact_ready: datetime
    target_start: datetime
    target_end: datetime
    artifact_sha256: str
    input_sha256: str
    target_sha256: str
    probability: float | None
    null_probability: float
    stake: float
    abstention_reason: str | None = None

    def __post_init__(self) -> None:
        text(self.forecast_id, "forecast_id")
        text(self.subject, "subject")
        for name in ("created_at", "source_ready", "artifact_ready", "target_start", "target_end"):
            object.__setattr__(self, name, aware_utc(getattr(self, name), name))
        if not (max(self.source_ready, self.artifact_ready) <= self.created_at
                < self.target_start <= self.target_end):
            raise ValueError("sources/artifacts must be ready before a strictly future target")
        for name in ("artifact_sha256", "input_sha256", "target_sha256"):
            _digest_text(getattr(self, name), name)
        p0, stake = scalar(self.null_probability, "null_probability"), scalar(self.stake, "stake")
        if not 0 < p0 < 1 or stake < 0 or stake > 1 / p0:
            raise ValueError("Bernoulli null must be in (0,1), stake in [0,1/p0]")
        object.__setattr__(self, "null_probability", p0)
        object.__setattr__(self, "stake", stake)
        if self.probability is None:
            if self.abstention_reason is None or stake != 0:
                raise ValueError("abstentions require a reason and zero stake")
            text(self.abstention_reason, "abstention_reason")
        elif not 0 <= scalar(self.probability, "probability") <= 1:
            raise ValueError("probability must be in [0,1]")
        elif self.abstention_reason is not None:
            raise ValueError("a prediction cannot also be an abstention")
        else:
            object.__setattr__(self, "probability", scalar(self.probability, "probability"))


@dataclass(frozen=True)
class Settlement:
    forecast_id: str
    revealed_at: datetime
    outcome: int

    def __post_init__(self) -> None:
        text(self.forecast_id, "forecast_id")
        object.__setattr__(self, "revealed_at", aware_utc(self.revealed_at, "revealed_at"))
        if not isinstance(self.outcome, Integral) or self.outcome not in (0, 1):
            raise ValueError("settlement outcome must be binary")
        object.__setattr__(self, "outcome", int(self.outcome))


@dataclass(frozen=True)
class PrequentialScore:
    forecasts: int
    calls: int
    abstentions: int
    matured: int
    unresolved_matured: int
    scored: int
    mean_brier: float | None
    mean_log_loss: float | None
    log_evalue: float


@dataclass(frozen=True)
class ForecastJournal:
    entries: tuple[Forecast | Settlement, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise TypeError("journal entries must be an immutable tuple")
        forecasts: dict[str, Forecast] = {}
        targets = set()
        settled: set[str] = set()
        last: datetime | None = None
        for item in self.entries:
            if not isinstance(item, (Forecast, Settlement)):
                raise TypeError("journal entries must be Forecast or Settlement")
            at = item.created_at if isinstance(item, Forecast) else item.revealed_at
            if last is not None and at < last:
                raise ValueError("journal cannot append a backdated event")
            last = at
            if isinstance(item, Forecast):
                target = (item.subject, item.target_start, item.target_end, item.target_sha256)
                if item.forecast_id in forecasts or target in targets:
                    raise ValueError("duplicate forecast or target would reuse outcome evidence")
                forecasts[item.forecast_id] = item
                targets.add(target)
            else:
                if item.forecast_id not in forecasts or item.forecast_id in settled:
                    raise ValueError("settlement needs one existing, unsettled forecast")
                if item.revealed_at < forecasts[item.forecast_id].target_end:
                    raise ValueError("outcome cannot be revealed before the target ends")
                settled.add(item.forecast_id)

    def append(self, item: Forecast | Settlement) -> ForecastJournal:
        return ForecastJournal((*self.entries, item))

    def digest(self) -> str:
        payload = [{"kind": type(item).__name__, **asdict(item)} for item in self.entries]

        def encode(value: object) -> str:
            if isinstance(value, datetime):
                return value.isoformat()
            raise TypeError("unsupported journal field")

        return hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=encode).encode()).hexdigest()

    def score(self, as_of: datetime) -> PrequentialScore:
        """Missing/abstained labels remain in coverage; bets require conditional P(Y=1)<=p0.

        Stakes were committed before the target. Correlated/overlapping outcomes are NOT
        automatically covered: the stated conditional null must hold given earlier outcomes.
        Proper scores are descriptive, without confidence intervals or market inference.
        """
        cutoff = aware_utc(as_of, "as_of")
        forecasts = {item.forecast_id: item for item in self.entries
                     if isinstance(item, Forecast) and item.created_at <= cutoff}
        settlements = [item for item in self.entries
                       if isinstance(item, Settlement) and item.revealed_at <= cutoff]
        matured = {key for key, value in forecasts.items() if value.target_end <= cutoff}
        resolved = {item.forecast_id for item in settlements}
        brier, log_loss = [], []
        log_evalue = 0.0
        for item in settlements:
            forecast = forecasts[item.forecast_id]
            p = forecast.probability
            if p is None:
                continue
            brier.append((p - item.outcome) ** 2)
            correct_probability = p if item.outcome else 1 - p
            log_loss.append(-math.log(correct_probability) if correct_probability else math.inf)
            # The min only removes multiplication roundoff at the validated stake boundary.
            loss_fraction = min(1.0, forecast.stake * forecast.null_probability)
            factor = (1 + forecast.stake * (1 - forecast.null_probability)
                      if item.outcome else 1 - loss_fraction)
            log_evalue += math.log(factor) if factor else -math.inf
        calls = sum(item.probability is not None for item in forecasts.values())
        return PrequentialScore(
            len(forecasts), calls, len(forecasts) - calls, len(matured),
            len(matured - resolved), len(brier),
            sum(brier) / len(brier) if brier else None,
            sum(log_loss) / len(log_loss) if log_loss else None, log_evalue)
