# Findings

Findings are recorded as they occur, including ones that weaken this project's own design.

## F1: context-specific "COVID" knowledge in pre-2020 ChronoBERT vintages

**Status:** reproducible probe result. The cause is unconfirmed, and nothing has yet been reported to
the model authors.

**What we tested.** `scripts/leakprobe.py` masks every subtoken of a term whose first public use is
known. It then compares a context that evokes the term with a control context that has the same
surface pattern but an unrelated meaning. A vintage trained before the term existed should not
rank it highly in the evoking context.

| Term (first public use) | Vintage | Evoking rank | Control rank |
|---|---|---|---|
| COVID (2020-02-11) | 2018-12-31 | **1** (mean log-p −0.06) | 1,163 |
| COVID | 2019-12-31 | **1** (mean log-p −0.02) | 1,400 |
| COVID | 2020-12-31 | 1 | 79 |
| coronavirus (2020-01-09) | 2018-12-31 | 342 | 2,665 |
| coronavirus | 2019-12-31 | 302 | 1,444 |
| coronavirus | 2020-12-31 | 1 | 5 |
| Brexit (2012-05-15) | 2010-12-31 | 2,444 | 7,592 |
| Brexit | 2011-12-31 | 2,109 | 7,317 |
| Brexit | 2016-12-31 | 16 | 1,243 |
| Omicron (2021-11-26) | 2019 / 2020 / 2021 | 37 / 20 / 60 | 247 / 444 / 304 |
| ChatGPT (2022-11-30) | 2020 / 2021 / 2022 | 28 / 20 / 18 | 3,759 / 3,265 / 1,925 |

**Reading.**
- The 2018 and 2019 vintages complete "Lockdowns in 2020 were imposed to slow the spread of
  ___-19" with "COVID" at about 94–98% probability. In an unrelated "part number ___-19"
  context the term ranks below 1,000th, so this is context-specific knowledge, not a token-prior
  artifact.
- The same vintages do **not** know "coronavirus", and Brexit is clean, so leakage, if present,
  is narrow rather than wholesale.
- Omicron and ChatGPT are inconclusive: their first subtokens are generic, and the post-coinage
  vintages don't clearly know them either.

**Hypothesis, not established:** some pre-2020 training documents may carry original timestamps
but contain later revisions, for example encyclopedia articles edited to add "cancelled due to the
COVID-19 pandemic". That would spread "COVID-19" while leaving "coronavirus" rare.

**Implications for this project.**
- ChronoBERT vintages cannot be assumed perfectly leak-free. The referee's representation threat
  fails, and the gate stays blocked.
- Mitigation (deviation D3): every H1 result must also hold under a bag-of-words TF-IDF
  representation, which structurally cannot leak information from after the filing.
- The probe covers only five terms, and its power is limited for multi-token or generic-prefix
  terms. A broader, dated neologism set, especially for 2022–2024 (the vintages this project
  actually uses), is future work.
- Before any public claim about the model, contact the ChronoBERT authors with the reproduction
  script.
