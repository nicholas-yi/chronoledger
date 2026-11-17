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

## D8: formation-time eligibility, neutralization, and missing-return accounting

- **Logged:** 2026-11-13, after the historical H0 estimates, before any rebuilt
  empirical H0 estimate. Discovered by source inspection and synthetic invariance
  tests, not by choosing a better return estimate.
- **Future-availability bug:** `form_portfolios()` dropped firms without a known
  next-month return before assigning quintiles and weights. Hiding one future
  outcome changed a synthetic 50-firm formation into 49 firms. Formation now uses
  only known signals, shares, current prices, and size breakpoints.
- **Missing outcomes:** the pre-registered primary 0% assumption is explicit in
  `Config.missing_return`; -30% and -100% sensitivities use identical formation
  sets and are separately logged. Gross returns and drift both use the declared
  assumption, and missing long/short observations are counted. These are bounds
  on unpriced observations, not observed delisting returns, and do not restore
  firms absent from the current-ticker universe or repair F2.
- **Neutralization:** the legacy implementation pooled filings by their acceptance
  month and used that month's latest filing time. It could use information not
  known at an earlier event or even at the month's formation close. Monthly
  residuals are now fit on each variant's latest eligible firm signals and controls
  known at its formation close, as intended by pre-registration v2. They are not
  reused as filing-time event scores.
- **Industry-source limitation:** SIC is still the fixed mapping in the current SEC
  bulk entity metadata, not a historically timestamped industry table. Formation
  canaries establish timing for shares, filings, and acquisition events under that
  fixed mapping; they do not prove historical SIC availability. H4 and neutralized
  H0 estimates remain conditional diagnostics until that proxy is qualified or
  replaced before confirmatory evaluation.
- **Event panels:** raw change panels remain descriptive pipeline diagnostics.
  Neutralized panels are explicitly **not evaluated** until an event-time
  neutralization contract is fixed. The co-primary success rule cannot be claimed
  satisfied from these outputs. The neutralized H0 variants labeled `H1n` in the
  historical ledger are not the claim-level H1 signal.
- **Equivalence scope:** legacy optimization comparisons use the same corrected
  shares (D7) and complete-return rows, solely for engineering comparison. They
  test the unchanged numerical operations, not equivalence to the deliberately
  removed future-outcome selection or legacy neutralization design. Production
  formation never uses that complete-return restriction.
- **Evidence:** focused tests cover future-outcome availability, the three declared
  missing-return assumptions and counts, and post-close filing/share/acquisition
  events that must not alter formation residuals. Historical runs are retained;
  rebuilt results must disclose these corrections as well as fresh-data differences.

## D9: apply the existing price-return integrity guard to event inputs

- **Logged:** 2026-11-13, after the historical event estimates and rebuilt-data
  engineering comparisons, but before any fresh H0/H4/H6 hypothesis estimate.
- **Observed:** auditing all 2,733 usable guarded histories found two daily returns
  below -100% and one non-finite return. One sub--100% return was on 2023-01-03,
  inside the development period. F3's monthly guard had not been applied to the
  daily series used by the event engines.
- **Correction:** daily and monthly price ratios share one guard: ratios producing
  returns `<= -1` or non-finite values are marked missing, with warning counts.
  Daily returns do not forward-fill missing adjusted prices. All four event
  loaders use the shared helper, and H0 reports its daily exclusion count.
  This is the existing vendor-price cleaning policy, not an assertion that a
  genuine -100% delisting payoff is impossible; such payoffs require an explicit
  source or the separately reported missing-return assumption.
- **Limit:** nonpositive vendor-adjusted levels remain a source-quality warning.
  Removing an unusable ratio does not validate the rest of that series or fix
  survivorship. Raw event panels remain development diagnostics; neutralized
  panels remain unevaluated under D8. H5 is not rerun by this repair, and H6(b)
  remains invalid under F2.
- **Validation:** the regression test covers zero/negative denominators,
  non-finite returns, missing-price gaps, retained valid returns, and visible
  exclusion counts. Historical ledger entries are not edited.

## 2026-11-13 bounded implementation review (uncommitted, no new trial)

