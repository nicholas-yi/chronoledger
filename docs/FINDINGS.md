# Findings

Findings are recorded as they occur, including ones that weaken this project's own design.

**Latest Batch B status:** development reruns completed once, but exact numerical
reconciliation and claims-roster identity gates were **BLOCKED**; see F7/F8 below.
No retry, tolerance relaxation, identity remapping or DSR calculation was used to
make them pass. Earlier successful engineering checks remain evidence for their
own revisions, not resolution of these new discrepancies.
**Update 2026-11-21:** F8 is explained by the numerical-thread setting for both H0
and H4, and each reproduces exactly under its setting
([F8 update](#f8-update-explained-by-the-numerical-thread-setting-2026-11-20), D14/D15).
All 16,921 required accessions now have qualified acceptance times, and all 404 F7
disagreements resolve to the listed security
([F9 update 2](#f9-update-2-every-required-accession-qualified-five-stored-early-2026-11-21)).
One new problem surfaced: five filings from one company have stored times 4-5 hours
**early**, which was real look-ahead in the H0 inputs. D16 corrected the inputs and reran H0 with no change in conclusions ([D16 rerun](#d16-rerun-on-corrected-filing-times-2026-11-21)).
The H4 stages stay held.

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
neutralized event panels remained unevaluated until D17 (exploratory, wrong sign; see the 2026-11-21 section). `H1n` is a historical ledger label for neutralized
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
remain conditional on that proxy. Neutralized event panels remained unevaluated pending a time-safe specification, which D17 later supplied (exploratory);
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

**Update 2026-11-20:** A3 read the headers of all 256 audited CIK-disagreement
accessions, and every one lists both CIKs (co-registrant evidence). The 148 other
disagreements were outside the audit roster. See the
[F9 update](#f9-update-header-clock-basis-established-2708-accessions-qualified-2026-11-20).
Security-identity adjudication remains open.
**Update 2026-11-21:** A4 read the other 148 headers. Under the declared rule,
all 404 disagreements list both CIKs, and in every case only the pair CIK (the one
H0 joins to prices) is a listed security. H0's identity join is therefore right
for these filings; bulk's accession-level dedup kept the unlisted co-registrant.
See the [F9 update 2](#f9-update-2-every-required-accession-qualified-five-stored-early-2026-11-21).

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

### F8 update: explained by the numerical-thread setting (2026-11-20)

**Status: H0 and H4 both explained and exactly reproducible.** The approved
H0-only [reproducibility diagnostic](../results/f8_h0_reproducibility.json),
frozen at `76bbdc6` with its decision rule written before execution, ran the
unchanged registered H0 configurations in fresh child processes. It did not
overwrite the recorded results file:

| Comparison (`results` and `coverage`, exact float equality) | Differences |
|---|---:|
| Single-thread run A vs single-thread run B | 0 |
| Single-thread run A vs committed Batch B file | 0 |
| Library-default threads vs the original multi-thread baseline `15b8a2d` | 0 |
| Library-default threads vs single-thread | 16 (the same 16 F8 fields) |

Both recorded values are therefore deterministic on this host: one numerical
thread reproduces Batch B bit for bit, and the OpenBLAS default (0.3.34, 16
logical CPUs) reproduces the original baseline bit for bit. The mechanism was
measured directly on the neutralized formation residuals, without reading returns.
39,984 of 54,684 residuals differ in the last bits between the two settings, at
most 1.7e-17. Only two near-tied pairs swap rank, four rows in total
(10-K formation 2023-02 and latest formation 2023-05). Those swaps are the only
change to rank IC, so mean IC moves by 9.1e-8 and 1.1e-6. Net/gross returns,
alphas and the monthly series are untouched.

No tolerance was substituted and no tie-breaking rule was adopted after the fact.
[D14](DEVIATIONS.md#d14-hold-the-numerical-thread-setting-fixed-in-exact-reproduction)
fixes the thread setting as part of future exact comparisons. The 36 appended
ledger rows repeat existing config hashes, so `n_trials` is unchanged.
This is numerical provenance, not scientific acceptance of any H0 estimate.

**H4, same day.** H4's file-reading stages are held because they load outcome
files that span the H4 holdout years. Under
[D15](DEVIATIONS.md#d15-one-development-only-h4-extract-for-the-f8-numerical-check),
one process read those files once, decoding 3,303 holdout-window outcome rows in
memory and writing none, and produced a development-only extract. The extract's
5,270-row panel equals the full-file panel exactly
([extract receipt](../results/h4_dev_extract.json)). The registered regressions
then ran on it in three fresh processes
([H4 check](../results/f8_h4_reproducibility.json)):

| Comparison (exact float equality) | Differences |
|---|---:|
| Single-thread run A vs single-thread run B | 0 |
| Single-thread run A vs committed Batch B file | 0 |
| Library-default threads vs the original baseline `15b8a2d` | 0 |
| Library-default threads vs single-thread | 12 (the same 12 F8 fields, at most 6.5e-13) |

So the H4 differences are also the thread setting, and D14 applies. The 18
appended ledger rows repeat existing config hashes. Every H4 stage stays hard
held, and nothing was run on validation or holdout data.

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

### F9 update: header clock basis established; 2,708 accessions qualified (2026-11-20)

**Status: partly resolved.** The missing piece was evidence of which clock the
filing header uses. A3 tested that against the SEC's own filing-date rule, then
qualified every accession it could read. The other 14,213 remain unresolved
because they were never read, not because they failed.

**Clock basis (CB1).** Regulation S-T Rule 13(a)(2)
([17 CFR 232.13](https://www.ecfr.gov/current/title-17/section-232.13)) deems a
filing submitted after 5:30 p.m. "Eastern Standard Time or Eastern Daylight Saving
Time, whichever is currently in effect" filed on the next business day. If the header
`ACCEPTANCE-DATETIME` is that Eastern civil clock, its `FILING-DATE` must roll at 17:30
in both seasons. A fixed-EST clock (the PDS field label) would roll at 16:30 in
summer; a UTC clock would roll around 21:30. The test and its thresholds were frozen
at `47a6c51` before any A3 request or filing-date analysis
([CB1 receipt](../results/timestamp_a3_clock_basis_cb1.json)):

| Statistic | Previously fetched headers (CB1) | New A3 headers (CB1-R) |
|---|---:|---:|
| Daylight weekday, accepted 16:30–17:30, same-day filing date | 240/240 | 262/262 |
| Weekday accepted 17:35–21:30, filing date rolled forward | 196/197 | 111/112 |
| Weekday accepted at or before 17:30 but rolled forward | 0/1,355 | 0/1,277 |
| Decision | Pass | Pass (replicated) |

This rejects the fixed-EST and UTC readings of the header. It assumes EDGAR's own
clock was synchronized; it does not verify each second against an external clock,
and it says nothing about JSON `Z` fields.

**Qualification.** An accession qualifies when the clock basis passed and every
archive-path header and index was read. The header and index walls must agree,
convert uniquely through daylight-saving changes, lie inside the frozen candidate
envelope, and carry a filing date consistent with the 17:30 cutoff. The
[A3 report](../results/timestamp_full_a3_report.json) qualifies **2,708 of
16,921** required accessions: all 108 designated clock disagreements, all 256 CIK
disagreements, and 2,344 accessions from the seeded random remainder. No read
accession failed the rule. All 2,708 first closes are assigned on the nominal
16:00 ET calendar; none falls in the early-close window.

**Look-ahead direction.** The declared
[impact analysis](../results/timestamp_a3_impact.json) compares each stored time with
its qualified time. It uses the nominal calendar and a conservative one that moves
every possible early-close date to 13:00 ET:

| Stored time | Equal to qualified | Same first close | Later close (delay only) | Earlier close (look-ahead) |
|---|---:|---:|---:|---:|
| Pair (H0 knowledge time) | 2,698 | 2,704 | 4 | **0** |
| Bulk | 2,546 | 2,674 | 34 | **0** |

The results are identical under both calendars. All 108 designated disagreements
match the pair time; bulk is four or five hours late. Ten random-remainder
accessions match neither stored time: both stored sources are four (seven cases)
or five (three cases) hours **late**, like the earlier `0000003545-24-000034`
example. A late time can only delay a trade.

Among the 2,344 randomly ordered qualified accessions, 0 show pair-time look-ahead.
A one-sided 95% Clopper-Pearson upper bound computed **after** seeing that count is
0.13% for this population. The stop came from gateway errors, which are unrelated to
filing times, but this is still not a certificate for the 14,213 unread accessions.

**Identity (F7).** All 256 audited CIK-disagreement accessions list **both** CIKs in
the filing header, which is co-registrant evidence. The other 148 universe
disagreements were outside the frozen audit roster and were never fetched. Header
roles still do not adjudicate which company's security a signal belongs to.

**Acquisition.** 2,800 A3 requests: 2,793 HTTP 200, four 502 and three 504 gateway
errors, and no 503 throttling. The first 502 stopped the run under the frozen
policy. The owner then approved amendment 1, which handles 502/504 like 503 under the
same six-pause cap. The sixth gateway pause stopped the audit permanently at
6,054 of 34,402 requests. Dispatch gaps met 0.667 seconds throughout, and 1.0
seconds after the amendment.

No timestamp, table, signal, price, return or ledger row was changed, and the
holdout remains sealed. The referee's `time_authority` check read this report
and still failed, correctly, because 14,213 accessions were unresolved.

### F9 update 2: every required accession qualified; five stored early (2026-11-21)

**Status: clock authority established for all 16,921 accessions; H0 inputs need a
correction for one company.** You approved continuing (A4) with a gentler gateway
rule, a ceiling of 35,000 and the F7 fetches. The
[A4 config](../results/timestamp_full_a4_config.json) was frozen before any request:

- First 502/504 on a URL: wait 60 seconds and retry, not counted.
- A repeat failure, or any 503/429: a counted 10-minute pause, capped at 12.
- Stop if more than 15 of the last 500 requests are gateway errors.

The single segment finished the whole order: 28,616 requests, of which 28,550 were
HTTP 200, 45 were 504 and 21 were 502. It used 57 short retries and 9 of 12 counted
pauses, and every resource in the inventory now has an outcome. Usage is 34,670 of
35,000 requests.

The [original A4 report](../results/timestamp_full_a4_report.json) qualified 16,909
accessions. Its 12 "unresolved" were a bug in the report's raw reader: their headers
were pinned-cache hits that the run had read and parsed correctly, but the report
looked for them in the empty A4 attempt list. A disclosed
[correction](../results/timestamp_full_a4_correction1.json), made after seeing that
report and changing no rule, produced
[revision 2](../results/timestamp_full_a4_report_r2.json):

| Result (revision 2) | Value |
|---|---:|
| Required accessions qualified | **16,921 of 16,921** |
| CB1 replication on 14,213 new headers: 16:30-17:30 daylight same-day / 17:35-21:30 rolled / early rolls | 2,729/2,729; 1,043/1,058; 0/13,057 |
| F7 disagreements resolved to the listed pair CIK | 404 of 404 |
| Pair time equals the qualified time | 16,818 |
| Pair time reaches a later first close (delay only) | 51 |
| Pair time reaches an **earlier** first close (look-ahead) | **5** |

One accession (`0001437749-22-029683`) was accepted in the afternoon of a possible
early-close date, so its first close is qualified only on the nominal calendar. One
other has a filing date adjusted earlier, which the rule allows.

**The five look-ahead cases** are all MHLA (CIK 1412100) filings from 2023-2024:
`0001412100-23-000056`, `-23-000086`, `-23-000097`, `-24-000014` and `-24-000047`.
Both SEC JSON sources store the Eastern wall-clock time with a UTC label. For example,
a 10-Q accepted at 17:07 ET on 2023-05-09 is stored as 17:07 UTC (13:07 ET). That is
before that day's 16:00 close, so H0 treats the filing as tradable one close before
it was public. Metadata diagnostics on the pair times show 56 first closes and one
formation-eligibility record-month change, with no latest-filing choice changed.
The effect on H0 returns has **not** been measured. Correcting it means replacing
stored knowledge times with qualified ones and rerunning the development results,
which is a numbered deviation. The owner approved it the same day; see the
[D16 rerun](#d16-rerun-on-corrected-filing-times-2026-11-21).

This assumes EDGAR's own clock was synchronized and Rule 13(a)(2)'s Eastern basis.
It does not verify any timestamp against an external clock. No timestamp, table,
signal, price, return or ledger row was changed, and the holdout remains sealed.

### D16 rerun on corrected filing times (2026-11-21)

**Status: H0 inputs corrected and rerun; conclusions unchanged; development only.**
Under [D16](DEVIATIONS.md#d16-replace-h0-knowledge-times-with-qualified-acceptance-times),
logged before anything ran, every H0 signal with a qualified time took that time, in a
new input file ([build receipt](../results/d16_h0_time_correction.json)). The other
4,581 rows kept their stored time, and the script confirmed that every one is
assignment-insensitive. 103 of 21,502 times changed: the 5 look-ahead MHLA filings,
51 late ones, and 47 that move without changing the first close. The one acceptance
on a possible early-close afternoon (2022-12-23, 15:19 ET) is on a full trading day
according to NYSE Group's published calendar, so its 16:00 close stands.

The unchanged H0 runner then ran once with one thread (D14)
([results](../results/returns_h0_development_d16.json),
[comparison](../results/d16_h0_rerun_comparison.json)):

| Variant | Net mean / month, Batch B → D16 | Alpha t, Batch B → D16 |
|---|---:|---:|
| `v1_10K_raw` | -0.80485% → -0.80497% | -0.4543 → -0.4546 |
| `v2_latest_raw` | +0.29079% → +0.29079% | +1.4575 → +1.4575 |
| `v2_latest_neutral` | -0.29411% → -0.29411% | -2.3307 → -2.3307 |
| `v2_10K_neutral` | -1.68946% → -1.68947% | -2.3592 → -2.3592 |

78 fields changed, all slightly. The largest movement is in the raw `v1_10K_raw`
event panel (descriptive only), where t goes from 1.84 to 2.03 with the coefficient
almost unchanged (1.7446 → 1.7451). Its sign is the **opposite** of the Lazy Prices
prediction, it uses 17 month clusters, and it is not a registered test, so it supports
nothing. The 12 ledger rows repeat existing configuration hashes.

F8 had blocked two development diagnostics; D14 explained F8, so they now run on the
corrected series ([diagnostics](../results/current_vintage_diagnostics_d16.json)).
Using the registered trial count (10 per family) and 17 aligned months, the
conditional deflated Sharpe probabilities are 0.035 (`v1_10K_raw`) and 0.195
(`v2_latest_raw`) for H0, and 0.024 and 0.001 for the neutralized variants. The
frozen D4 predicate marks both raw H0 variants **not_supported**. PBO is not estimable
below 32 months. Because F10 makes the registered monthly t-test unreliable at this
length, these are descriptive.

The full [referee](../results/REFEREE.md) now passes `time_authority` at level 4,
including a new check that every H0 knowledge time in use equals its qualified time.
The gate stays **BLOCKED** only by `inference.calibration`, the permanent limit in F10.
No holdout data was read, and the H4/H6 stages stay held.

### H4/H6 timing, the event-time H0 panel, the prospective holdout and social sentiment (2026-11-21)

**2012-2018 H4/H6a timing (A5).** Offline, only 262 of the H4 sample's 2012-2018
filings could change a registered H4/H6a assignment if their time were 5 hours off:

- 252 sit within hours of a restatement event or the 365-day window edge.
- 10 are same-company 10-Ks filed within 10 hours of each other.
- No H4 development pair is near the window or year edges.

The approved [A5 audit](../results/timestamp_a5_report.json) read all 524 header and
index pages (529 requests; usage 35,199 of 35,800). Two things came out of it:

- 110 older filings have no header page (HTTP 404), so only their index time exists.
- On the 152 headers that exist, the Eastern-clock pattern replicates: 39/39 same-day
  filings just before 17:30, 22/22 rolled after 17:35, and 0/124 early rolls. The
  frozen integrity sub-check still failed. Two filings were accepted 12 and 44 seconds
  after 22:00 ET with correctly rolled dates, and at this sample size the 0.1%
  tolerance allows none. Under the frozen rule, **0 of 262 qualify**. The rule was not
  changed.

A labelled [post-hoc sensitivity](../results/timestamp_a5_posthoc_sensitivity.json)
reads those times as Eastern anyway:

- 132 of the 262 stored bulk times are 4-5 hours early, 10 are 4 hours late and 120 are exact.
- **No H6a development indicator, window or year changes, and no H4 10-K order changes**
  (109 firms checked). H4 and H6a compare filings with each other and use dates
  rather than trading closes, so a shared clock offset cancels.
- The early times would matter for any future return test that uses these older bulk
  times; they do not matter for H4/H6a as registered.

**D17, the event-time neutralized H0 panel (exploratory).** Registered and tagged before
it ran, after earlier development results ([D17](DEVIATIONS.md#d17-define-the-event-time-neutralized-signal-for-the-h0-event-co-primary)).
Results are from the [D17 run](../results/h0_event_neutral_development.json):

| Variant | Coefficient (expected < 0) | Month-clustered t | Wild bootstrap p | Events |
|---|---:|---:|---:|---:|
| Latest filing | +0.113 | 0.46 | 0.67 | 12,575 |
| 10-K only | +1.366 | 2.60 | 0.13 | 4,181 |

Neither supports the hypothesis. Both point the **wrong way**. The 10-K variant's
clustered t of 2.60 shrinks to a bootstrap p of 0.13, which is the over-rejection F10
predicts with 16 clusters. Two new H1n configurations were logged, so H1n now counts 12.

**D18, a prospective H4/H6a holdout.** The exposed 2022-2025 windows are retired as
confirmatory evidence. Confirmatory H4/H6a evaluation will use filings accepted from
2026-11-22 to 2027-11-21, evaluated once: H6a not before 2028-12-31 and H4 not before
2029-03-31. [periods.py](../src/asof/periods.py) enforces those dates
([D18](DEVIATIONS.md#d18-move-h4-and-h6a-confirmatory-evaluation-to-a-prospective-holdout)).
H6b stays invalid: fixing survivorship needs delisting-inclusive prices, and the owner
declined paid data on 2026-11-21.

**Social sentiment (H7 scaffolding).** A
[point-in-time pipeline](../src/asof/social.py) is built and tested, but no X data has
been fetched; see the [H7 design note](H7_SOCIAL_SENTIMENT.md). The candidate scorer
failed its qualification on human-labelled finance text
([receipt](../results/sentiment_scorer_validation.json)). On Financial PhraseBank, VADER
scores 57.1% accuracy (macro-F1 0.49), below the 61.4% that always predicting
"neutral" would get. A finance-qualified scorer is required before any paid data.

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

### F10 status: a permanent limit of this design (2026-11-20)

The failing `inference.calibration` referee check is **not a pending task** that
more engineering can close. It fails because the registered monthly design has only T=17/18 development
months, and the sealed holdout has about 28. Every monthly procedure tested,
including the established robust alternatives, fails the frozen 5% size rule at
all three lengths. More simulation cannot add months, and opening the holdout
for that purpose is not authorized. Switching to a method chosen after these
results would be a post-result protocol change.

So the check stays failing on purpose, and the referee keeps reporting it. Any
monthly t-statistic in this project should be read as descriptive. Closing the
gap needs a new study design with more independent months, such as the
[older-period study](RESEARCH_PLAN.md#closing-the-known-gaps), registered before
its data are examined. This is a scope statement, not a new simulation or test.
