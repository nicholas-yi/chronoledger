# Deviations from pre-registration

## D1: restricting return tests to periods with adequate free-price coverage

- **Logged:** 2026-11-12, **before any return data was loaded or examined.** The only data examined were EDGAR filing indexes and XBRL public-float frames, used for the coverage audit in `docs/DATA_AUDIT.md`.
- **Reason:** free price data covers only 55–71% of large issuers (public float above $500M) in 2011–2018. The missing firms are not random: they include both acquisition targets and failures, so delisting-return bounds can't repair the bias. The project owner chose free data over a paid survivorship-free source.
- **Change:**
  - Return tests use only signals whose knowledge time falls in periods where coverage of issuers with float above $500M is at least 85%. That means float year 2023 onward, so signal knowledge time starts 2023-01-01.
  - New splits:
    - Development: 2023-01-01 → 2024-06-30.
    - **Sealed holdout:** 2024-07-01 → 2026-10-31.
    - Live forward test from public release onward (unchanged).
  - The pre-registered 2011–2022 periods are not used for return tests. They remain available for extraction and reconciliation work that needs no prices.
  - Hypotheses, signal definitions, portfolio rules, thresholds, and delisting sensitivities are unchanged.
- **New secondary test (added for power, also before seeing returns):**
  - A filing-level panel regression of the 3-month post-filing abnormal return (return minus the FF5+UMD-predicted return, with betas estimated over the prior 252 trading days) on the signal.
  - Standard errors are clustered by calendar month.
  - Same sign and threshold rules as the primary test.
- **Consequences, stated in advance:**
  - The holdout has about 28 monthly observations. At a monthly long-short volatility near 3%, t ≥ 3 would need a mean of roughly 1.7% per month.
  - The portfolio test can detect only very large effects. Null results will be reported as uninformative about moderate effects, not as evidence of no effect.
  - Coverage in the new periods is 88–97%, not 100%, so delisting sensitivities still apply.

## D2: defining "prior-knowledge hallucination rate" for the extraction gate

- **Logged:** 2026-11-12, **after** seeing the first benchmark result (Qwen 3.5 4B, 300 cases): 5.0% of raw model outputs failed grounding (28/557). No return data was involved.
- **Issue:** the pre-registration set a gate of "prior-knowledge hallucination rate below 2%" without defining how to compute it. The first implementation counted every rejected output, which includes paraphrased quotes where the partner does appear in the text.
- **Definition adopted:** prior-knowledge hallucination rate = raw outputs naming a partner absent from the entire source chunk, divided by all raw outputs.
- **Transparency:**
  - Both rates are reported side by side in every benchmark result: all ungrounded outputs, and prior-knowledge hallucinations only.
  - The referee checks the prior-knowledge rate against the 2% gate.
  - Because this definition was chosen after seeing a number, the all-ungrounded rate is also shown in the referee report, so readers can apply the stricter reading.
  - Accepted links are unaffected: every accepted link passes deterministic grounding.

## D3: leak-proof robustness representation for H1

- **Logged:** 2026-11-12, after the neologism probe (`docs/FINDINGS.md`, F1) showed
  context-specific "COVID" knowledge in pre-2020 ChronoBERT vintages. **No return data was
  involved.**
- **Change:** H1 is additionally computed with a bag-of-words TF-IDF paragraph representation,
  fitted only on filings known by each as-of date. It cannot encode information from after the
  filing.
- **Rule:** H1 is "supported" only if it meets the pre-registered threshold under ChronoBERT
  **and** keeps its sign with t ≥ 2.0 under TF-IDF. The ChronoBERT threshold is unchanged.


## D4: referee scope and leak criterion for the neologism probe

- **Logged:** 2026-11-12, **after** seeing the extended probe results. No return data was involved.
- **Change 1, criterion:** a probe counts as leakage only if it is context-specific: in a vintage trained before the term existed, the evoking-context rank is at most 10 **and** the control-context rank is at least 100.
  - The original rank-only rule flagged Mounjaro in the 2021 vintage (evoking rank 6), but the control context ranked it 8, so the signal was a generic subword prior, not knowledge.
  - Under either rule, COVID in the 2018 and 2019 vintages remains flagged.
