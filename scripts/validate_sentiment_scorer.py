"""Measure a sentiment scorer on human-labelled finance text before any paid social data.

Declared before execution: VADER (vaderSentiment 3.3.2) with its standard thresholds,
compound >= 0.05 positive, <= -0.05 negative, otherwise neutral. Data: Financial PhraseBank
v1.0 (Malo et al. 2014; CC BY-NC-SA 3.0, kept under ignored ``data/``), sentences where
all annotators agreed and where at least half agreed. Reported against the majority-class
baseline. One shot; the receipt refuses to be overwritten.
"""

from __future__ import annotations

import json
from collections import Counter

from asof.config import DATA_DIR, PROJECT_ROOT
from asof.ledger import file_sha256
from asof.runtime import frozen_receipt, write_receipt
from asof.social import vader_scorer

ROOT = DATA_DIR / "raw" / "phrasebank" / "FinancialPhraseBank-v1.0"
RECEIPT = PROJECT_ROOT / "results" / "sentiment_scorer_validation.json"
LABELS = ("negative", "neutral", "positive")


def label(score: float) -> str:
    return "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"


def evaluate(rows: list[tuple[str, str]], scorer) -> dict:
    predicted = [label(scorer(text)) for text, _ in rows]
    truth = [gold for _, gold in rows]
    confusion = {g: dict(Counter(p for p, t in zip(predicted, truth, strict=True) if t == g)) for g in LABELS}
    f1 = {}
    for name in LABELS:
        tp = sum(p == t == name for p, t in zip(predicted, truth, strict=True))
        precision = tp / max(1, predicted.count(name))
        recall = tp / max(1, truth.count(name))
        f1[name] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    polar = [(p, t) for p, t in zip(predicted, truth, strict=True) if t != "neutral" and p != "neutral"]
    majority = Counter(truth).most_common(1)[0]
    return {"n": len(rows), "accuracy": sum(p == t for p, t in zip(predicted, truth, strict=True)) / len(rows),
            "macro_F1": sum(f1.values()) / 3, "F1": f1,
            "majority_class": majority[0], "majority_baseline_accuracy": majority[1] / len(rows),
            "polar_sign_agreement": sum(p == t for p, t in polar) / len(polar) if polar else None,
            "polar_pairs": len(polar), "gold_counts": dict(Counter(truth)), "confusion_gold_to_predicted": confusion}


def load(name: str) -> list[tuple[str, str]]:
    rows = []
    for line in (ROOT / name).read_text(encoding="latin-1").splitlines():
        text, _, gold = line.rpartition("@")
        if gold.strip() in LABELS:
            rows.append((text.strip(), gold.strip()))
    return rows


def main() -> None:
    if RECEIPT.exists():
        raise RuntimeError("scorer validation already recorded; preserve it")
    freeze = frozen_receipt(PROJECT_ROOT, ("scripts/validate_sentiment_scorer.py", "src/asof/social.py"))
    scorer = vader_scorer()
    write_receipt(RECEIPT, {
        "scope": "VADER on Financial PhraseBank v1.0; scorer qualification before any social-media data",
        **freeze, "declared_rule": __doc__.split("Declared before execution:")[1].strip(),
        "data_SHA256": {name: file_sha256(ROOT / name) for name in ("Sentences_AllAgree.txt", "Sentences_50Agree.txt")},
        "all_agree": evaluate(load("Sentences_AllAgree.txt"), scorer),
        "at_least_half_agree": evaluate(load("Sentences_50Agree.txt"), scorer),
        "limits": "PhraseBank sentences are news and press-release text, not posts; this measures finance "
                  "vocabulary handling, not accuracy on X posts. Data stay local under the CC BY-NC-SA licence.",
    })
    print(json.dumps({k: {m: v for m, v in json.loads(RECEIPT.read_text())[k].items()
                          if m in ("n", "accuracy", "macro_F1", "majority_baseline_accuracy", "polar_sign_agreement")}
                      for k in ("all_agree", "at_least_half_agree")}, indent=1))


if __name__ == "__main__":
    main()
