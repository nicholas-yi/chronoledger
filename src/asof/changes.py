"""Claim-level change between consecutive annual reports (hypothesis H1).

Risk-factor sections are split into paragraph-level claims. Each year's claims are matched to the
previous year's by cosine similarity of *centered* ChronoBERT embeddings (raw mean-pooled MLM
embeddings are highly anisotropic: unrelated risks score ~0.97). Unmatched current claims are
new; unmatched prior claims are removed. The threshold is calibrated on synthetic edit/negative
pairs only, never on returns.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import numpy as np

EmbedFn = Callable[[list[str]], np.ndarray]


def paragraphs(section_text: str, min_chars: int = 150) -> list[str]:
    """Split into paragraphs, attaching short heading lines to the paragraph that follows."""
    out: list[str] = []
    pending = ""
    for line in (ln.strip() for ln in section_text.split("\n")):
        if not line:
            continue
        if len(line) < min_chars:
            pending = f"{pending} {line}".strip()
            continue
        out.append(f"{pending} {line}".strip() if pending else line)
        pending = ""
    return out


def center(emb: np.ndarray, mean: np.ndarray) -> np.ndarray:
    x = emb - mean
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.clip(norms, 1e-12, None)


@dataclass(frozen=True)
class ChangeScore:
    new_share: float
    removed_share: float
    n_current: int
    n_previous: int

    @property
    def score(self) -> float:
        return 0.5 * (self.new_share + self.removed_share)


def claim_change(
    previous: list[str], current: list[str], embed_fn: EmbedFn, mean: np.ndarray, tau: float
) -> ChangeScore:
    if not previous or not current:
        return ChangeScore(float("nan"), float("nan"), len(current), len(previous))
    p = center(embed_fn(previous), mean)
    c = center(embed_fn(current), mean)
    sim = c @ p.T
    cur_len = np.array([len(x) for x in current], dtype=float)
    prev_len = np.array([len(x) for x in previous], dtype=float)
    new = sim.max(axis=1) < tau
    removed = sim.max(axis=0) < tau
    return ChangeScore(
        float(cur_len[new].sum() / cur_len.sum()),
        float(prev_len[removed].sum() / prev_len.sum()),
        len(current),
        len(previous),
    )


def light_edit(text: str, rng: random.Random) -> str:
    """Year-over-year boilerplate update: shift years and numbers, maybe drop/duplicate a sentence."""
    text = re.sub(r"\b(20\d\d)\b", lambda m: str(int(m.group(1)) + 1), text)
    text = re.sub(r"\b(\d{1,3})(%| percent)", lambda m: f"{int(m.group(1)) + rng.randint(-3, 3)}{m.group(2)}", text)
    sents = re.split(r"(?<=[\.\!\?])\s+", text)
    if len(sents) > 2 and rng.random() < 0.5:
        sents.pop(rng.randrange(len(sents)))
    return " ".join(sents)


def calibration_pairs(
    paras_by_firm: dict[int, list[str]], n: int, seed: int = 0
) -> list[tuple[str, str, int]]:
    """(a, b, label): 1 = same claim lightly edited; 0 = different claim (same firm or other firm)."""
    rng = random.Random(seed)
    firms = [f for f, ps in paras_by_firm.items() if len(ps) >= 2]
    pairs = []
    for _ in range(n):
        f = rng.choice(firms)
        a = rng.choice(paras_by_firm[f])
        pairs.append((a, light_edit(a, rng), 1))
        if rng.random() < 0.5:
            b = rng.choice([x for x in paras_by_firm[f] if x != a])
        else:
            g = rng.choice([x for x in firms if x != f] or [f])
            b = rng.choice(paras_by_firm[g])
        pairs.append((a, b, 0))
    return pairs


def calibrate_tau(sims: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Threshold maximizing balanced accuracy; returns (tau, balanced_accuracy)."""
    best = (0.0, 0.0)
    for tau in np.unique(sims):
        pred = sims >= tau
        tpr = (pred & (labels == 1)).sum() / max((labels == 1).sum(), 1)
        tnr = (~pred & (labels == 0)).sum() / max((labels == 0).sum(), 1)
        bal = 0.5 * (tpr + tnr)
        if bal > best[1]:
            best = (float(tau), float(bal))
    return best


# ----------------------------------------------------------- leak-proof TF-IDF (deviation D3)


class AsOfTfidf:
    """TF-IDF whose vocabulary and IDF come only from documents public by ``as_of``.

    Bag-of-words weights cannot encode anything not present in the fitting corpus, so restricting
    the corpus by knowledge time makes the representation leak-proof by construction.
    """

    def __init__(self, min_df: int = 2, max_features: int = 20_000) -> None:
        self.min_df = min_df
        self.max_features = max_features
        self.vocab: dict[str, int] = {}
        self.idf = np.zeros(0)

    def fit(self, docs: list[tuple[datetime, str]], as_of: datetime) -> AsOfTfidf:
        from collections import Counter

        from asof.sections import tokens

        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        known = [text for t, text in docs if t <= as_of]
        df: Counter[str] = Counter()
        for text in known:
            df.update(set(tokens(text)))
        terms = sorted((w for w, c in df.items() if c >= self.min_df), key=lambda w: (-df[w], w))
        terms = sorted(terms[: self.max_features])
        self.vocab = {w: i for i, w in enumerate(terms)}
        n = len(known)
        self.idf = np.array([np.log((1 + n) / (1 + df[w])) + 1.0 for w in terms])
        return self

    def transform(self, texts: list[str]) -> np.ndarray:
        from asof.sections import tokens

        out = np.zeros((len(texts), len(self.vocab)))
        for i, text in enumerate(texts):
            for w in tokens(text):
                j = self.vocab.get(w)
                if j is not None:
                    out[i, j] += 1.0
        out *= self.idf
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.clip(norms, 1e-12, None)