- **Change 2, scope:** the gating representation threat assesses only the vintages this project uses for 2023+ filings (2022, 2023, and 2024). The all-vintage result is still evaluated and reported in every referee run as a **non-gating known issue**.
  - The gate's protection against representation leakage rests mainly on D3: any H1 claim must also hold under the leak-proof TF-IDF representation.
- **Power caveat, stated with the change:** post-coinage vintages also fail to recognize rare brand names (Kenvue, Solventum, Mounjaro). A clean in-use probe therefore rules out only large, high-frequency leaks.

## D5: operational details for H6 (quiet revisions), fixed before H6 data was examined

- **Logged:** 2026-11-12, after `prereg-v2` and **before any H6 data was loaded**. Pre-registration v2 left these choices open, and they are now fixed in `src/asof/quiet.py`, with tests:
  - **Tag:** `NetIncomeLoss` only. Revenue is routinely reclassified, for example for discontinued operations, while net income is not.
  - **Size:** a revision counts if it is more than 1% below the first-reported value, and that first-reported value's absolute size exceeded $1M.
  - **Form:** only regular 10-K or 10-Q comparative columns count. Amendments themselves are not "quiet."
  - **Scale changes:** filings that revise three or more income-statement tags by the same ratio (to three decimals) are treated as unit or scale changes and excluded.
  - **H6(a) outcome:** a 10-K/A or an 8-K Item 4.02 by the same firm within 365 days after the revising filing. Because 10-K/As are often Part III-only amendments, the 4.02-only rate is reported descriptively, but it does not decide success.

## D6: fit H4 winsorization on development observations only

- **Logged:** 2026-11-13, **after** the historical H4 development estimates in the ledger,
  but before a rebuilt-data H4 estimate was evaluated. Identified by source inspection and
  reproduced with synthetic data; no new validation or holdout estimate was examined.
- **Bug:** `build_panel()` computed the 1%/99% winsorization cutoffs on every available
  signal period before `stage_test()` selected development rows. Future-period outcomes
  could therefore change development regressors and outcomes.
- **Correction:** select signals accepted in the existing H4 development window
  (2012-01-01 through 2018-12-31 UTC) before estimating any winsorization cutoffs.
  Next-fiscal-year outcomes remain the first-reported values required by the design.
  The hypothesis, outcomes, 1%/99% levels, and inference thresholds are unchanged.
- **Evidence and consequence:** `tests/test_h4_development.py` demonstrates that adding
  synthetic future observations changed development `d_roa` under the old code and must
  not do so under the correction. Historical entries remain untouched. Rebuilt results
  must be distinguished from the old estimates; this repair does not retroactively
  establish that historical preprocessing respected the holdout boundary.

## D7: deterministic point-in-time share ties and genuinely later confirmation

- **Logged:** 2026-11-13, after the historical F3 development estimates and after
  examining rebuilt share metadata, but before any rebuilt H0 return estimate.
- **Observed:** the rebuilt cleaned shares had two conflicting `(cik, knowledge_time)`
  groups. Across 49,554 engineering snapshot queries, legacy per-query sorting and
  batch sorting selected different values three times. No return estimate was
  needed to discover this.
- **Correction:** within one knowledge instant, use the most recent reported share
  date (`end`), then accession (`accn`), with stable input order for remaining ties.
  Keep one candidate per firm and instant before the existing F3 jump check.
  Confirmation of a large jump must therefore occur at a strictly later knowledge
  time, never from another fact in the same filing. As-of and signal sorts are
  stable so appending future rows cannot reorder existing equal-time rows.
- **Scope:** this is a point-in-time data-cleaning correction, not a new return
  hypothesis or threshold. Numerical optimization equivalence is assessed on the
  same corrected shares for both engines. It must not be described as exact
  replication of the old ambiguous tie handling.
- **Validation:** `tests/test_backtest.py` covers most-recent reported-date
  selection and prevents same-filing pseudo-confirmation. Historical ledger
  entries are retained; fresh trial lineage must pin the corrected code.
