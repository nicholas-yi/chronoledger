"""Synthetic intervention benchmark for relationship extraction (ground truth by construction).

Real 10-K sentences form the background. Into each chunk we inject sentences about fictitious
companies whose correct extraction is known:

* positives: named customers (with or without a revenue share) and named suppliers;
* distractors: fictitious companies mentioned as competitors, acquisition targets, analysts,
  litigants, or unnamed customers, which must not become customer/supplier links.

Fictitious names are checked against every company name in the EDGAR master index so they
cannot collide with real filers. No human labels are used anywhere.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field

from asof.extraction import ExtractionResult, Extractor
from asof.reconcile import normalize_partner

_SYL = ["vel", "tro", "na", "or", "bi", "que", "cal", "du", "ran", "brim", "wel", "tar", "sen",
        "quo", "lix", "dra", "mon", "zep", "ha", "riv", "kel", "nox", "pra", "ves", "tal", "ium"]
_SUFFIX = ["Systems", "Holdings", "Labs", "Industries", "Health", "Logistics", "Fabrication",
           "Networks", "Materials", "Retail", "Energy", "Devices"]

CUSTOMER_PCT = [
    "Sales to {p} accounted for {pct}% of our total net revenue in fiscal {y}.",
    "{p} represented approximately {pct}% of our consolidated net sales during {y}.",
    "In {y}, our largest customer, {p}, accounted for {pct}% of revenue.",
    "Revenue from {p} was {pct}% of total revenue for the year ended December 31, {y}.",
    "We derived {pct}% of our net revenue from sales to {p} in {y}.",
]
CUSTOMER_NOPCT = [
    "{p} is one of our most significant customers.",
    "We sell a substantial portion of our products to {p} under a multi-year agreement.",
    "Our customers include {p}, which purchases our products for use in its own offerings.",
]
SUPPLIER = [
    "We rely on {p} as the sole supplier of certain key components.",
    "Substantially all of our products are manufactured by {p}.",
    "We purchase a significant portion of our raw materials from {p}.",
    "{p} provides contract manufacturing services for our devices.",
]
DISTRACTOR = [
    ("We compete with {p} and other companies in our markets.", "competitor"),
    ("Our principal competitors include {p}.", "competitor"),
    ("In {y}, we completed the acquisition of {p}.", None),
    ("According to {p}, an industry research firm, the market grew in {y}.", None),
    ("We are a defendant in litigation brought by {p}.", None),
    ("One customer accounted for {pct}% of our net revenue in {y}.", "unnamed"),
]


@dataclass
class Injection:
    name: str
    relation: str | None  # customer, supplier, competitor, or None (must not be customer/supplier)
    pct: float | None
    sentence: str


@dataclass
class Case:
    case_id: str
    chunk: str
    injections: list[Injection] = field(default_factory=list)


def fictitious_names(n: int, real_names: set[str], rng: random.Random) -> list[str]:
    out: set[str] = set()
    real_norm = {normalize_partner(x) for x in real_names}
    real_tokens = {t for x in real_norm for t in x.split()}
    while len(out) < n:
        stem = "".join(rng.choice(_SYL) for _ in range(rng.randint(2, 3))).capitalize()
        if stem.lower() in real_tokens:
            continue
        name = f"{stem} {rng.choice(_SUFFIX)}"
        if normalize_partner(name) not in real_norm:
            out.add(name)
    return sorted(out)


def build_cases(
    backgrounds: list[str], real_names: set[str], n_cases: int, seed: int = 0
) -> list[Case]:
    rng = random.Random(seed)
    names = fictitious_names(n_cases * 4, real_names, rng)
    rng.shuffle(names)
    cases = []
    for i in range(n_cases):
        bg = rng.choice(backgrounds)
        sentences = [s for s in re.split(r"(?<=[\.\!\?])\s+", bg) if s.strip()]
        start = rng.randrange(max(1, len(sentences) - 4))
        body = sentences[start:start + rng.randint(2, 4)]
        injections = []
        for _ in range(rng.randint(1, 3)):
            name = names.pop()
            year = rng.randint(2012, 2025)
            pct = rng.randint(10, 45)
            kind = rng.random()
            if kind < 0.35:
                inj = Injection(name, "customer", float(pct),
                                rng.choice(CUSTOMER_PCT).format(p=name, pct=pct, y=year))
            elif kind < 0.5:
                inj = Injection(name, "customer", None, rng.choice(CUSTOMER_NOPCT).format(p=name))
            elif kind < 0.75:
                inj = Injection(name, "supplier", None, rng.choice(SUPPLIER).format(p=name))
            else:
                tpl, rel = rng.choice(DISTRACTOR)
                inj = Injection(name, "competitor" if rel == "competitor" else None, None,
                                tpl.format(p=name, pct=pct, y=year))
            injections.append(inj)
            body.insert(rng.randint(0, len(body)), inj.sentence)
        cases.append(Case(f"c{i:04d}", " ".join(body), injections))
    return cases


@dataclass
class Score:
    tp: int = 0
    fn: int = 0
    fp: int = 0
    pct_wrong: int = 0
    raw_outputs: int = 0
    raw_ungrounded: int = 0
    by_kind: dict[str, list[int]] = field(default_factory=dict)  # kind -> [hit, total]

    def as_dict(self) -> dict:
        recall = self.tp / (self.tp + self.fn) if self.tp + self.fn else float("nan")
        precision = self.tp / (self.tp + self.fp) if self.tp + self.fp else float("nan")
        hall = self.raw_ungrounded / self.raw_outputs if self.raw_outputs else 0.0
        return {
            "recall": recall, "precision": precision, "raw_hallucination_rate": hall,
            "tp": self.tp, "fn": self.fn, "fp": self.fp, "pct_wrong": self.pct_wrong,
            "raw_outputs": self.raw_outputs, "raw_ungrounded": self.raw_ungrounded,
            "recall_by_kind": {k: v[0] / v[1] for k, v in self.by_kind.items() if v[1]},
        }


def score_case(case: Case, result: ExtractionResult, score: Score) -> None:
    score.raw_outputs += len(result.accepted) + len(result.rejected)
    score.raw_ungrounded += sum(
        1 for _, why in result.rejected if why in ("evidence_not_in_source", "partner_not_in_evidence")
    )
    fict = {normalize_partner(i.name): i for i in case.injections}
    got: dict[str, set[tuple[str, float | None]]] = {}
    for link in result.accepted:
        got.setdefault(normalize_partner(link.partner), set()).add((link.relation, link.revenue_pct))

    for key, inj in fict.items():
        outputs = got.get(key, set())
        relations = {r for r, _ in outputs}
        if inj.relation in ("customer", "supplier"):
            kind = f"{inj.relation}{'_pct' if inj.pct is not None else ''}"
            hit = inj.relation in relations
            if hit and inj.pct is not None:
                pcts = {p for r, p in outputs if r == inj.relation}
                if not any(p is not None and abs(p - inj.pct) < 0.5 for p in pcts):
                    score.pct_wrong += 1
                    hit = False
            score.tp += hit
            score.fn += not hit
            score.by_kind.setdefault(kind, [0, 0])
            score.by_kind[kind][0] += hit
            score.by_kind[kind][1] += 1
            score.fp += len(relations - {inj.relation, "other"})
        else:
            score.fp += len(relations & {"customer", "supplier"})


def run(cases: list[Case], extractor: Extractor) -> dict:
    score = Score()
    for case in cases:
        score_case(case, extractor.extract_chunk(case.chunk), score)
    return score.as_dict()


def dump_cases(cases: list[Case]) -> str:
    return "\n".join(
        json.dumps({"case_id": c.case_id, "chunk": c.chunk,
                    "injections": [i.__dict__ for i in c.injections]})
        for c in cases
    )
