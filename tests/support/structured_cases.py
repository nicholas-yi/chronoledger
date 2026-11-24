"""The 24 invented structured claim cases first scored against HHEM (not promoted)."""

from __future__ import annotations


def fixture() -> tuple[dict, ...]:
    definitions = (
        ("value", "FictionPoppy reported revenue of 18 USD million for 2017.",
         "FictionPoppy reported revenue of 18 USD million for 2017.",
         "FictionPoppy reported revenue of 81 USD million for 2017."),
        ("year", ("Company: FictionQuartz.\n| Item | 2016 (USD million) | 2017 (EUR thousand) |\n"
                  "| Revenue | 63 | 28.5 |"),
         "FictionQuartz's 2017 revenue was 28.5 EUR thousand.",
         "FictionQuartz's 2017 revenue was 63 USD million."),
        ("currency", "FictionReed reported revenue of 21 EUR million for 2018.",
         "FictionReed reported revenue of 21 EUR million for 2018.",
         "FictionReed reported revenue of 21 USD million for 2018."),
        ("scale", "Company: FictionSpruce. Amounts in USD thousand.\n| Item | 2018 |\n| Revenue | 25 |",
         "FictionSpruce's 2018 revenue was 25 USD thousand.",
         "FictionSpruce's 2018 revenue was 25 USD million."),
        ("sign", ("FictionTamarack reported operating income of (14) USD million for 2017. "
                  "Parentheses denote a negative amount."),
         "FictionTamarack's 2017 operating income was negative 14 USD million.",
         "FictionTamarack's 2017 operating income was positive 14 USD million."),
        ("entity", ("FictionUmber reported revenue of 31 USD million for 2018. "
                    "Its customer FictionViolet reported revenue of 45 USD million for 2018."),
         "FictionUmber's 2018 revenue was 31 USD million.",
         "FictionUmber's 2018 revenue was 45 USD million."),
        ("definition", ("FictionWillow reported gross margin of 12 percent for 2017. "
                        "Its operating margin was 7 percent for 2017."),
         "FictionWillow's 2017 gross margin was 12 percent.",
         "FictionWillow's 2017 gross margin was 7 percent."),
        ("scope", ("FictionXylem reported consolidated revenue of 70 USD million for 2018. "
                   "Its north segment revenue was 20 USD million."),
         "FictionXylem's 2018 consolidated revenue was 70 USD million.",
         "FictionXylem's 2018 consolidated revenue was 20 USD million."),
        ("basis", ("For 2018, FictionYarrow reported GAAP operating income of 13 USD million "
                   "and non-GAAP operating income of 19 USD million."),
         "FictionYarrow's 2018 GAAP operating income was 13 USD million.",
         "FictionYarrow's 2018 GAAP operating income was 19 USD million."),
        ("denominator", ("FictionZircon reported diluted earnings per share of 1.25 USD per share "
                         "for 2018. Basic earnings per share was 1.40 USD per share."),
         "FictionZircon's 2018 diluted earnings per share was 1.25 USD per share.",
         "FictionZircon's 2018 diluted earnings per share was 1.40 USD per share."),
        ("footnote", ("Company: FictionAcorn, fiscal 2017. Default units: USD million.\n"
                      "| Revenue (b) | 33 |\n(b) Revenue alone is stated in EUR thousand."),
         "FictionAcorn's 2017 revenue was 33 EUR thousand.",
         "FictionAcorn's 2017 revenue was 33 USD million."),
        ("correction", ("Original: FictionBramble reported revenue of 40 EUR million for 2018. "
                        "Correction: FictionBramble reported revenue of 44 EUR million for 2018. "
                        "This correction supersedes the original amount."),
         "FictionBramble's corrected 2018 revenue was 44 EUR million.",
         "FictionBramble's corrected 2018 revenue was 40 EUR million."),
    )
    return tuple({
        "id": f"HHEM-{i:02d}-{member}", "category": category, "source": source, "claim": claim,
        "expected_supported": member == 0,
    } for i, (category, source, positive, negative) in enumerate(definitions, 1)
                 for member, claim in enumerate((positive, negative)))
