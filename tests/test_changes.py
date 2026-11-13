import random

import numpy as np
import pytest

from asof.changes import (
    calibrate_tau,
    calibration_pairs,
    claim_change,
    light_edit,
    paragraphs,
)


def test_paragraphs_attach_headings() -> None:
    text = "Supply Risks\n" + "We depend on suppliers. " * 10 + "\nTax\n" + "Tax laws may change. " * 10
    ps = paragraphs(text)
    assert len(ps) == 2 and ps[0].startswith("Supply Risks") and ps[1].startswith("Tax")


def _bow_embed(texts: list[str]) -> np.ndarray:
    vocab = sorted({w for t in texts for w in t.lower().split()} | {"x"})
    m = np.array([[t.lower().split().count(w) for w in vocab] for t in texts], dtype=float)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def test_claim_change_detects_new_and_removed() -> None:
    a = "alpha beta gamma delta " * 5
    b = "epsilon zeta eta theta " * 5
    c = "iota kappa lambda mu " * 5
    allv = [a, b, c]
    full = _bow_embed(allv)  # one shared vocabulary so dimensions align
    lookup = {t: full[i] for i, t in enumerate(allv)}
    embed = lambda xs: np.array([lookup[x] for x in xs])  # noqa: E731
    mean = np.zeros(full.shape[1])
    s = claim_change([a, b], [a, c], embed, mean, tau=0.9)
    # Shares are weighted by paragraph length.
    assert s.new_share == pytest.approx(len(c) / (len(a) + len(c)))
    assert s.removed_share == pytest.approx(len(b) / (len(a) + len(b)))
    same = claim_change([a, b], [a, b], embed, mean, tau=0.9)
    assert same.score == 0.0


def test_light_edit_shifts_years() -> None:
    out = light_edit("In 2023 revenue rose. Costs fell. Margins held.", random.Random(0))
    assert "2024" in out and "2023" not in out


def test_calibration_pairs_balanced() -> None:
    paras = {1: ["a " * 50, "b " * 50, "c " * 50], 2: ["d " * 50, "e " * 50]}
    pairs = calibration_pairs(paras, 40)
    labels = [p[2] for p in pairs]
    assert labels.count(1) == labels.count(0) == 40


def test_calibrate_tau_separates() -> None:
    sims = np.array([0.9, 0.85, 0.8, 0.3, 0.2, 0.1])
    labels = np.array([1, 1, 1, 0, 0, 0])
    tau, bal = calibrate_tau(sims, labels)
    assert 0.3 < tau <= 0.8 and bal == 1.0


def test_tfidf_ignores_documents_after_as_of() -> None:
    from datetime import datetime, timedelta, timezone

    from hypothesis import given, settings
    from hypothesis import strategies as st

    from asof.changes import AsOfTfidf

    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    words = ["supply", "risk", "tariff", "cyber", "labor", "demand", "pandemic", "credit"]

    @settings(max_examples=40, deadline=None)
    @given(st.lists(st.tuples(st.integers(0, 900), st.lists(st.sampled_from(words), min_size=1, max_size=12)),
                    min_size=1, max_size=30), st.integers(0, 1000))
    def check(raw, day):
        docs = [(t0 + timedelta(days=d), " ".join(ws)) for d, ws in raw]
        as_of = t0 + timedelta(days=day)
        full = AsOfTfidf(min_df=1).fit(docs, as_of)
        trunc = AsOfTfidf(min_df=1).fit([x for x in docs if x[0] <= as_of], as_of)
        assert full.vocab == trunc.vocab
        assert np.allclose(full.idf, trunc.idf)
        probe = ["supply risk tariff", "cyber pandemic"]
        assert np.allclose(full.transform(probe), trunc.transform(probe))

    check()


def test_tfidf_future_only_word_is_unknown() -> None:
    from datetime import datetime, timezone

    from asof.changes import AsOfTfidf

    docs = [(datetime(2019, 6, 1, tzinfo=timezone.utc), "supply risk"),
            (datetime(2020, 6, 1, tzinfo=timezone.utc), "pandemic risk")]
    vec = AsOfTfidf(min_df=1).fit(docs, datetime(2019, 12, 31, tzinfo=timezone.utc))
    assert "pandemic" not in vec.vocab
    assert np.allclose(vec.transform(["pandemic"]), 0.0)
