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

### F1 update: probing the vintages this project uses

These use verified first-use dates: J&J named Kenvue on 2022-09-28; 3M named Solventum on 2023-11-16; DuPont named Qnity on 2025-04-29; the FDA approved Mounjaro on 2022-05-13.

| Term | Vintage (pre = before first use) | Evoking rank | Control rank |
|---|---|---|---|
| Mounjaro | 2021 (pre) / 2022 | 6 / 7 | 8 / 10 |
| Kenvue | 2021 (pre) / 2022 | 923 / 818 | 403 / 257 |
| Solventum | 2022 (pre, in use) / 2023 | 594 / 688 | 1,264 / 1,294 |
| Qnity | 2022 / 2023 / 2024 (all pre, all in use) | 311 / 611 / 368 | 2,768 / 3,407 / 3,379 |

- **No context-specific leakage in the in-use vintages.** But the post-coinage positive controls also fail: the 2022 vintage doesn't know Kenvue, and the 2023 vintage doesn't know Solventum. Yearly vintages appear to absorb only high-frequency new terms, such as COVID, so this probe can detect only large leaks.
- **Mounjaro is a subword-prior false positive under the rank-only rule:** its control context ranks it just as high. See deviation D4.
- **More power** needs frequent terms coined within the in-use window, or a different method, such as likelihood comparisons on dated news text.

## F2: distress-event tests are invalid under a current-ticker universe

**Status:** confirmed by diagnostic. It invalidates the H5b, H5c, and H6(b) development results.

**Trigger.** Every H5 development result had the opposite sign to the published effects, even though those effects are well established. Late-filing notices showed a mean CAR(+1..+60) of +6.8% (t = 1.5), Item 4.02 +5.9%, Item 4.01 +4.4%, and Friday-evening 8-Ks +0.97% relative to other 8-Ks (t = 2.0).

**Diagnostics.**
- **Random-date placebo, same universe:** mean CAR(+1..+20) −0.3% (t = −2.1); CAR(+1..+60) −0.6% (t = −1.3). There's no general positive bias.
- **Coverage by event type**, using all SEC filers from the bulk archive, Jan 2023–Jun 2024:

| Filers | Firms | In price-covered universe | Stopped filing 10-Ks before mid-2025 |
|---|---|---|---|
| All 10-K filers | 7,378 | 36.6% | 26.2% |
| NT 10-K/10-Q | 1,822 | 11.0% | 49.3% |
| 8-K Item 4.02 | 329 | 27.1% | 34.3% |
| 8-K Item 4.01 | 1,115 | 20.6% | 30.7% |

**Reading.** The universe uses today's tickers and a public float of at least $200M. Distressed filers are therefore 1.3–3.3x less likely to be included, and the excluded ones are disproportionately those that later disappeared. Among distressed firms, conditioning on survival selects the rebounders, so the sign flips.

**Consequences.**
- H5b, H5c, and H6(b) cannot be tested with free current-ticker price data. Their development results are reported as **invalid**, not as evidence against the published effects. Their holdouts will not be opened under this data.
- H5a compares Friday-evening 8-Ks with other 8-Ks within the same universe, so it is less directly affected, but it is still subject to the same selection. Its positive development estimate is not a replication.
- Testing distress events needs prices for delisted securities, for example the Tiingo free tier, or for acquired firms, their deal consideration. This is the strongest argument yet for adding a delisted-price source.

## F3: three data bugs caught by an implausible backtest

**Trigger.** The first H0 development run showed long-short means of +20% to +27% per month, with alpha t-statistics up to 4.6. That is an order of magnitude above any credible text-change effect, so it was treated as a bug until proven otherwise.

**Root causes.**
1. **XBRL share-count typos.** PKG filed 89.8 billion shares in one 10-Q, against about 89.8 million before and after; the maximum in the data was 8 × 10^13. Value weights became meaningless.
   - Fix: point-in-time cleaning. A jump of more than 10x takes effect only after a later filing confirms it.
2. **Vendor look-ahead in price levels.** Yahoo's prices embed adjustments for splits after the request window. Fix: see `docs/DATA_AUDIT.md`.
3. **Impossible returns.** Monthly returns below −100% appeared. Fix: treated as data errors and dropped.

**Process.**
- The invalid runs remain in the append-only trial ledger, so they still count toward the multiple-testing penalty.
- The referee now includes a `data_integrity` threat that automatically fails any long-short mean above 5% per month.

**Rebuild update (2026-11-13):** conflicting same-acceptance-time share facts also
needed a deterministic rule. Two duplicate fact groups produced three legacy/batch
snapshot mismatches across 49,554 engineering queries. Cleaning now selects the
latest reported share date at that instant and requires a strictly later instant
to confirm a large jump; see [D7](DEVIATIONS.md#d7-deterministic-point-in-time-share-ties-and-genuinely-later-confirmation).
This is a data-cleaning correction, not a new empirical return finding.

## F4: H4 winsorization used observations outside development

**Status:** implementation bug reproduced with synthetic data on 2026-11-13; corrected
before the rebuilt-data regression. No new empirical result is established by this test.

`build_panel()` winsorized ratio variables before selecting the development period.
Synthetic future observations changed the development-only `d_roa` cutoffs, violating
the intended separation. Development signals are now selected before fitting cutoffs;
see [D6](DEVIATIONS.md#d6-fit-h4-winsorization-on-development-observations-only).
The prior H4 ledger entries remain available but are not clean evidence of out-of-period
preprocessing invariance. A fresh development run is required. The return holdout remains
sealed, and no validation or holdout regression was run as part of this repair.

## F5: formation selected on future outcomes; monthly residuals were not event-time signals

**Status:** source defects reproduced with synthetic data before rebuilt empirical
H0 estimates, 2026-11-13. See [D8](DEVIATIONS.md#d8-formation-time-eligibility-neutralization-and-missing-return-accounting).

- Removing one next-month return changed a 50-firm formation into 49 firms and
  changed its weights. Missing future outcomes must not determine current holdings.
- Filing-month cohort residuals used the latest filing time in that month, so they
  could not be treated as scores observable at each filing's acceptance time.

Formation now ignores future return availability, uses explicit missing-return
assumptions with counts, and neutralizes latest eligible signals using formation-time
controls. Neutralized event panels remain unevaluated pending a time-safe specification;
raw panels are descriptive diagnostics, not the pre-registered neutralized co-primary.
These repairs do not establish an effect, repair survivorship, or validate historical
estimates. No formal claim-level H1 result is produced by these cosine variants.
