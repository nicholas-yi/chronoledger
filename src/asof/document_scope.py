"""D13 pre-body calendar gate. Declared dates are not source-clock certification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from asof.periods import HoldoutAccessError

type DateValue = str | date | datetime | None
DEVELOPMENT_START = date(2012, 1, 1)
DEVELOPMENT_END = date(2018, 12, 31)


@dataclass(frozen=True)
class DocumentDates:
    accepted_at: DateValue
    knowledge_at: DateValue
    period_end: DateValue
    contexts: tuple[DocumentDates, ...] = ()


def parse_document_date(value: DateValue, field: str) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise HoldoutAccessError(f"{field}: naive timestamp is not qualified date metadata")
        return value.astimezone(UTC).date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise HoldoutAccessError(f"{field}: unknown date; no body access")
    text = " ".join(value.split())
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        timestamp = datetime.fromisoformat(text)
    except ValueError:
        timestamp = None
    if timestamp is not None:
        return parse_document_date(timestamp, field)
    for pattern in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise HoldoutAccessError(f"{field}: unparseable date; no body access")


def require_eligible_documents(documents: Sequence[DocumentDates] | None) -> None:
    """Allow only fully dated 2012-2018 documents/context; no holdout override.

    The development whitelist conservatively rejects validation, H4/H6 holdouts,
    D1 return holdout and follow-up sources, including late outcome filings for
    which no finite H4 availability endpoint can safely be assumed.
    """
    if documents is None or not documents:
        raise HoldoutAccessError("D13 requires dated documents before any body read or fingerprint")
    for document in documents:
        if not isinstance(document, DocumentDates):
            raise HoldoutAccessError("D13 requires complete typed document/context dates")
        values = {
            "acceptance": parse_document_date(document.accepted_at, "acceptance"),
            "knowledge": parse_document_date(document.knowledge_at, "knowledge"),
            "period_end": parse_document_date(document.period_end, "period_end"),
        }
        for field, value in values.items():
            if not DEVELOPMENT_START <= value <= DEVELOPMENT_END:
                raise HoldoutAccessError(
                    f"{field} {value}: outside D13 development-only source envelope; "
                    "H4/H6 validation/holdout, follow-ups and D1 return reservations "
                    "cannot be cleared by a price cutoff")
        if values["knowledge"] < values["acceptance"]:
            raise HoldoutAccessError("knowledge date precedes acceptance")
        if values["period_end"] > min(values["acceptance"], values["knowledge"]):
            raise HoldoutAccessError("period end follows availability")
        if document.contexts:
            require_eligible_documents(document.contexts)


def filing_document_dates(row: Mapping) -> DocumentDates:
    """No implicit acceptance/knowledge alias: the ingesting caller declares both."""
    return DocumentDates(row.get("accepted_at"), row.get("knowledge_time"), row.get("report_date"))
