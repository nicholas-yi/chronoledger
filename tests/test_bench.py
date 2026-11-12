import random

from asof.bench import Case, Injection, Score, build_cases, fictitious_names, score_case
from asof.extraction import ExtractionResult, Link


def test_fictitious_names_avoid_real_filers() -> None:
    real = {"Veltro Systems Inc", "Apple Inc", "Microsoft Corp"}
    names = fictitious_names(50, real, random.Random(0))
    assert len(names) == 50
    assert "Veltro Systems" not in names


def test_build_cases_injects_sentences_into_background() -> None:
    bg = ["We design products. Our customers are diverse. We sell worldwide. Margins vary."]
    cases = build_cases(bg, set(), n_cases=20, seed=1)
    for c in cases:
        for inj in c.injections:
            assert inj.sentence in c.chunk


def _case() -> Case:
    return Case("c0", "...", [
        Injection("Veltrona Systems", "customer", 14.0, "s1"),
        Injection("Calduran Metals", "supplier", None, "s2"),
        Injection("Orbique Labs", None, None, "s3"),
    ])


def test_perfect_extraction_scores_perfectly() -> None:
    res = ExtractionResult([Link("Veltrona Systems", "customer", 14.0, "e"),
                            Link("Calduran Metals", "supplier", None, "e")], [])
    s = Score()
    score_case(_case(), res, s)
    d = s.as_dict()
    assert (d["recall"], d["precision"]) == (1.0, 1.0)


def test_distractor_and_wrong_pct_penalized() -> None:
    res = ExtractionResult([Link("Veltrona Systems", "customer", 41.0, "e"),
                            Link("Orbique Labs", "customer", None, "e")],
                           [(Link("Apple", "customer", None, "e"), "partner_not_in_evidence")])
    s = Score()
    score_case(_case(), res, s)
    d = s.as_dict()
    assert d["tp"] == 0 and d["fn"] == 2 and d["fp"] == 1 and d["pct_wrong"] == 1
    assert d["raw_hallucination_rate"] == 1 / 3
