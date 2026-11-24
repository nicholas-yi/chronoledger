"""Lifecycle tests with known end states, plus time invariance and an append-only ablation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from asof.extraction import Link
from asof.reconcile import FilingEvent, append_only, normalize_partner, reconcile

T0 = datetime(2023, 2, 1, tzinfo=UTC)


def L(partner: str, pct: float | None = None, rel: str = "customer") -> Link:
    return Link(partner, rel, pct, f"{partner} accounted for {pct}% of revenue.")


def K(accession: str, days: int, *links: Link, reporter: int = 1) -> FilingEvent:
    return FilingEvent(accession, reporter, "10-K", T0 + timedelta(days=days), tuple(links))


def A(accession: str, days: int, amends: str, *links: Link, restates: bool = True) -> FilingEvent:
    return FilingEvent(accession, 1, "10-K/A", T0 + timedelta(days=days), tuple(links),
                       amends=amends, restates_section=restates)


KEY = (1, "veltrona systems", "customer")


def test_partner_normalization() -> None:
    assert normalize_partner("The Veltrona Systems, Inc.") == "veltrona systems"
    assert normalize_partner("Veltrona Systems Corp") == "veltrona systems"


def test_repeated_evidence_extends_support() -> None:
    snap = reconcile([K("a", 0, L("Veltrona Systems", 12)), K("b", 365, L("Veltrona Systems Inc.", 13))])
    assert snap.links[KEY].support == {"a", "b"}
    assert KEY in snap.current()
    assert snap.revenue_pct(KEY) == 13


def test_not_reaffirmed_is_historical_not_current() -> None:
    snap = reconcile([K("a", 0, L("Veltrona Systems", 12)), K("b", 365)])
    assert snap.links[KEY].supported
    assert KEY not in snap.current()


def test_amendment_retracts_unsupported_link() -> None:
    snap = reconcile([K("a", 0, L("Veltrona Systems", 12)), A("a1", 30, "a")])
    assert not snap.links[KEY].supported
    assert KEY not in snap.current()


def test_amendment_preserves_link_with_remaining_support() -> None:
    events = [K("a", 0, L("Veltrona Systems", 12)), K("b", 365, L("Veltrona Systems", 12)),
              A("b1", 400, "b")]
    snap = reconcile(events)
    assert snap.links[KEY].support == {"a"}
    assert KEY not in snap.current()  # latest effective annual (b1) no longer states it


def test_partial_amendment_changes_nothing() -> None:
    events = [K("a", 0, L("Veltrona Systems", 12)), A("a1", 30, "a", restates=False)]
    snap = reconcile(events)
    assert snap.links[KEY].support == {"a"}
    assert KEY in snap.current()


def test_amendment_supersedes_percentage_with_history() -> None:
    events = [K("a", 0, L("Veltrona Systems", 12)), A("a1", 30, "a", L("Veltrona Systems", 15))]
    before = reconcile(events, T0 + timedelta(days=10))
    after = reconcile(events, T0 + timedelta(days=40))
    assert before.revenue_pct(KEY) == 12
    assert after.revenue_pct(KEY) == 15
    assert [p for _, _, p in after.links[KEY].pct_history] == [12, 15]


def test_chained_amendments_resolve_to_latest() -> None:
    events = [K("a", 0, L("Veltrona Systems", 12)), A("a1", 30, "a", L("Veltrona Systems", 15)),
              A("a2", 60, "a", L("Veltrona Systems", 16))]
    snap = reconcile(events)
    assert snap.links[KEY].support == {"a2"}
    assert snap.revenue_pct(KEY) == 16


def test_append_only_ablation_keeps_stale_state() -> None:
    events = [K("a", 0, L("Veltrona Systems", 12)), A("a1", 30, "a")]
    as_of = T0 + timedelta(days=60)
    assert not reconcile(events, as_of).links[KEY].supported
    assert (KEY, 12) in append_only(events, as_of)  # retracted link still looks active


ev_strategy = st.lists(
    st.tuples(st.integers(0, 2000), st.sampled_from(["Veltrona", "Orbique", "Calduran"]),
              st.integers(10, 40), st.booleans(), st.booleans()),
    min_size=1, max_size=25,
)


@settings(max_examples=80, deadline=None)
@given(ev_strategy, st.integers(-10, 2100))
def test_reconcile_is_time_invariant(raw, day) -> None:
    events: list[FilingEvent] = []
    originals: list[str] = []
    for i, (d, partner, pct, is_amend, restates) in enumerate(raw):
        acc = f"f{i}"
        if is_amend and originals:
            events.append(A(acc, d + 1, originals[-1], L(partner, pct), restates=restates))
        else:
            events.append(K(acc, d, L(partner, pct)))
            originals.append(acc)
    as_of = T0 + timedelta(days=day)
    full = reconcile(events, as_of)
    truncated = reconcile([e for e in events if e.knowledge_time <= as_of], as_of)
    assert {k: (s.support, s.pct_history) for k, s in full.links.items()} == {
        k: (s.support, s.pct_history) for k, s in truncated.links.items()
    }
    assert full.latest_annual == truncated.latest_annual
