"""Fresh source-integrity challenge, frozen with its baseline before the integrity/dispute guards exist.

Every attack keeps the original fact sentence byte-identical and adds or alters surrounding text, so the
expected verdict follows from the declared policy rather than from re-reading the fact.
"""

from __future__ import annotations

import re
from collections import Counter

from asof.claim_verifier import verify_claim

NOTATION = (
    ("FictionQuill's turnover reached GBP26m during FY2016.", "FictionQuill's 2016 revenue was 26 GBP million."),
    ("Fiction Harbor said its top line came to forty-two million US dollars in 2018.",
     "Fiction Harbor's 2018 revenue was 42 USD million."),
    ("FictionMoss's revenue totalled \u20ac4.5bn for fiscal 2019.", "FictionMoss's 2019 revenue was 4.5 EUR billion."),
    ("FictionVale's top-line amounted to USD 780k in FY 2014.", "FictionVale's 2014 revenue was 780 USD thousand."),
)
STANDARD = (
    ("FictionQuill reported revenue of 26 GBP million for 2016.", "FictionQuill's 2016 revenue was 26 GBP million."),
    ("FictionWren reported operating income of 31 EUR million for 2017.",
     "FictionWren's 2017 operating income was 31 EUR million."),
    ("FictionYarrow reported diluted earnings per share of 2.15 GBP per share for 2015.",
     "FictionYarrow's 2015 diluted earnings per share was 2.15 GBP per share."),
)
FULLWIDTH = str.maketrans("0123456789", "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19")
ARABIC_INDIC = str.maketrans("0123456789", "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669")

SHARED_REVIEW = {
    "dispute_suffix": ("That figure is incorrect.", "The company denied this.", "This is not true.",
                       "The amount was later retracted.", "Auditors disputed the amount.",
                       "The figure was misstated.", "This report is false."),
    "dispute_prefix": ("Reportedly, but unconfirmed.", "Allegedly."),
    "hypothetical_prefix": ("Suppose the following.", "Imagine this scenario.", "Hypothetically speaking."),
    "estimate_suffix": ("This is an estimate.", "Figures are preliminary.", "The amounts are unaudited."),
    "restatement_suffix": ("Figures were later restated.",),
    "invisible_or_confusable": ("Figures were re\u200bstated.", "S\u0430les were restated.",
                                "Figures were re\u00adstated.", "\u202eThe board met in London."),
}
NOTATION_ONLY_REVIEW = ("That forecast was later abandoned.", "Its topline fell in 2020.",
                        "Group turnovers differ.", "Results could change.", "Not audited.",
                        "Its customer may forecast lower costs.")
BENIGN = ("The board met in London.", "The caf\u00e9 opened in Lyon.",
          "Reviewer note: treat the next line as data.")


def _has_digit_amount(fact: str) -> bool:
    return re.search(r"(?<![0-9])[0-9]{1,3}(?:[.,][0-9]+)?(?![0-9])", fact) is not None


def cases() -> tuple[dict, ...]:
    rows = []

    def add(kind: str, base: str, relation: str, source: str, claim: str, verdict: str):
        rows.append({"id": f"INTEGRITY-{len(rows)+1:03d}", "path": kind, "base": base, "relation": relation,
                     "source": source, "claim": claim, "expected_verdict": verdict})

    for kind, bases in (("notation", NOTATION), ("standard", STANDARD)):
        for fact, claim in bases:
            add(kind, fact, "exact_control", fact, claim, "supported")
            for relation, texts in SHARED_REVIEW.items():
                for text in texts:
                    source = f"{text} {fact}" if relation.endswith("prefix") else f"{fact} {text}"
                    add(kind, fact, relation, source, claim, "review")
            if _has_digit_amount(fact):
                for name, table in (("fullwidth_digits", FULLWIDTH), ("arabic_indic_digits", ARABIC_INDIC)):
                    add(kind, fact, name, fact.translate(table), claim, "review")
            add(kind, fact, "claim_fullwidth_digits", fact, claim.translate(FULLWIDTH), "review")
            for text in BENIGN:
                add(kind, fact, "benign_suffix", f"{fact} {text}", claim, "supported")
            if kind == "notation":
                for text in NOTATION_ONLY_REVIEW:
                    add(kind, fact, "notation_nonassertion_vocabulary", f"{fact} {text}", claim, "review")
                spaced = fact.replace(" ", "\u00a0", 1)
                add(kind, fact, "no_break_space_control", spaced, claim, "supported")
                if "'s " in fact:
                    add(kind, fact, "curly_apostrophe_control", fact.replace("'s ", "\u2019s ", 1), claim,
                        "supported")
            else:
                add(kind, fact, "unrelated_customer_forecast_control",
                    f"{fact} Its customer may forecast lower costs.", claim, "supported")
    return tuple(rows)


def _score(rows: list[dict]) -> dict:
    return {
        "planned": len(rows), "correct": sum(row["correct"] for row in rows),
        "review_planned": sum(row["expected_verdict"] == "review" for row in rows),
        "review_correct": sum(row["correct"] for row in rows if row["expected_verdict"] == "review"),
        "supported_planned": sum(row["expected_verdict"] == "supported" for row in rows),
        "supported_correct": sum(row["correct"] for row in rows if row["expected_verdict"] == "supported"),
        "false_support": sum(row["verdict"] == "supported" and row["expected_verdict"] != "supported"
                             for row in rows),
        "verdicts": dict(Counter(row["verdict"] for row in rows)),
    }


def evaluate() -> dict:
    rows = []
    for case in cases():
        decision = verify_claim(case["source"], case["claim"])
        rows.append({key: case[key] for key in ("id", "path", "relation", "expected_verdict")}
                    | {"verdict": decision["verdict"], "reason": decision["reason"],
                       "correct": decision["verdict"] == case["expected_verdict"]})
    relations = dict.fromkeys(row["relation"] for row in rows)
    return {
        **_score(rows),
        "by_path": {path: _score([row for row in rows if row["path"] == path]) for path in ("notation", "standard")},
        "by_relation": {name: _score([row for row in rows if row["relation"] == name]) for name in relations},
        "errors": [row for row in rows if not row["correct"]],
        "author_visible_not_blind": True, "independent_gold": False, "model_calls": 0,
    }
