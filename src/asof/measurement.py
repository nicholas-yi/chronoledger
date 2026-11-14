"""Evidence-linked exact-ID measurement evaluation, not semantic labeling or return testing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal


@dataclass(frozen=True)
class MeasurementCase:
    case_id: str
    issuer_id: str
    split: Literal["train", "validation", "test"]
    knowledge_time: datetime
    gold: frozenset[str] | None
    prediction: frozenset[str] | None
    gold_refs: tuple[str, ...] = ()
    prediction_refs: tuple[str, ...] = ()
    gold_verified: bool = False
    gold_complete: bool = False
    gold_reason: str | None = None
    abstention_reason: str | None = None


@dataclass(frozen=True)
class MeasurementScore:
    cases: int
    scored_cases: int
    gold_unknown_cases: int
    gold_unverified_cases: int
    gold_incomplete_cases: int
    scored_predictions: int
    scored_abstentions: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float | None
    recall: float | None
    prediction_coverage: float | None
    exact_match_accuracy: float | None
    selective_exact_match_accuracy: float | None


def _utc(time: datetime) -> datetime:
    if not isinstance(time, datetime) or time.tzinfo is None or time.utcoffset() is None:
        raise ValueError("measurement knowledge_time and split bounds must be timezone-aware")
    return time.astimezone(UTC)


def validate_measurement_case(case: MeasurementCase) -> MeasurementCase:
    if not case.case_id.strip() or not case.issuer_id.strip():
        raise ValueError("nonempty case and issuer identities required")
    if case.split not in ("train", "validation", "test"):
        raise ValueError("unknown measurement partition")
    _utc(case.knowledge_time)
    if not isinstance(case.gold_verified, bool) or not isinstance(case.gold_complete, bool):
        raise TypeError("gold verification/completeness must be explicit booleans")
    for values in (case.gold, case.prediction):
        if values is not None and (not isinstance(values, frozenset)
                                   or any(not isinstance(v, str) or not v.strip() for v in values)):
            raise ValueError("gold/prediction must be explicit immutable sets of nonempty claim IDs")
    if any(not ref.strip() for ref in (*case.gold_refs, *case.prediction_refs)):
        raise ValueError("evidence references must be nonempty")
    if case.gold is None:
        if (case.gold_verified or case.gold_complete or not case.gold_reason
                or not case.gold_reason.strip()):
            raise ValueError("unknown gold needs a reason, not verification/completeness")
    elif case.gold_verified and not case.gold_refs:
        raise ValueError("verified gold requires evidence references")
    if case.prediction is None:
        if not case.abstention_reason or not case.abstention_reason.strip():
            raise ValueError("an abstention requires a reason; it is not an empty negative prediction")
    else:
        if case.abstention_reason is not None:
            raise ValueError("emitted prediction cannot also be an abstention")
        if case.prediction and not case.prediction_refs:
            raise ValueError("positive predicted claim IDs require evidence references")
    return case


def validate_measurement_splits(
    cases: Sequence[MeasurementCase], *, train_end: datetime,
    validation_end: datetime, test_end: datetime,
) -> None:
    """Issuer-disjoint partitions and half-open chronological bounds; no split inferred."""
    boundaries = tuple(_utc(t) for t in (train_end, validation_end, test_end))
    if not boundaries[0] < boundaries[1] < boundaries[2]:
        raise ValueError("split boundaries must be strictly increasing")
    seen_cases = set()
    issuer_splits: dict[str, str] = {}
    for case in cases:
        validate_measurement_case(case)
        if case.case_id in seen_cases:
            raise ValueError(f"duplicate measurement case: {case.case_id}")
        seen_cases.add(case.case_id)
        previous = issuer_splits.setdefault(case.issuer_id, case.split)
        if previous != case.split:
            raise ValueError(f"issuer appears across measurement partitions: {case.issuer_id}")
        t = _utc(case.knowledge_time)
        valid = (t < boundaries[0] if case.split == "train" else
                 boundaries[0] <= t < boundaries[1] if case.split == "validation"
                 else boundaries[1] <= t < boundaries[2])
        if not valid:
            raise ValueError(f"case violates its chronological partition: {case.case_id}")


def score_measurement(cases: Sequence[MeasurementCase]) -> MeasurementScore:
    """Micro counts over complete, declared-verified gold; abstentions retain false negatives.

    This tests exact supplied claim IDs, not semantic matching, source truth or annotation
    independence. Unknown/unverified/incomplete gold stays outside accuracy denominators
    with explicit counts. No default 100% precision when no claims were emitted.
    """
    if len({c.case_id for c in cases}) != len(cases):
        raise ValueError("duplicate measurement cases would inflate denominators")
    scored = unknown = unverified = incomplete = predictions = abstentions = 0
    tp = fp = fn = exact = 0
    for case in cases:
        validate_measurement_case(case)
        if case.gold is None:
            unknown += 1
            continue
        if not case.gold_verified:
            unverified += 1
            continue
        if not case.gold_complete:
            incomplete += 1
            continue
        scored += 1
        if case.prediction is None:
            abstentions += 1
            fn += len(case.gold)
            continue
        predictions += 1
        tp += len(case.gold & case.prediction)
        fp += len(case.prediction - case.gold)
        fn += len(case.gold - case.prediction)
        exact += case.gold == case.prediction
    return MeasurementScore(
        len(cases), scored, unknown, unverified, incomplete, predictions, abstentions,
        tp, fp, fn, tp / (tp + fp) if tp + fp else None,
        tp / (tp + fn) if tp + fn else None,
        predictions / scored if scored else None, exact / scored if scored else None,
        exact / predictions if predictions else None)
