"""New author-visible verification pairs and separate explicit format-shift controls."""


def fixture() -> tuple[dict, ...]:
    definitions = (
        ("value", "FictionCamellia reported revenue of 26 GBP million for 2016.",
         "FictionCamellia's 2016 revenue was 26 GBP million.",
         "FictionCamellia's 2016 revenue was 62 GBP million."),
        ("column_year", ("Company: FictionDogrose.\n"
                         "| Item | 2015 (USD million) | 2016 (GBP thousand) |\n"
                         "| Revenue | 82 | 34.5 |"),
         "FictionDogrose's 2016 revenue was 34.5 GBP thousand.",
         "FictionDogrose's 2016 revenue was 82 USD million."),
        ("currency", "FictionElder reported revenue of 27 GBP million for 2016.",
         "FictionElder's 2016 revenue was 27 GBP million.",
         "FictionElder's 2016 revenue was 27 EUR million."),
        ("scale", ("Company: FictionFreesia. Amounts in EUR thousand.\n"
                   "| Item | 2016 |\n| Revenue | 38 |"),
         "FictionFreesia's 2016 revenue was 38 EUR thousand.",
         "FictionFreesia's 2016 revenue was 38 EUR billion."),
        ("sign", ("FictionGentian reported operating income of (23) GBP million for 2016. "
                  "Parentheses denote a negative amount."),
         "FictionGentian's 2016 operating income was negative 23 GBP million.",
         "FictionGentian's 2016 operating income was positive 23 GBP million."),
        ("entity", ("FictionHeather reported revenue of 46 EUR million for 2016. "
                    "Its customer FictionIris reported revenue of 58 EUR million for 2016."),
         "FictionHeather's 2016 revenue was 46 EUR million.",
         "FictionHeather's 2016 revenue was 58 EUR million."),
        ("definition", ("FictionJonquil reported gross margin of 17 percent for 2016. "
                        "Its operating margin was 9 percent for 2016."),
         "FictionJonquil's 2016 gross margin was 17 percent.",
         "FictionJonquil's 2016 gross margin was 9 percent."),
        ("scope", ("FictionKalmia reported consolidated revenue of 84 EUR million for 2016. "
                   "Its west segment revenue was 29 EUR million."),
         "FictionKalmia's 2016 consolidated revenue was 84 EUR million.",
         "FictionKalmia's 2016 consolidated revenue was 29 EUR million."),
        ("basis", ("For 2016, FictionLotus reported GAAP operating income of 21 EUR million "
                   "and non-GAAP operating income of 32 EUR million."),
         "FictionLotus's 2016 GAAP operating income was 21 EUR million.",
         "FictionLotus's 2016 GAAP operating income was 32 EUR million."),
        ("denominator", ("FictionMagnolia reported diluted earnings per share of 2.15 GBP per share "
                         "for 2016. Basic earnings per share was 2.45 GBP per share."),
         "FictionMagnolia's 2016 diluted earnings per share was 2.15 GBP per share.",
         "FictionMagnolia's 2016 diluted earnings per share was 2.45 GBP per share."),
        ("footnote", ("Company: FictionNarcissus, fiscal 2016. Default units: USD million.\n"
                      "| Revenue (c) | 48 |\n(c) Revenue alone is stated in GBP thousand."),
         "FictionNarcissus's 2016 revenue was 48 GBP thousand.",
         "FictionNarcissus's 2016 revenue was 48 USD million."),
        ("correction", ("Original: FictionOleander reported revenue of 52 GBP million for 2016. "
                        "Correction: FictionOleander reported revenue of 57 GBP million for 2016. "
                        "This correction supersedes the original amount."),
         "FictionOleander's corrected 2016 revenue was 57 GBP million.",
         "FictionOleander's corrected 2016 revenue was 52 GBP million."),
    )
    return tuple({
        "id": f"STRUCT-{i:02d}-{member}", "category": category, "source": source, "claim": claim,
        "expected_supported": member == 0,
    } for i, (category, source, positive, negative) in enumerate(definitions, 1)
                 for member, claim in enumerate((positive, negative)))


def boundary_controls() -> tuple[dict, ...]:
    definitions = (
        ("FictionPeony's turnover reached GBP26m during FY2016.",
         "FictionPeony's 2016 revenue was 26 GBP million.", True),
        ("FictionPeony's turnover reached GBP26m during FY2016.",
         "FictionPeony's 2016 revenue was 62 GBP million.", False),
        ("FictionRue said its top line came to twenty million euros in 2016.",
         "FictionRue's 2016 revenue was 20 EUR million.", True),
        ("FictionRue said its top line came to twenty million euros in 2016.",
         "FictionRue's 2016 revenue was 30 EUR million.", False),
        ("FictionSorrel: fiscal2016 EPS(diluted)=GBP2.20; EPS(basic)=GBP2.50.",
         "FictionSorrel's 2016 diluted earnings per share was 2.20 GBP per share.", True),
        ("FictionSorrel: fiscal2016 EPS(diluted)=GBP2.20; EPS(basic)=GBP2.50.",
         "FictionSorrel's 2016 diluted earnings per share was 2.50 GBP per share.", False),
    )
    return tuple({"id": f"BOUNDARY-{i:02d}", "source": source, "claim": claim,
                  "expected_supported": truth} for i, (source, claim, truth) in enumerate(definitions, 1))
