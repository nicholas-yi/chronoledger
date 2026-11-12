# Pre-registration (v1)

Registered before any return data was loaded into this project. The git tag `prereg-v1` marks this
document. Any later change is logged in `docs/DEVIATIONS.md` with date, reason, and whether it was
made before or after seeing returns.

## 1. Hypotheses

| ID | Hypothesis | Type |
|---|---|---|
| H0 | **Replication.** Firms whose annual 10-K text changes most underperform firms whose text changes least (Cohen, Malloy & Nguyen 2020, "Lazy Prices"), measured with bag-of-words cosine similarity. | Replication of a known effect |
| H1 | **Claim-level change.** A reconciled, claim-level change score (new, superseded, and retracted claims in risk factors, MD&A, and customer disclosures) predicts returns incrementally to H0. | New signal |
| H2 | **Hidden links.** Customer-momentum predictability (Cohen & Frazzini 2008) exists for LLM-extracted customer links below the 10%-of-revenue disclosure threshold, incrementally to links at or above it. | New signal |
| H3 | **Propagated change.** A customer's claim-level change score predicts its suppliers' returns. | New signal |

Direction is fixed in advance: high change → lower future returns (H0, H1, H3); supplier returns follow lagged customer returns (H2).

## 2. Sample and time

- **Filers:** SEC registrants filing form `10-K` (amendments `10-K/A` feed reconciliation only), common equity matched to a price series.
- **Knowledge time:** EDGAR `acceptanceDateTime` (verified to be true UTC). A signal is usable only from the first 16:00 ET market close strictly after acceptance.
- **Periods**, assigned by the signal's knowledge time:
  - Development: 2011-07-01 → 2018-12-31. All design choices and tuning happen here.
  - Validation: 2019-01-01 → 2021-12-31. Used once, for selecting among development candidates.
  - **Sealed holdout:** 2022-01-01 → 2026-10-31. Opened once, after the analysis code is frozen and tagged.
  - Live forward test: from public release onward, with weekly signal snapshots committed by CI.
- The XBRL era (mid-2011 onward) is used because size filters need point-in-time shares outstanding (`dei:EntityCommonStockSharesOutstanding`).

## 3. Models and look-ahead controls

- **Representations:** ChronoBERT (`manelalab/chrono-bert-v1-YYYYMMDD`), always the latest vintage strictly before the filing's acceptance date. Filings after 2024-12-31 use the 2024-12-31 vintage.
- **Extraction:** local open-weight models (Qwen 3.5 via Ollama). Extraction only records what the filing text states; LLMs never score sentiment and never predict returns.
- **Gate before extraction outputs are used in any test:**
  - prior-knowledge hallucination rate below 2% on the counterfactual entity-swap benchmark;
  - recall at least 0.80 and precision at least 0.90 on synthetic injected disclosures.
  - If either gate fails, H1–H3 are reported as not testable rather than tested with a weaker extractor.
- **Invariance:** every function producing a signal, universe, or weight must pass the time-travel invariance test (`tests/test_invariance.py`). Canary tests must confirm that known-leaky code is caught.

## 4. Portfolio construction (fixed)

- Rebalance monthly at the month-end close, holding for one month.
- Each month, sort firms with a usable signal into quintiles. The long-short portfolio is long the low-change quintile and short the high-change quintile (H0, H1, H3). For H2, it is long suppliers of the top customer-return quintile and short suppliers of the bottom quintile.
- **Primary weighting:** value-weighted, with market cap equal to as-of XBRL shares outstanding times price. Secondary weighting: equal-weighted.
- **Filters at formation:** price of at least $5; market cap at or above the NYSE 20th-percentile breakpoint (Ken French breakpoints).
- **Costs:** half-spread estimated from daily close, high, and low prices (Abdi & Ranaldo 2017). Cost per rebalance equals 2 × half-spread × turnover. Primary results are net of costs.

## 5. Inference

- **Primary statistic:** monthly net long-short return regressed on FF5 + UMD, with Newey-West standard errors (6 lags).
- **Thresholds:**
  - H0 (replication of a known effect): t ≥ 2.0 with the pre-registered sign.
  - H1–H3 (new signals): t ≥ 3.0 (Harvey, Liu & Zhu 2016), with the pre-registered sign, in the sealed holdout.
- **Multiple testing:**
  - Every configuration evaluated on development or validation data is logged in the trial ledger.
  - The Deflated Sharpe Ratio uses N = the number of distinct logged configurations.
  - Probability of backtest overfitting is computed via CSCV with 16 blocks across all logged configurations.
- **Fitted models:** combinatorially purged cross-validation with an embargo of at least 1 month.
- **Robustness (reported, not used to declare success):** q5 factors; equal weighting; size terciles; pre- vs. post-publication periods of the original papers; recession months; degree-preserving rewired graphs (H2, H3); shuffled filing dates; placebo model vintages.

## 6. Data limitations accepted in advance

- **Survivorship:** prices come from a free source that omits most delisted securities. Mitigation:
  - Delistings are identified from EDGAR Form 25 and Form 15 filings and from firms that stop filing.
  - Every result is re-estimated assuming delisting returns of 0%, −30%, and −100% for those firms' missing months (Shumway 1997 motivates −30%).
  - Coverage by year is reported.
  - The primary result is the 0% case, and all three are reported side by side.
- **Statistical power:** the holdout has about 58 months. With a monthly long-short volatility near 3%, t ≥ 3 requires a mean of roughly 1.2% per month. A null holdout result is therefore weak evidence of no effect, and will be described that way.
- **Index constituents:** no official historical constituent list is used. The universe is defined by EDGAR filers and the filters above.

## 7. What counts as success

- **A hypothesis is supported** only if it meets its threshold, keeps its pre-registered sign under all three delisting assumptions, and passes the Socratic referee gate (every threat at level 4 or higher).
- **Otherwise it is reported as not supported.** Exploratory findings are labeled as such, never promoted to headline results, and never described as a tradable edge.
