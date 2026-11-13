# Pre-registration v2

**Registered:** 2026-11-12, before any data for the hypotheses below was loaded or examined. Tagged
`prereg-v2`. This document adds to `PREREGISTRATION.md` (v1) and its deviations; it does not change
v1's definitions of H0–H3 except where stated in section 2.

No return data had been examined when this was written. The H0 development backtest had not been
run.

## 1. New hypotheses

| ID | Hypothesis | Outcome | Sample |
|---|---|---|---|
| **H4** | Firms whose 10-K text changes more experience worse future fundamentals. | Next-fiscal-year ΔROA; probability of an earnings decline; probability of a goodwill impairment | XBRL era, all filers including later-delisted ones |
| **H5a** | 8-Ks accepted on Friday after 16:00 ET carry worse news than other 8-Ks (DellaVigna & Pollet 2009, replicated with exact acceptance times). | Abnormal return over trading days +1..+20 after acceptance | Return periods (D1) |
| **H5b** | Late-filing notices (NT 10-K, NT 10-Q) precede negative returns. | Abnormal return +1..+60 | Return periods (D1) |
| **H5c** | 8-K Item 4.02 (non-reliance on prior financials) and Item 4.01 (auditor change) precede negative returns. | Abnormal return +1..+60 | Return periods (D1) |
| **H6** | "Quiet" downward revisions predict formal restatements and negative returns. A quiet revision is a prior-period income-statement value revised down in a later filing's comparative column, with no 10-K/A and no 8-K Item 4.02 in the prior 120 days. | (a) A 10-K/A or 8-K Item 4.02 within 12 months; (b) abnormal return +1..+60 | (a) XBRL era; (b) return periods (D1) |

## 2. Specification changes to existing hypotheses (pre-data)

- **Neutralization (H1 primary; H0 robustness):** each formation month, the change score is replaced
  by its residual from a cross-sectional regression on two-digit SIC industry dummies, log market
  cap, and an indicator for an 8-K Item 2.01 (acquisition or disposition completed) in the prior
  12 months.
  - This removes industry-wide disclosure waves (e.g., ASC 842, CECL, COVID risk factors,
    cybersecurity Item 1C) and mechanical merger-driven text changes.
  - H0 stays raw as the replication primary; the neutralized H0 is reported as robustness.
- **10-Q changes:** 10-Qs are compared with the same fiscal quarter one year earlier, following
  Cohen, Malloy & Nguyen. The signal at a formation date is the change score of the firm's latest
  filing of either form.
- **Co-primary inference for H0, H1, and H3, adding power:**
  1. The v1 monthly long-short portfolio test.
  2. A filing-level event panel: abnormal return over trading days +1..+60, regressed on the
     neutralized signal, with standard errors clustered by calendar month.
  - Abnormal returns are relative to FF5+UMD betas estimated over trading days −260..−21, using
    daily factors.
  - A hypothesis is supported only if at least one co-primary test reaches |t| ≥ 3.2 (the t ≥ 3.0
    bar with a Holm correction for two tests), the other has the same sign, and the D3 TF-IDF
    agreement rule holds where it applies.
- **Reported corroboration (never decides success):** the monthly rank information coefficient (IC)
  with its t-statistic, and daily-rebalanced calendar-time portfolios.

## 3. H4 design

- **Sample:** a reproducible random sample of 1,500 CIKs (seed 20261112) drawn from all 10-K filers
  with XBRL facts and maximum reported public float of at least $50M, with no condition on current
  listing status. Later-delisted firms are deliberately included.
- **Periods**, by 10-K knowledge time:
  - Development: 2012-01-01 → 2018-12-31.
  - Validation: 2019-01-01 → 2021-12-31.
  - **Sealed holdout:** 2022-01-01 → 2025-06-30.
- **Outcomes:** taken from the next fiscal year's 10-K as first reported, never as later revised.
  - ΔROA = NI(t+1)/Assets(t+1) − NI(t)/Assets(t).
  - Decline indicator: NI(t+1) < NI(t).
  - Impairment indicator: GoodwillImpairmentLoss(t+1) > 0.
- **Test:** pooled regression with industry and year fixed effects, two-way clustered by firm and
  year. Controls: log total assets, ROA(t), and sales growth(t).
  - Primary outcome: ΔROA.
  - Holm correction across the three outcomes.
  - Threshold: |t| ≥ 3.0 with the expected sign (more change predicts lower ΔROA and a higher
    probability of decline or impairment).
- **Signals:** the raw Lazy Prices cosine on the full 10-K, and the neutralized version (primary).

## 4. H5 and H6 design

- **Event timing:** event time is EDGAR acceptance in UTC. Abnormal returns start at the first
  close after acceptance. Overlapping events for the same firm within 20 trading days are merged
  into the first one.
- **Thresholds:**
  - H5a–H5c and H6(b) replicate published effects: |t| ≥ 2.0 with the expected sign, with a Holm
    correction across these four tests.
  - H6(a) is a new signal: |t| ≥ 3.0.
- **H6 exclusions** (mechanical revisions): per-share and share-count tags (splits), and revisions
  of exactly the same relative size across all income-statement tags in one filing (unit or scale
  changes).
- **Holdout:** H5–H6 return tests use the D1 splits. H6(a) uses the H4 splits.

## 5. Process

- Every evaluated configuration is logged in the trial ledger with data and code lineage (git
  commit, uncommitted-changes flag, and SHA-256 hashes of input files).
- The referee gate applies to every reported result.
