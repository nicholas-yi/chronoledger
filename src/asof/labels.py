"""Future evidence-label validation; no automatic relabeling of historical outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal


@dataclass(frozen=True)
class LabelEvidence:
    endpoint: Literal["claim", "income_decline", "impairment", "formal_365d"]
    status: Literal["positive", "negative", "unknown", "censored"]
    value: bool | None
    evidence_refs: tuple[str, ...]
    reason: str | None = None
    positive_verified: bool = False
    observation_complete: bool = False
    followup_complete: bool = False
    explicit_zero: bool = False
    complete_statement: bool = False
    signal_time: datetime | None = None
    event_time: datetime | None = None
    observation_end: datetime | None = None


def validate_label(label: LabelEvidence) -> LabelEvidence:
    """Check declared evidence, not the truth/completeness of source documents."""
    if label.endpoint not in {"claim", "income_decline", "impairment", "formal_365d"}:
        raise ValueError("unknown endpoint")
    if label.status not in {"positive", "negative", "unknown", "censored"}:
        raise ValueError("unknown label status")
    if label.positive_verified and label.status != "positive":
        raise ValueError("verified positive evidence contradicts the supplied label status")
    if label.status in {"unknown", "censored"}:
        if label.value is not None or not label.reason or not label.reason.strip():
            raise ValueError("unknown/censored labels require null value and explicit reason")
        return label
    for value in (label.signal_time, label.event_time, label.observation_end):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("evidence timestamps must be timezone-aware")
    if not label.evidence_refs or any(not ref.strip() for ref in label.evidence_refs):
        raise ValueError("observed labels require evidence references")
    if label.status == "positive":
        if label.value is not True or not label.positive_verified:
            raise ValueError("positive label requires a verified positive and true value")
    else:
        if label.value is not False or not label.observation_complete:
            raise ValueError("negative label requires complete observation evidence")
        if label.endpoint == "formal_365d" and not label.followup_complete:
            raise ValueError("formal_365d negative requires complete follow-up")
        if label.endpoint == "impairment" and not (label.explicit_zero or label.complete_statement):
            raise ValueError("absent impairment tag is not zero without statement/zero evidence")
    if label.endpoint == "formal_365d":
        if label.signal_time is None:
            raise ValueError("formal_365d observed label requires signal_time")
        start = label.signal_time.astimezone(UTC)
        end = start + timedelta(days=365)
        event = None if label.event_time is None else label.event_time.astimezone(UTC)
        if label.status == "positive" and (event is None or not start < event <= end):
            raise ValueError("formal positive requires an event in (signal_time, signal_time+365d]")
        if label.status == "negative":
            if event is not None and start < event <= end:
                raise ValueError("negative contradicts an in-window qualifying event")
            if label.observation_end is None or label.observation_end.astimezone(UTC) < end:
                raise ValueError("negative observation envelope does not cover 365 days")
    return label