This review occurred **after** the recorded H0/H4/H6 development estimates.
Only source inspection and synthetic fixtures were used; no empirical configuration,
new source, scoring rule, cutoff or hypothesis was evaluated. No tag was created.

- `CarEngine.car()` selected complete firm returns but not complete factor rows,
  unlike `car()`'s joint `dropna()`. Synthetic missing market-factor rows produced
  an SVD exception, and missing risk-free rows produced NaN where the reference
  returned a finite CAR. The fast path now uses the reference's same complete-row
  rule. This does **not** change either engine to scheduled-session windows or
  resolve the event-anchor ambiguity.
- H4's decline label compared next income with a missing current income and
  emitted zero. It now requires both income values to be observed, preserving
  `NI(t+1) < NI(t)` and missing versus observed no-decline. Existing regressions
  also require current ROA, but no empirical impact or unchanged result is claimed.
  The separate missing-impairment-tag-to-zero assumption is **not** changed.

The original ledger, checked-in results, referee report, source pins and tags remain
historical evidence, not validation of these local changes. Any later empirical
rerun requires an approved queue/resource decision, the usual trial lineage, and
explicit review of affected source contracts. Design alternatives in the
[bounded gate packet](DATA_AUDIT.md#bounded-gate-advancement-2026-11-13)
remain proposals; this note does not authorize them or a new numbered/tagged design.

## 2026-11-13 Lead-D3a: separate synthetic planner (not a registered-runner change)

After the historical development results, the owner explicitly selected
`timing_scope='separate-synthetic-planner'` under CL-P2. The opt-in
[`asof.timing.plan_return_window`](../src/asof/timing.py) is implemented and tested
only on caller-supplied synthetic schedules and availability metadata.
Strictly later ready/deadline eligibility, hypothetical entry-close-to-next-close
intervals, fixed scheduled estimation/outcome slots and explicit support/censoring
are specified in the [v0.2 contract](DATA_AUDIT.md#lead-d3a-opt-in-synthetic-planner-v02).

This is not a new numbered scientific deviation, empirical configuration or tag.
No historical runner, old clock/CAR default, source license, endpoint, SIC rule,
neutralization/overlap policy, hypothesis, score or date was changed by this release.
No result or ledger entry is rewritten, and no held-out input was inspected.
The earlier two local corrections remain identifiable rather than being attributed
to this planner. Any real-data application or runner migration requires its own
accepted design and explicit evaluation/resource approval; the rest of D3 and
Lead-D2/D4-D9 stay open.

## D10: disclose the historical 10-Q/A quiet-exclusion discrepancy

- **Logged:** 2026-11-13, **after** the recorded H6 development results and their
  reproduced estimate. Identified by source inspection, not by a new evaluation.
- **Discrepancy:** v2/D5 describe no prior 10-K/A or Item4.02 within120days.
  `quiet_down_revisions()` has always included **both** 10-K/A and10-Q/A in
  that prior-amendment exclusion. This implemented rule differs from the narrower
  written specification; historical entries and results are retained unchanged.
- **Action:** disclosure only, no historical code/label change or H6 rerun.
  Lead-D6's **future**, separately registered quiet construct excludes both forms;
  that does not automatically add10-Q/A to the formal365day endpoint or turn
  administrative amendments into substantive restatements.
- **Boundary:** no tag or holdout opening is authorized. This numbered protocol
  discrepancy disclosure is not a new coordination decision; the operative
  future decision is Lead-D6. No source/rights or scientific acceptance follows.

## D11: apply the missing-income label and missing-factor parity corrections

- **Logged:** 2026-11-13, after the historical development results and synthetic
  regression tests, **before** the single Batch B H4/H0 development reruns.
- **H4 correction:** a decline label requires observed NI(t) and NI(t+1).
  Missing current income previously compared false and became zero. The formula,
  dates, controls, winsorization, outcomes and configuration otherwise stay fixed.
  Existing current-ROA controls may already exclude affected rows; impact is to
  be measured, not assumed zero.
- **CAR parity:** the fast engine now excludes missing factor/RF rows just as
  reference `car()` does. This fixes synthetic SVD/NaN mismatches without moving
  to the prospective session planner or changing legacy valid-observation windows.
  Cached permitted-period factor missingness is inspected before the rerun.
- **Execution boundary:** one H4 test stage and one output-only-extended H0 run;
  original entries/results remain recoverable by revision, new attempts append.
  Compare all H0 pre-existing summary fields exactly; unexpected differences stop
  that step, with no tuning or retry toward a preferred number. No H6/H5 rerun,
  source substitution, new hypothesis, tag or holdout access is authorized.

## D12: require established robust significance checks for future acceptance

- **Approval/provenance:** user approval through Lead, 2026-11-13 23:57 ET,
  followed by the Lead's primary-source rounding/tail correction. Recorded after
  prior development estimates and Batch A synthetic size results, **before**
  Batch E verification and any holdout evaluation. This is future-only; no
  frozen estimate, statistic, sign, registered N, split, cost or result is changed.
- **Supersession:** the unexecuted **Lead-D10 c*** proposal is retired. Do not run
  its 216,000 + 30,000 + 4,000 allocation or introduce empirical max-DGP critical
  values. Lead-D10 is a coordination label, not the already occupied D10 number.
- **Additional necessary condition:** retain every original registered gate and
  additionally require the matching robust procedure to reject in the registered
  expected direction at the original bar's two-sided-equivalent normal level:
  `2*norm.sf(bar)` (2.0: 4.550%, 3.0: 0.270%, 3.2: 0.137%). This cannot rescue a
  registered failure. Missing evidence, infeasibility, unqualified assumptions,
  unreliable geometry or unattainable resolution yields **undetermined**, never pass.
- **Monthly:** EWC uses the full alpha-regression score/bread with all six factors,
  unrestricted residuals, type-II cosine weights, `floor(0.4*T**(2/3))` and Student
  `t_nu`. At T=17/18/28, nu=2/2/3. The initial nearest-rounding instruction was
  corrected before commitment/execution; no E3 run used it. NW-fixed-b is reported,
  not the deciding monthly test: `S=ceil(1.3*sqrt(T))`, `maxlags=S-1`, weights
  `1-j/S`, and KV(2005) Table I interpolation in b. Frozen NW six-lag behavior
  still means S=7 and is unchanged. The table lacks the 99.5th and rarer percentiles:
  NW two-sided 1%/0.27% are unavailable, not ordinary-t/normal substitutes.
- **H4:** an additional IM test uses seven year-group coefficient estimates,
  equal weighting and `t_6`. Within-group constants/redundancies can be absorbed
  without changing the nuisance column space; an unidentified signal or any
  infeasible registered group prevents evaluation. No opportunistic q reduction.
  Independent approximately Gaussian, unbiased common-target group estimates
  remain substantive assumptions; group count does not establish them.
- **Event panels:** WCR bootstrap clusters by registered month with Webb
  six-point weights, restricted-null generation and re-studentization. Inclusive
  absolute tails, full enumeration when bounded, otherwise explicit-seed
  `(1+exceedances)/(B+1)` are fixed API conventions. IM-by-month is a required
  **reported cross-check**, never the deciding statistic, a veto or a rescue.
  The unrestricted one-sided 5% heteroskedastic-Gaussian IM guarantee is limited
  to q<=14; q=17/28 is not presented as covered.
- **Attainability/precision:** retain bootstrap granularity floors (seven-cluster
  Rademacher cannot go below 1/64; B=399 plus-one cannot go below 1/400). For EWC
  nu<=3, future bars>=3 remain undetermined pending rare-level qualification:
  `t_2` critical values are about 19.207/26.947 at bars3/3.2; `t_3` about
  9.219/11.605. These are finite mathematical critical values, **not** a proof of
  mathematical impossibility or an implementation bug. The hold is conservative,
  not a new simulated cutoff. Zero/numerically-zero variance is explicitly
  unavailable, including IM's otherwise paper-specific zero-statistic convention.
- **Decision interface:** endpoint-specific robust thresholds must be supplied
  from future registration, not selected after outcomes. The monthly v1 bar and
  the qualifying co-primary's 3.2 requirement cannot be weakened. The old D4
  predicate is named `registered_co_primary_decision` for historical/diagnostic
  use only; `co_primary_decision` now requires robust endpoint checks.
- **Qualification:** Batch E's frozen 5% Monte Carlo adoption rule and estimator
  assumptions are additional requirements, not scientific acceptance. A
  synthetic reliability label cannot clear P0, F2/F4, measurement, economic
  effects, source rights, borrow/fill or holdout permission. No robust procedure
  is applied to development data in this batch. No push or tags.

Equations, source pins, the pre-execution allocation and its limits are in the
[Batch E contract](DATA_AUDIT.md#batch-e-established-tests-and-frozen-verification-contract).

## D13: exploratory KPI disclosure screen crossed reserved calendars

- **Logged:** 2026-11-17, **after** the incident, under the owner's CL-KPI-D13
  decision. This records exposure and a prospective access correction, not a
  new hypothesis, a successful experiment or retrospective holdout clearance.
- **Bug:** the exploratory cached KPI-omission screen, frozen at `a9d788f`,
  selected its roster without a reserved-window eligibility filter. Being
  before the D1 return holdout did not exclude H4/H6(a) validation, holdout or
  outcome-source windows. The `a9d788f` roster is **superseded, not to be used**;
  its original plan, manifest, commits and stopped receipts remain historical.
- **Access clarification (verbatim CL-KPI-D13 addendum):**

  (a) preparation SHA-256-fingerprinted all 192 pinned compressed annual cache objects, reading their compressed bytes;

  (b) 4–6 annual bodies were decompressed and parsed;

  (c) the full bulk metadata parquet was fingerprinted, and decoded columns were filtered for 2021-07-01..2024-06-30, including Items that can carry H6 event codes;

  (d) 93 8-K context records were metadata only, with zero bodies read;

  (e) the 188 annual and 93 context records fall within H4/H6(a) 2022-01-01..2025-06-30 and the H6(a) follow-up calendar through 2026-06-30; 4 annuals fall in the 2019–2021 validation period; 0 fall in the D1 return holdout from 2024-07-01;

  (f) no fundamentals values, labels, joins, prices, returns or models were evaluated, but the raw sources may contain outcome-bearing material, so exclusion is not certified.

- **Additional limits:** three decompressed reads are checkpoint-confirmed;
  the crash leaves the exact additional resource in the next case unknown.
  No fundamental values, outcome labels or joins, prices or returns were
  extracted. No human viewed filing text and zero usable metric cases were produced.
  The old static `holdout_opened=false` field is not an exposure audit.
- **Prior calendar use (context only):** the same July 2021-June 2024
  bulk-metadata calendar was already used by earlier
  [H0](../scripts/h0_data.py) and [P0](../scripts/p0_acceptance_audit.py)
  development work. This does not authorize or cure the additional exposure,
  establish exclusion of outcome-bearing material, or restore untouched status.
- **Quarantine:** original outputs and the metadata-only exposure audit remain
  under ignored `data\kpi_omission_v1`; the stopped summary was removed from
  untracked `results`, not published as scientific evidence. No source was
  reprocessed after the stop and no trial-ledger row was appended.
  The private audit is referenced only by path and fingerprint:
  `data\kpi_omission_v1\reserved_window_audit.json`, SHA-256
  `b0f1c4306cf592f9d72d03fb5670f4f0fc61ae5b35bf11d5b178391da30dff92`.
- **Correction:** the shared, mandatory eligibility check is implemented once in
  [document_scope.py](../src/asof/document_scope.py); guarded document-reading
  entrypoints call it before body reads or fingerprints. The KPI wrapper delegates
  to that shared check rather than duplicating the policy; see
  [entrypoint coverage](DOCUMENT_SCOPE.md#enforced-entrypoints).
  Acceptance/knowledge dates, period ends and used context must all pass;
  unknown/unparseable dates fail closed. Parser repairs and guard verification
  use invented fixtures.
  Any rescoped KPI execution requires development-only eligibility, a new
  frozen roster and the separate minimum-cache-size decision.
- **Evidence and consequence:** the retained private scope audit distinguishes
  compressed-byte fingerprints, confirmed body reads, possible additional
  reads, next-year source relationships and H6 follow-up envelopes. This adds
  to the existing D6 limitation: **no future H4/H6(a) holdout evaluation may be
  described as untouched**. Hypotheses, outcomes, registered windows and
  thresholds are unchanged. No ledger row, holdout release, push or tag follows.
