"""D: dated economic exposure and similarity are distinct in-memory operators."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike

from asof.timeutil import aware_utc

from ._validation import FloatArray, matrix, readonly, scalar, text, vector

Relation = Literal["customer_revenue", "supplier_cost", "creditor_assets"]


@dataclass(frozen=True)
class ExposureEdge:
    affected: str
    counterparty: str
    relation: Relation
    fraction: float | None
    period_end: date
    known_at: datetime
    source_id: str
    explicitly_stated: bool = True

    def __post_init__(self) -> None:
        for name in ("affected", "counterparty", "source_id"):
            text(getattr(self, name), name)
        if self.affected == self.counterparty:
            raise ValueError("self exposure is not a bilateral edge")
        if self.relation not in ("customer_revenue", "supplier_cost", "creditor_assets"):
            raise ValueError("unknown economic exposure type")
        if self.fraction is not None and not 0 <= scalar(self.fraction, "fraction") <= 1:
            raise ValueError("economic fraction must lie in [0,1]")
        if not isinstance(self.period_end, date) or isinstance(self.period_end, datetime):
            raise TypeError("period_end must be a date")
        known = aware_utc(self.known_at, "known_at")
        if self.period_end > known.date():
            raise ValueError("period end cannot follow availability")
        object.__setattr__(self, "known_at", known)
        if not isinstance(self.explicitly_stated, bool):
            raise TypeError("explicitly_stated must be a boolean")


@dataclass(frozen=True)
class ExposurePanel:
    nodes: tuple[str, ...]
    values: FloatArray
    unknown_pairs: tuple[tuple[str, str], ...]


def exposure_panel(
    nodes: Sequence[str], edges: Sequence[ExposureEdge], *, as_of: datetime,
    period_end: date, relation: Relation, complete_rows: frozenset[str],
) -> ExposurePanel:
    """A[i,j] is a dated fraction of affected i exposed to counterparty j.

    Completeness is supplied, not authenticated. Uncovered pairs/unknown fractions stay
    unknown; no renormalization, symmetrization, IDF or confidence weighting is applied.
    """
    identities = tuple(text(node, "node") for node in nodes)
    if not identities or len(set(identities)) != len(identities):
        raise ValueError("a nonempty unique node universe is required")
    if not isinstance(complete_rows, frozenset) or not complete_rows <= set(identities):
        raise ValueError("explicit complete_rows must be a subset of nodes")
    if relation not in ("customer_revenue", "supplier_cost", "creditor_assets"):
        raise ValueError("unknown exposure relation")
    if not isinstance(period_end, date) or isinstance(period_end, datetime):
        raise TypeError("period_end must be a date")
    cutoff = aware_utc(as_of, "as_of")
    index = {name: i for i, name in enumerate(identities)}
    values = np.full((len(index), len(index)), np.nan)
    for node in complete_rows:
        values[index[node], :] = 0
    np.fill_diagonal(values, 0)
    latest: dict[tuple[str, str], ExposureEdge] = {}
    for edge in sorted(edges, key=lambda e: e.known_at):
        if edge.known_at > cutoff or edge.period_end != period_end or edge.relation != relation:
            continue
        if edge.affected not in index or edge.counterparty not in index:
            raise ValueError("eligible counterparty lies outside the declared node universe")
        if not edge.explicitly_stated:
            raise ValueError("model-inferred identities cannot establish an exposure coefficient")
        pair = (edge.affected, edge.counterparty)
        old = latest.get(pair)
        if old is not None and old.known_at == edge.known_at and old.fraction != edge.fraction:
            raise ValueError("simultaneous conflicting economic exposure")
        latest[pair] = edge
    for (affected, counterparty), edge in latest.items():
        values[index[affected], index[counterparty]] = (
            edge.fraction if edge.fraction is not None else np.nan)
    if (np.nansum(values, axis=1) > 1 + 1e-12).any():
        raise ValueError("fractions with the same denominator cannot exceed one")
    unknown = tuple((identities[i], identities[j]) for i, j in zip(*np.where(np.isnan(values)),
                                                                  strict=True))
    return ExposurePanel(identities, readonly(values), unknown)


def _qualified(panel: ExposurePanel) -> FloatArray:
    if panel.unknown_pairs:
        raise ValueError("unknown economic exposure is not zero; propagation is unavailable")
    return matrix(panel.values, "exposure", (len(panel.nodes), len(panel.nodes)))


def one_hop(panel: ExposurePanel, shock: ArrayLike) -> FloatArray:
    return readonly(_qualified(panel) @ vector(shock, "shock", len(panel.nodes)))


def leontief_total(panel: ExposurePanel, shock: ArrayLike) -> FloatArray:
    """Solve (I-A)^(-1)z, including the direct shock, under an explicitly stable linear model."""
    a = _qualified(panel)
    z = vector(shock, "shock", len(panel.nodes))
    if np.max(np.abs(np.linalg.eigvals(a))) >= 1:
        raise ValueError("linear propagation is not stable")
    result = np.linalg.solve(np.eye(len(z)) - a, z)
    if not np.isfinite(result).all():
        raise FloatingPointError("nonfinite propagated shock")
    return readonly(result)


def shared_counterparty_similarity(incidence: ArrayLike) -> FloatArray:
    """IDF-weighted cosine on a complete binary incidence matrix, not economic exposure."""
    present = matrix(incidence, "incidence")
    if not np.isin(present, [0, 1]).all():
        raise ValueError("similarity incidence must be binary, not economic/confidence weights")
    idf = np.log((1 + len(present)) / (1 + present.sum(axis=0))) + 1
    weighted = present * idf
    norms = np.linalg.norm(weighted, axis=1)
    if (norms == 0).any():
        raise ValueError("similarity is undefined for an empty counterparty row")
    normalized = weighted / norms[:, None]
    return readonly(normalized @ normalized.T)
