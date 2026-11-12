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

