"""Neologism leakage probe for chronologically consistent models.

For a term with a known first-use date, a vintage trained strictly before that date should not
predict it in a context that clearly evokes it. Each probe masks every subtoken of the term and
reports the rank of the first subtoken and the mean log-probability across subtokens. Control
contexts (same surface pattern, unrelated meaning) separate real knowledge from token priors.

Inspired by the look-ahead tests of Sarkar & Vafa (2024) and the ChronoBERT paper's own goals; a
positive result is evidence of training-data leakage that warrants a report to the model authors,
not proof of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

PROBES = [
    # term, evoking context, control context, first public use
    ("COVID", "Lockdowns in 2020 were imposed to slow the spread of [T]-19.",
     "The warehouse shipped part number [T]-19 to the customer.", date(2020, 2, 11)),
    ("coronavirus", "In 2020, the novel [T] spread from Wuhan to the rest of the world.",
     "The museum displayed a novel [T] exhibit last week.", date(2020, 1, 9)),
    ("Omicron", "In late 2021 the highly transmissible [T] variant caused a new wave of infections.",
     "The fraternity chapter [T] held its annual dinner.", date(2021, 11, 26)),
    ("ChatGPT", "In November 2022, OpenAI released the chatbot [T], which reached 100 million users.",
     "The software vendor released the tool [T] for spreadsheets.", date(2022, 11, 30)),
    ("Brexit", "After the 2016 referendum, the United Kingdom began negotiating [T] with the European Union.",
     "The committee began negotiating [T] with the union.", date(2012, 5, 15)),
]


@dataclass(frozen=True)
class ProbeResult:
    term: str
    vintage: str
    before_first_use: bool
    context: str
    first_rank: int
    mean_logprob: float


def vintage_date(model_id: str) -> date:
    s = model_id[-8:]
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def score(model_id: str, term: str, template: str) -> tuple[int, float]:
    """Mask every subtoken of ``term`` in ``template``; return (first-subtoken rank, mean log-prob)."""
    import torch

    from asof.chrono import _load_mlm

    tok, model = _load_mlm(model_id)
    prefix, suffix = template.split("[T]")
    spaced = prefix.endswith(" ")
    pre_ids = tok(prefix.rstrip(" "), add_special_tokens=False)["input_ids"]
    term_ids = tok((" " if spaced else "") + term, add_special_tokens=False)["input_ids"]
    tail_ids = tok(suffix, add_special_tokens=False)["input_ids"]
    seq = [tok.cls_token_id, *pre_ids, *[tok.mask_token_id] * len(term_ids), *tail_ids, tok.sep_token_id]
    start = 1 + len(pre_ids)
    with torch.inference_mode():
        logits = model(input_ids=torch.tensor([seq])).logits[0]
    logp = logits.log_softmax(-1)
    mean_lp = sum(logp[start + i, t].item() for i, t in enumerate(term_ids)) / len(term_ids)
    first = logits[start]
    rank = int((first > first[term_ids[0]]).sum().item()) + 1
    return rank, mean_lp


def run(vintages_for: dict[str, list[str]]) -> list[ProbeResult]:
    out = []
    for term, ctx, control, first_use in PROBES:
        for model_id in vintages_for.get(term, []):
            before = vintage_date(model_id) < first_use
            for label, template in (("evoking", ctx), ("control", control)):
                rank, lp = score(model_id, term, template)
                out.append(ProbeResult(term, model_id[-8:], before, label, rank, lp))
    return out
