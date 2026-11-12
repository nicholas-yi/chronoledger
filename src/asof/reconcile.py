"""Provenance-based reconciliation of extracted relationships across filings.

Each relationship key (reporter, partner, relation) carries a support set: the effective filings
that assert it. Rules, applied in knowledge-time order:

* An original 10-K adds itself to the support of every link it states (repeated evidence extends
  support) and becomes the reporter's latest annual snapshot.
* A 10-K/A that restates the relevant section replaces the amended filing: the original is removed
  from every support set and the amendment is added for the links it states. Links left with
  empty support are retracted; links supported by other filings survive.
* A 10-K/A that does not restate the section (e.g. Part III only) changes nothing.
* Revenue percentages are versioned: a newer effective statement supersedes an older one, and the
  full history is kept.

``as_of`` reads only events known by the as-of instant, so it is invariant by construction; this is
also property-tested. The design follows the episode-provenance reconciliation idea in
arXiv:2609.34242, re-implemented from the public description for filings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from asof.extraction import Link

_SUFFIX = re.compile(
    r"\b(incorporated|inc|corporation|corp|company|co|limited|ltd|llc|plc|lp|l\.p|sa|ag|nv|"
    r"holdings?|group)\b\.?"
)


def normalize_partner(name: str) -> str:
    n = name.lower().replace("&", " and ")
    n = re.sub(r"^the\s+", "", n)
    n = _SUFFIX.sub(" ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


@dataclass(frozen=True)
class FilingEvent:
    accession: str
    reporter: int
    form: str  # "10-K" or "10-K/A"
    knowledge_time: datetime
    links: tuple[Link, ...]
    amends: str | None = None
    restates_section: bool = True


Key = tuple[int, str, str]


@dataclass
class LinkState:
    key: Key
    support: set[str] = field(default_factory=set)
    pct_history: list[tuple[datetime, str, float | None]] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)

    @property
    def supported(self) -> bool:
        return bool(self.support)


@dataclass
class Snapshot:
    links: dict[Key, LinkState]
    latest_annual: dict[int, str]

    def current(self) -> dict[Key, LinkState]:
        """Links asserted by each reporter's latest effective annual report."""
        return {
            k: s for k, s in self.links.items()
            if self.latest_annual.get(k[0]) in s.support
        }

    def revenue_pct(self, key: Key) -> float | None:
        state = self.links.get(key)
        if not state:
            return None
        live = [(t, acc, p) for t, acc, p in state.pct_history if acc in state.support]
        return live[-1][2] if live else None


def _key(reporter: int, link: Link) -> Key:
    return (reporter, normalize_partner(link.partner), link.relation)


def reconcile(events: list[FilingEvent], as_of: datetime | None = None) -> Snapshot:
    if as_of is not None and as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    known = [e for e in events if as_of is None or e.knowledge_time <= as_of]
    known.sort(key=lambda e: (e.knowledge_time, e.accession))
    links: dict[Key, LinkState] = {}
    latest_annual: dict[int, str] = {}
    replaced: dict[str, str] = {}  # original accession -> effective replacement

    def effective(acc: str) -> str:
        while acc in replaced:
            acc = replaced[acc]
        return acc

    for ev in known:
        if ev.form == "10-K/A":
            if not ev.amends or not ev.restates_section:
                continue
            target = effective(ev.amends)
            for state in links.values():
                state.support.discard(target)
            replaced[target] = ev.accession
            if latest_annual.get(ev.reporter) == target:
                latest_annual[ev.reporter] = ev.accession
        else:
            latest_annual[ev.reporter] = ev.accession
        for link in ev.links:
            k = _key(ev.reporter, link)
            state = links.setdefault(k, LinkState(k))
            state.support.add(ev.accession)
            state.evidence[ev.accession] = link.evidence
            state.pct_history.append((ev.knowledge_time, ev.accession, link.revenue_pct))
    return Snapshot(links, latest_annual)


def append_only(events: list[FilingEvent], as_of: datetime) -> list[tuple[Key, float | None]]:
    """Ablation baseline without reconciliation: every statement ever made stays active."""
    out = []
    for ev in sorted(events, key=lambda e: e.knowledge_time):
        if ev.knowledge_time <= as_of:
            out += [(_key(ev.reporter, ln), ln.revenue_pct) for ln in ev.links]
    return out
