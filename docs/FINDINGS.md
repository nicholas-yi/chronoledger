# Findings

Findings are recorded as they occur, including ones that weaken this project's own design.

**Latest Batch B status:** development reruns completed once, but exact numerical
reconciliation and claims-roster identity gates are **BLOCKED**; see F7/F8 below.
No retry, tolerance relaxation, identity remapping or DSR calculation was used to
make them pass. Earlier successful engineering checks remain evidence for their
own revisions, not resolution of these new discrepancies.

## Development rerun reconciliation (2026-11-13)

**Current status: development diagnostics only, no supported hypothesis or tradable edge.**
The numerical runs used [execution revision db73f74](https://github.com/nicholas-yi/chronoledger/tree/db73f742214239f4e4b1a0515784279f492da3ec).
The [ledger](../results/trial_ledger.jsonl) retains all 18 original entries, including invalid runs,
and appends new engineering checks and evaluations with input and runtime lineage.
All five common H0 input-file hashes changed on rebuild; that alone does not distinguish
data-content, serialization, runtime, and code effects.

### H0 cosine variants: the other three are now rerun

| Variant | Monthly observations | Net mean / month | Alpha t |
|---|---:|---:|---:|
| `v1_10K_raw` | 17 | -0.80485% | -0.4543 |
| `v2_latest_raw` | 18 | +0.29079% | +1.4575 |
| `v2_latest_neutral` | 18 | -0.29411% | -2.3307 |
| `v2_10K_neutral` | 17 | -1.68946% | -2.3592 |

These are net long-low-change/short-high-change portfolios, so positive is the registered
direction. None establishes support. The first variant is close to the historical partial
-0.80497% result, but D7/D8 correct ties, eligibility and neutralization; this is not a
claim of exact replication of the old implementation.
No held long/short leg lacks its next-month return, so all three missing-return assumptions
coincide. That is not evidence that missing firms or survivorship have been repaired.
The [full output](../results/returns_h0_development.json) includes raw descriptive event panels;
neutralized event panels remain unevaluated. `H1n` is a historical ledger label for neutralized
cosine variants, not a tested claim-level H1 signal.

The full process took 61.073 seconds with validated prepared inputs, including all 12 monthly
configurations. Every numeric metric exactly matched the earlier raw-preparation run.
That earlier run took 298.712 seconds and failed the timing target; it remains recorded.
Snapshot construction separately took 154.955 seconds and exactly round-tripped 57,195 monthly
rows and 2,733 daily series (14,433,060 returns). These are local component/process observations,
not a hardware-independent performance guarantee.

### H4: no-support conclusion reproduced, not identical estimates

| Signal -> outcome | Historical t | Rebuilt t | Observations, unchanged |
|---|---:|---:|---:|
| Neutralized -> dROA | -1.2475 | -1.2007 | 2,655 |
| Neutralized -> earnings decline | -0.0151 | -0.0616 | 2,658 |
| Neutralized -> impairment | +1.1836 | +1.2221 | 2,689 |
| Raw -> dROA | -1.2049 | -1.1520 | 2,655 |
| Raw -> earnings decline | -0.0745 | -0.1836 | 2,658 |
| Raw -> impairment | +1.0191 | +1.0604 | 2,689 |

All absolute t values remain below 1.23, versus the 3.0 bar. Directions for dROA and
impairment remain as expected; decline remains wrong-sign and near zero.
With development-only winsorization (D6), the dROA mean changes from -2.2972% to -4.0996%
and the primary coefficient from -19.9324 to -36.1710 in native score/ROA units.
Firm counts remain 607/608/614 by outcome, with only seven year clusters. The current-SIC
proxy is not historical industry data. See [the full output](../results/h4_development.json).
Original byte-identical inputs and runtime were not available, so no numerical decomposition
of each source of change is claimed. The repair does not restore H4's untouched holdout status.

### H6: exact H6(a) reproduction; H6(b) still invalid

Every reported H6(a) metric exactly reproduces the historical entry: adjusted coefficient
0.04202909 (+4.20 percentage points), t = 1.7377173, 22,745 filings, 499 quiet filings,
and 1,103 firms. Observed formal-outcome rates are 17.8357% versus 13.7238%; 4.02-only
descriptive rates are 4.8096% versus 1.8161%. This does not meet the new-signal bar of 3.0.
The counting unit is a filing, with year fixed effects and firm-clustered inference;
the broad outcome includes amendments that are not earnings restatements.

The fresh H6(b) pipeline diagnostic is CAR +4.5792%, t = 1.7708, 316 events and 15 month
clusters, close to the historical value. It remains **INVALID under F2**, not a return finding.
See [H6 output](../results/h6_development.json). H5 return tests were not rerun here.
The referee did recompute the distress-coverage contrasts: NT 0.30, Item 4.02 0.74 and
Item 4.01 0.56 relative to all 10-K filers, below the 0.8 diagnostic floor.

The executable referee passes its defined gating checks; that is not scientific acceptance.
The current-SIC proxy, fixed-16:00 session clock, valid-observation CAR indexing, incomplete
neutralized co-primary, and historical H4 contamination remain qualification/approval issues.
No holdout test, paid-data purchase, market-data-key use, or publication beyond this existing
public repository was performed.

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
- ChronoBERT vintages cannot be assumed perfectly leak-free. At the initial discovery, before D4,
  this failed the representation threat and blocked the gate. D4 later scoped gating to the in-use
  vintages; the all-vintage failure remains visible as a known, non-gating issue.
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
preprocessing invariance. The corrected development run is reconciled above; it does not restore
an untouched H4 holdout. No validation or holdout regression was run as part of this repair.

## F5: formation selected on future outcomes; monthly residuals were not event-time signals

**Status:** source defects reproduced with synthetic data before rebuilt empirical
H0 estimates, 2026-11-13. See [D8](DEVIATIONS.md#d8-formation-time-eligibility-neutralization-and-missing-return-accounting).

- Removing one next-month return changed a 50-firm formation into 49 firms and
  changed its weights. Missing future outcomes must not determine current holdings.
- Filing-month cohort residuals used the latest filing time in that month, so they
  could not be treated as scores observable at each filing's acceptance time.

Formation now ignores future return availability, uses explicit missing-return
assumptions with counts, and neutralizes latest eligible signals using formation-time
size/event controls under a fixed SIC mapping. The SIC mapping is current metadata,
not verified historical classification, so neutralized H0 and H4 interpretations
remain conditional on that proxy. Neutralized event panels remain unevaluated pending a time-safe specification;
raw panels are descriptive diagnostics, not the pre-registered neutralized co-primary.
These repairs do not establish an effect, repair survivorship, or validate historical
estimates. No formal claim-level H1 result is produced by these cosine variants.

## F6: the F3 price-return guard did not cover daily event inputs

**Status:** confirmed by an exhaustive rebuilt-cache audit before fresh hypothesis
estimates. Across 2,733 usable daily histories, two returns were below -100% and one
was non-finite; one sub--100% observation fell on 2023-01-03. The audit also found
503 nonpositive vendor-adjusted observations during 2021-2022. The vendor-level
cause is not established.

The monthly guard alone did not protect event-study estimation windows. Daily
loaders now use the same explicit price-ratio guard, log exclusions, and preserve
missingness rather than forward-filling; see [D9](DEVIATIONS.md#d9-apply-the-existing-price-return-integrity-guard-to-event-inputs).
This is not a reconstruction or independent validation of vendor total returns.
Historical event estimates retain their original lineage and limitations, and F2
still invalidates distress-event inference with the current-ticker universe.

## F7: H0 pair metadata disagrees with the bulk filing identity/acceptance metadata

**Status:** observed during the metadata-only claims-roster preflight in Batch B,
before any claims draw. Of16,226 permitted-development candidate pairs, all
accessions matched and all forms agreed, but **305CIK fields and124acceptance
timestamps** differed between the pair input and current bulk filing metadata.
These counts can overlap; they are not summed as distinct events.

The [blocker artifact](../results/batch_b_claims_roster_blocker.json) preserves
counts, dtypes and ten metadata-only examples. The two CIK columns are both int64,
so this is not explained by a float/int comparison. Neither source has been
adjudicated as correct. Co-registration, historical source changes or other causes
are possibilities, **not established explanations**. Impact on historical signals,
identity joins or return attribution has not been evaluated.

The60-case claims selection stopped before sampling; its
[roster status](../results/claims_audit_roster.json) has zero cases and an explicit
blocker. A header-only blank annotation template is not a completed roster.
No CIK/time was remapped and no difficult case dropped. The independent20-case
endpoint metadata roster was drawn once under its separate fixed seed stream;
it contains no endpoint labels or certified complete observation.

This is a new source-integrity release blocker, not proof that all prior results
are wrong or a reason to silently replace their inputs after seeing returns.
F2/F4/F6 and holdout-isolation restrictions remain. The existing technical referee
does not automatically test this cross-source discrepancy; a technical PASS does
not clear F7.

## F8: single-thread Batch B does not reproduce every recorded summary bit-for-bit

**Status:** exact-comparison stop gates triggered; no empirical retry or tuning.
Source/protocol checkpoint `fb0a333` records D11 before the one H4 and one H0 run.

- **H4:**399development panel rows lack current NI, and all399 also lack the
  existing current-ROA control. Sample counts and outcome means matched, but
  12coefficient/t fields differed from the recorded revision, maximum absolute
  difference **6.466e-13**. [H4 impact evidence](../results/batch_b_h4_impact.json).
- **H0:** all net/gross means, alphas and raw event summaries matched exactly.
  Neutralized variants' mean IC and IC-t did not:16stored field differences
  across primary and sensitivity copies, representing four unique metric paths.
  [Exact comparison](../results/batch_b_rerun_comparison.json). Changes are small,
  but they fail the required **exact** contract; no tolerance was substituted.
- The factor audit found no missing or non-finite factor rows in the fingerprinted
  permitted prefix, so the CAR missing-factor fix cannot explain these changes
  for that vintage. A numerical-order/near-tie explanation is **unverified**;
  no post-result thread/tie/rounding change was attempted.

Current-vintage DSR was **not calculated** after the failed gate; the
[diagnostic status](../results/current_vintage_diagnostics.json) records the stop,
not a computed probability. PBO remains not_estimable with17/18monthly observations.
Monthly series were persisted as output only (210rows across12existing configurations),
without changing config hashes; new attempts remain in the append-only ledger.

The rounded no-support interpretation is unchanged, but that is not exact
reproducibility or scientific acceptance. Numerical provenance and the source
disagreement in F7 need explicit review before additional affected evaluations.
No holdout was opened or new source substituted.

## F9: P0 acceptance-time authority is not uniformly certified by JSON Z fields

**Status: P0 BLOCKED; no safe global time correction selected.** The read-only
[authority audit](../results/p0_acceptance_authority_audit.json) used 46 audited SEC
HTTP attempts cumulatively, bounded at 150 and <=2 requests/sec through the project
client/cache. No vendor/price request, ingestion mutation or empirical evaluation.
This discovery is **after the recorded development results**. A later accepted
input correction needs a numbered deviation before rerunning; existing ledger
rows and the frozen preregistration are not rewritten.

The 124 development pair/bulk acceptance disagreements are 75 offsets of +4 hours and
49 of +5 hours (bulk minus pair), matching seasonal ET/UTC offsets. Across the full
21,502 H0 signal rows, 165 differ: 105 at +4 and 60 at +5. That pattern alone does **not**
establish which side is wrong or that pair times are early.

Of 26 planned authority samples, 23 were attempted: 22 filings' own header and index
wall times agreed; the first historical H4 header URL returned 404, leaving all four
historical-H4 checks incomplete. Under the documented Eastern acceptance-clock
interpretation, 21 of 22 sampled pair instants match header-derived UTC, versus 7 bulk
instants. In all 14 sampled differing cases, **pair matches and bulk is 4/5 hours late**.
The two originally reported Kroger examples are in this category:

- `0001558370-23-004767`: header/index 2023-03-28 08:09:40, ET-derived 12:09:40 UTC;
  pair 12:09:40Z, bulk 16:09:40Z.
- `0001558370-24-004603`: header/index 2024-04-02 16:15:17, ET-derived 20:15:17 UTC;
  pair 20:15:17Z, bulk 2024-04-03 00:15:17Z.

One **internally agreeing** case is also wrong under that clock:
`0000003545-24-000034` has header/index 2024-02-07 16:54:22, ET-derived 21:54:22 UTC,
while both tables say 2024-02-08 02:54:22Z, five hours late. Agreement between
internal paths therefore cannot certify the source time.

Original cached API traces for 118 differing full-signal records (112 root-recent,
6 historical-page) all equal the stored pair timestamp, not bulk. Six other
differing CIKs lacked that API cache. Cache presence/value agreement is not a
per-row ingest-branch receipt: the DB did not persist the path/source vintage
that wrote each row. Raw bulk sample values already contain the discrepancy,
so changing only an ISO parser cannot reconstruct an unknown true instant.

### Actual impact versus conditional column substitution

For the 22 successful header/index cases, pair-to-ET-header comparison changes
**0 first registered closes, 0 formation-eligibility decisions and 0 sample-local
latest-filing choices**. The selector uses only sampled records, not complete
formation cross-sections. This is sample evidence,
**not proof of zero full-sample look-ahead**. No early-information close was
identified in that sample; the global size/direction remains unknown.

Replacing pair/DB times with bulk would change 22 development first-close
assignments and 2 latest-signal firm/month choices (31 closes over all H0 rows).
These are **conditional internal-column comparisons, not measured true correction
or look-ahead impacts**. For 49,821 H5-event metadata rows in the DB/bulk overlap,
235 timestamps differ and 16 registered-close assignments differ conditionally.
For 222,729 older 2012-2018 metadata overlap rows, 5,637 times differ in both directions,
939 closes and 3 UTC-year assignments differ conditionally. That older overlap is
not the complete H4/H6 population or an H6 quiet-event rerun.

All 5,270 H4 development pairs agree with their bulk source, a path-consistency
tautology, not independent authority. H6a uses the same bulk path; 24,432 regular/
amendment input rows were counted for the existing H4 issuer sample. Bulk-only
issuers/quiet-event dates were not exhaustively header-certified. No timestamp,
CIK, production table or snapshot was rewritten, and no H0/H4/H5/H6 rerun followed.

### Co-registrants and authority limits

No H0 signal accession appears under multiple CIKs. There are 404 full-signal
pair/bulk CIK disagreements (305 in development); in 4 sampled co-filed headers both
CIKs appear. This supports a one-accession/multiple-filer representation issue,
not an unambiguous duplicate signal to delete. Bulk's accession-only dedup
can collapse those relationships. Choosing the surviving bulk CIK is not a
security-identity adjudication.

All 404 bulk-side CIK rows are absent from the approved current price universe
and share metadata, whereas 380 pair-side rows have share metadata. For 6201/4515,
the existing universe maps 6201 to AAL and does not contain 4515. A blind CIK remap
would lose joins; no such remap or new price/share valuation was performed.

Official source scope is recorded in the audit:

- [SEC PDS specification, section 2.1](https://www.sec.gov/files/info/edgar/pdsdissemspec051310.pdf)
  labels Acceptance Time as EST (indexed official PDF text).
- [SEC 2023 rule](https://www.sec.gov/files/rules/final/2023/33-11159.pdf)
  describes EST/EDT as currently effective (indexed official text).
- [SEC EDGAR access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
  describes the ET operating clock (direct retrieval).

Own header/index wall fields were retrieved directly. These sources do not
guarantee that every JSON value ending in Z is correctly normalized. The PDFs
were not directly parsed with a new tool/dependency; historical source coverage
remains incomplete.

**Action:** withdraw the universal-UTC claim, keep the parser's syntactic behavior
unchanged, retain both raw sources and header evidence, and stop Batch C before
Parts 2-3. No new numbered ingestion/calibration deviation or conservative
critical-value gate is applied prematurely; those require a safely adjudicated
scope and the ordered next step. In particular, do not advance all pair times,
subtract an offset from every bulk row, pick latest metadata as truth, or infer
global safety from the previously tested five filers. The holdout remains sealed.

Validation: **18 focused tests and 213 full-suite tests passed**, including the
post-`8642597` helper code; selected Ruff checks passed. Two pre-existing synthetic
rank-deficiency warnings remain. These tests validate audit arithmetic and code
contracts, not the correctness of all live timestamps. No referee rerun was needed:
research inputs were unchanged, and the prior referee does not certify P0.

## F10: synthetic finite-sample size distortion of the registered tests

**SYNTHETIC / METHODOLOGICAL, not project inference or a tradable finding.**
The [Batch A verification](../results/synthetic_inference_calibration.json)
completed 2,000 attempts: 1,994 finite and six nonfinite panel statistics, without
redraw. It tested the project's NW-six-lag monthly alpha (T=18/28) and H4-style
firm/year clustered panel (40 firms, seven years) under fixed invented DGPs.

At the registered |t|>=3.2 bar, monthly null rejection ranged **4-16%** across
the eight small simulation cells; panel finite-statistic rates were about
**2.04-3.03%**, versus a normal-reference nominal **0.1374%**. These estimates
have substantial Monte Carlo error (150/200 attempts per null cell), and the six
nonfinite statistics are not successes or silently counted as non-rejections.
This is evidence that these reference bars can substantially overreject in
these toy geometries, not proof of a particular real strategy's false-positive
rate or universal failure of asymptotic methods.

[D12](DEVIATIONS.md#d12-require-established-robust-significance-checks-for-future-acceptance)
therefore adds established robust tests prospectively, instead of the retired
ad-hoc c* plan. Their own finite-sample behavior is to be checked under the
[frozen Batch E contract](DATA_AUDIT.md#batch-e-established-tests-and-frozen-verification-contract).
At that pre-execution freeze, no new size/power rates were claimed. The
[single Batch E run](../results/robust_inference_calibration.json) is now complete
from clean source `1499865544a1a46004dfa391002409efb0869370`, seed `2026111401`.
It consumed 34,540 data attempts plus 215,460 bootstrap draws, exactly 250,000
charges; 156.78125 CPU seconds, 158.922 wall seconds, 687.78125 MiB OS peak RSS.
The classical OLS/exact-t harness passed. No retry, new cutoff or method tuning.

**Completion is not statistical adoption.** Under the frozen rule (upper 95%
CP endpoint of 5% null rejection <=7.5% across every fixed DGP), every monthly
procedure is **unreliable at T=17/18/28**. Only panel IM passes that particular
synthetic 5% criterion; it is not proof of real H4 validity.

| Geometry | Registered-test worst 95% upper | Robust worst 95% upper | Verdict |
|---|---:|---:|---|
| Monthly T17 |39.06%|EWC 13.40%; NW-fixed-b 19.08%|All fail |
| Monthly T18 |38.00%|EWC 12.51%; NW-fixed-b 19.55%|All fail |
| Monthly T28 |24.91%|EWC 9.65%; NW-fixed-b 13.09%|All fail |
| Panel G7 |17.59%|IM 6.72%; WCR 8.73%|IM qualifies at 5% only |

Examples with observed counts versus nominal expectations:

- IID monthly T17: registered NW6 rejects 610/2,000=30.5% at nominal 5%;
  EWC 161/2,000=8.05%; NW-fixed-b 280/2,000=14.0%.
- AR(.3), T17: EWC 238/2,000=11.9%, upper 95% endpoint 13.40%, well beyond the
  7.5% adoption tolerance. T28 EWC 167/2,000=8.35%, upper 9.65%; longer here is
  still insufficient.
- No-year-shock panel: IM 9/250=3.6%, upper 6.72%; WCR 13/250=5.2%, upper 8.73%.
  WCR's failure of the conservative rule is **not proof** that its population
  rejection exceeds 7.5%; the finite precision is insufficient to qualify it.
- The registered two-way panel statistic is nonfinite in 7/250 attempts in
  **each** null DGP (14 total). Finite-only 5% rates are 22/243 and 25/243.
  Those missing statistics were retained, not redrawn or called non-rejections;
  the adoption bound conservatively treats them as possible rejections.

All monthly estimates and IM/WCR panel estimates were finite in this experiment.
At 1% EWC monthly null rates range 1.25-2.7%; at 0.27% they range 0.1-0.95%,
with the reported wide Monte Carlo intervals. KV Table I lacks the necessary
99.5th/rarer percentiles, so NW-fixed-b 1%/0.27% rates are **unavailable**, not zero.

Power is **raw rejection power, not size-adjusted or qualified project power**.
For example, at T28/EWC the positive 0.25 SD effect rejects 90/500=18.0%
(95% CI 14.73-21.65%) at 5%; the 1.0 SD effect rejects 450/500=90.0%
(87.03-92.49%). At 0.27%, that 1.0 SD effect rejects 112/500=22.4%
(18.82-26.31%). Because EWC fails the null-size rule, these rates are not
power guarantees for a reliable test. Panel power has only 10 attempts/effect;
its apparent high rates are too imprecise for economic conclusions.

Neither citing a paper nor passing implementation tests proves project assumptions.
No robust procedure, DSR/PBO or calibration outcome was applied to development data.
Monthly acceptance remains undetermined under unreliable geometry/low-nu rare-level
holds; panel IM's label cannot clear P0, F2/F4, source, measurement or owner gates.
The holdout remains sealed.
