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
