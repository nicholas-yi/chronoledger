"""Fresh notation/alias claim challenge, frozen with its baseline before any implementation change."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from asof.claim_verifier import verify_claim

VERDICTS = ("supported", "contradicted", "review")


def fixture() -> tuple[dict, ...]:
    rows = (
        # Unambiguous notation and declared revenue aliases that should resolve.
        ("FictionAlba's turnover reached EUR4.5bn during FY2017.",
         "FictionAlba's 2017 revenue was 4.5 EUR billion.", "supported", "compact_bn"),
        ("FictionAlba's turnover reached EUR4.5bn during FY2017.",
         "FictionAlba's 2017 revenue was 5.4 EUR billion.", "contradicted", "compact_bn"),
        ("FictionBirch said its top line came to one hundred twenty-five thousand pounds sterling in 2018.",
         "FictionBirch's 2018 revenue was 125 GBP thousand.", "supported", "spelled_amount"),
        ("FictionBirch said its top line came to one hundred twenty-five thousand pounds sterling in 2018.",
         "FictionBirch's 2018 revenue was 152 GBP thousand.", "contradicted", "spelled_amount"),
        ("FictionCress's revenue totalled GBP780k for fiscal 2019.",
         "FictionCress's 2019 revenue was 0.78 GBP million.", "supported", "compact_k_equivalence"),
        ("FictionCress's revenue totalled GBP780k for fiscal 2019.",
         "FictionCress's 2019 revenue was 7.8 GBP million.", "contradicted", "compact_k_equivalence"),
        ("FictionDune's top-line amounted to \u20ac312m in FY 2015.",
         "FictionDune's 2015 revenue was 312 EUR million.", "supported", "euro_symbol"),
        ("FictionDune's top-line amounted to \u20ac312m in FY 2015.",
         "FictionDune's 2015 revenue was 312 USD million.", "contradicted", "euro_symbol"),
        ("FictionElm said its turnover was forty-two million US dollars for 2016.",
         "FictionElm's 2016 revenue was 42 USD million.", "supported", "spelled_us_dollars"),
        ("FictionElm said its turnover was forty-two million US dollars for 2016.",
         "FictionElm's 2016 revenue was 24 USD million.", "contradicted", "spelled_us_dollars"),
        ("FictionPine's turnover reached GBP2.6m during FY2016.",
         "FictionPine's 2016 revenue was 2,600 GBP thousand.", "supported", "compact_m_equivalence"),
        ("FictionPine's turnover reached GBP2.6m during FY2016.",
         "FictionPine's 2016 revenue was 2,060 GBP thousand.", "contradicted", "compact_m_equivalence"),
        # Ambiguous, nonactual, qualified or wrong-subject wording must stay in review.
        ("FictionFern's employee turnover reached 12 percent during FY2017.",
         "FictionFern's 2017 revenue was 12 percent.", "review", "employee_turnover"),
        ("FictionGlen's turnover reached $26m during FY2016.",
         "FictionGlen's 2016 revenue was 26 USD million.", "review", "ambiguous_dollar_symbol"),
        ("FictionHolm said its top line would reach EUR90m in 2018.",
         "FictionHolm's 2018 revenue was 90 EUR million.", "review", "forecast_modal"),
        ("FictionIvy's inventory turnover reached GBP3m during FY2016.",
         "FictionIvy's 2016 revenue was 3 GBP million.", "review", "inventory_turnover"),
        ("FictionJuno said its top line came to twenty million pounds in 2016.",
         "FictionJuno's 2016 revenue was 20 GBP million.", "review", "ambiguous_pounds"),
        ("FictionKale's turnover reached GBP26m during FY2016, excluding a disposed segment.",
         "FictionKale's 2016 revenue was 26 GBP million.", "review", "trailing_qualification"),
        ("FictionLark's net sales reached EUR40m during FY2016.",
         "FictionLark's 2016 revenue was 40 EUR million.", "review", "unaliased_net_sales"),
        ("FictionNook's turnover reached GBP26m during FY2015.",
         "FictionNook's 2016 revenue was 26 GBP million.", "review", "wrong_year"),
        ("FictionOak's competitor's turnover reached GBP26m during FY2016.",
         "FictionOak's 2016 revenue was 26 GBP million.", "review", "competitor_subject"),
        ("FictionReed's turnover ratio reached 2.5 during FY2016.",
         "FictionReed's 2016 revenue was 2.5 GBP million.", "review", "turnover_ratio"),
        (("FictionSage's turnover reached GBP26m during FY2016. "
          "This is an illustrative example, not an actual disclosure."),
         "FictionSage's 2016 revenue was 26 GBP million.", "review", "illustrative"),
        ("FictionTeal said its top line came to twenty-five percent in 2016.",
         "FictionTeal's 2016 revenue was 25 percent.", "review", "percent_not_amount"),
    )
    return tuple({"id": f"NOTATION-{i:02d}", "source": source, "claim": claim,
                  "expected_verdict": verdict, "category": category}
                 for i, (source, claim, verdict, category) in enumerate(rows, 1))


_ONES = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
         "eighteen", "nineteen")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _words(number: int, british: bool) -> str:
    """Generator-side cardinal words, written independently of the verifier's parser."""
    hundreds, rest = divmod(number, 100)
    parts = [f"{_ONES[hundreds]} hundred"] if hundreds else []
    if rest:
        if parts and british:
            parts.append("and")
        parts.append(_ONES[rest] if rest < 20 else _TENS[rest//10]+(f"-{_ONES[rest % 10]}" if rest % 10 else ""))
    return " ".join(parts)


_ISSUERS = ("FictionAster", "FictionBrook", "Fiction Cobalt")
_ALIASES = (("'s", "revenue"), ("'s", "turnover"), ("'s", "top line"), ("'s", "top-line"),
            (" said its", "revenue"), (" said its", "turnover"), (" said its", "top line"))
_VERBS = ("reached", "totalled", "totaled", "amounted to", "came to", "was")
_PERIODS = ("during FY{y}", "in FY {y}", "for fiscal {y}", "for fiscal year {y}", "in {y}")
_CURRENCIES = ("GBP", "EUR", "USD")
_SCALES = ("million", "billion", "thousand")
_SUFFIX = {"thousand": ("k",), "million": ("m", "mn"), "billion": ("bn",)}
_VALUES = ("26", "4.5", "780", "2.6", "1,250", "42", "312", "0.75")
_INTEGERS = (26, 125, 42, 312, 780, 999, 17, 600)
_SPELLED_CURRENCY = {"GBP": ("pounds sterling",), "EUR": ("euros",), "USD": ("US dollars", "U.S. dollars")}
_SWAP = {"GBP": "EUR", "EUR": "USD", "USD": "GBP"}
_RESCALE = {"million": ("thousand", 3), "thousand": ("million", -3), "billion": ("million", 3)}


def _base(i: int) -> dict:
    issuer = _ISSUERS[i % 3]
    connector, alias = _ALIASES[i % 7]
    form = i % 5
    currency = "EUR" if form == 2 else _CURRENCIES[(i//5) % 3]
    scale = _SCALES[(i//3) % 3]
    raw = str(_INTEGERS[(i//2) % len(_INTEGERS)]) if form == 3 else _VALUES[(i//2) % len(_VALUES)]
    year = str(2010 + i % 11)
    suffix = _SUFFIX[scale][(i//6) % len(_SUFFIX[scale])]
    if form == 3:
        spelled = _SPELLED_CURRENCY[currency][(i//7) % len(_SPELLED_CURRENCY[currency])]
        amount = f"{_words(int(raw), british=i % 2 == 1)} {scale} {spelled}"
        ambiguous = f"{_words(int(raw), british=False)} {scale} {('dollars', 'pounds')[i % 2]}"
    else:
        amount = {0: f"{currency}{raw}{suffix}", 1: f"{currency} {raw}{suffix}",
                  2: f"\u20ac{raw}{suffix}", 4: f"{currency} {raw} {scale}"}[form]
        ambiguous = {0: f"${raw}{suffix}", 1: f"$ {raw}{suffix}", 2: f"${raw}{suffix}",
                     4: f"${raw} {scale}"}[form]
    return {"i": i, "issuer": issuer, "connector": connector, "alias": alias,
            "verb": _VERBS[i % 6], "amount": amount, "ambiguous_amount": ambiguous,
            "period": _PERIODS[(i//7) % 5].format(y=year), "year": year, "currency": currency,
            "scale": scale, "value": Decimal(raw.replace(",", "")), "form": form}


def _text(base: dict, *, issuer=None, connector=None, alias=None, verb=None, amount=None,
          tail="", after="") -> str:
    return (f"{issuer or base['issuer']}{connector or base['connector']} {alias or base['alias']} "
            f"{verb or base['verb']} {amount or base['amount']} {base['period']}{tail}.{after}")


def _claim(base: dict, *, value=None, currency=None, scale=None, year=None, metric="revenue") -> str:
    number = base["value"] if value is None else value
    return (f"{base['issuer']}'s {year or base['year']} {metric} was {format(number, 'f')} "
            f"{currency or base['currency']} {scale or base['scale']}.")


def grid(count: int = 60) -> tuple[dict, ...]:
    """Metamorphic variants: each relation's expected verdict is fixed by construction."""
    rows = []
    qualifiers = ("employee", "inventory", "segment", "asset")
    nonasserted = ("would reach", "never reached", "was expected to reach", "could reach")
    for i in range(count):
        base = _base(i)
        target, shift = _RESCALE[base["scale"]]
        rescaled = base["value"].scaleb(shift)
        variants = (
            ("exact", _text(base), _claim(base), "supported"),
            ("rescaled_equivalent", _text(base), _claim(base, value=rescaled, scale=target), "supported"),
            ("value_changed", _text(base), _claim(base, value=base["value"]+1), "contradicted"),
            ("currency_changed", _text(base), _claim(base, currency=_SWAP[base["currency"]]),
             "contradicted"),
            ("claim_year_absent", _text(base), _claim(base, year=str(int(base["year"])+1)), "review"),
            ("claim_metric_absent", _text(base), _claim(base, metric="operating income"), "review"),
            ("qualified_metric", _text(base, alias=f"{qualifiers[i % 4]} {base['alias']}"),
             _claim(base), "review"),
            ("nonasserted_verb", _text(base, verb=nonasserted[i % 4]), _claim(base), "review"),
            ("trailing_qualification", _text(base, tail=", excluding a disposed segment"),
             _claim(base), "review"),
            ("illustrative_document", _text(
                base, after=" This is an illustrative example, not an actual disclosure."),
             _claim(base), "review"),
            ("ambiguous_currency", _text(base, amount=base["ambiguous_amount"]), _claim(base), "review"),
            ("third_party_subject", _text(base, connector=f"{base['connector']} competitor's"
                                          if base["connector"] == " said its" else "'s competitor's"),
             _claim(base), "review"),
            ("issuer_prefix_collision", _text(base, issuer=f"{base['issuer']}ine"), _claim(base), "review"),
        )
        for relation, source, claim, verdict in variants:
            rows.append({"id": f"GRID-{i:02d}-{relation}", "relation": relation, "form": base["form"],
                         "source": source, "claim": claim, "expected_verdict": verdict})
    return tuple(rows)


def _score(rows: list[dict]) -> dict:
    resolvable = [row for row in rows if row["expected_verdict"] != "review"]
    review = [row for row in rows if row["expected_verdict"] == "review"]
    return {
        "planned": len(rows), "correct": sum(row["correct"] for row in rows),
        "resolvable_planned": len(resolvable),
        "resolvable_correct": sum(row["correct"] for row in resolvable),
        "review_planned": len(review), "review_correct": sum(row["correct"] for row in review),
        "false_support": sum(row["verdict"] == "supported" and row["expected_verdict"] != "supported"
                             for row in rows),
        "false_contradiction": sum(row["verdict"] == "contradicted"
                                   and row["expected_verdict"] != "contradicted" for row in rows),
        "unresolved_resolvable": sum(row["verdict"] == "review" for row in resolvable),
        "verdicts": dict(Counter(row["verdict"] for row in rows)),
        "resolved_without_valid_proof": sum(row["verdict"] != "review" and not row["proof_valid"]
                                            for row in rows),
    }


def _decide(cases: tuple[dict, ...], keys: tuple[str, ...]) -> list[dict]:
    rows = []
    for case in cases:
        decision = verify_claim(case["source"], case["claim"])
        rows.append({**{key: case[key] for key in keys},
                     "expected_verdict": case["expected_verdict"], "verdict": decision["verdict"],
                     "correct": decision["verdict"] == case["expected_verdict"],
                     "proof_valid": decision["proof_valid"], "reason": decision["reason"]})
    return rows


def evaluate() -> dict:
    challenge = _decide(fixture(), ("id", "category"))
    variants = _decide(grid(), ("id", "relation", "form"))
    by_relation = {relation: _score([row for row in variants if row["relation"] == relation])
                   for relation in dict.fromkeys(row["relation"] for row in variants)}
    return {
        "challenge": {**_score(challenge), "rows": challenge},
        "grid": {**_score(variants),
                 "by_relation": {key: {k: v for k, v in value.items() if k != "verdicts"}
                                 for key, value in by_relation.items()},
                 "errors": [row for row in variants if not row["correct"]]},
        "independent_gold": False, "model_calls": 0,
    }
