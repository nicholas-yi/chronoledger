# Findings

The current-state research log, including findings that weaken this project's own design.
Superseded intermediate states are compressed; the full chronological log is at the
[`archive-2026-11` tag](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md).

## Status summary

- **No hypothesis is supported and no tradable edge is claimed.** Every estimate below is a
  development diagnostic; a development estimate is not a finding, and a positive one is not
  a tradable edge.
- **H0:** no variant supports the registered direction; the D16 rerun on corrected filing
  times changed no conclusion, and the D17 event-time panel points the wrong way.
- **H4:** every absolute t is below 1.23, against the 3.0 bar. **H5b, H5c and H6(b)** are
  **invalid** under F2; H6(a) (t = 1.7377173) is below the 3.0 bar. **H7** was closed
  unregistered on 2026-11-21, so there is no H7 result.
- **Holdout.** Data after 2024-07-31 form the sealed H0 holdout, which has not been opened.
  The exposed 2022-2025 H4/H6a windows are retired; confirmatory H4/H6a evaluation moves to
  a prospective holdout (D18).
- **Referee gate.** The full [referee](../results/REFEREE.md) passes `time_authority` and is
  **BLOCKED** only by `inference.calibration`, the permanent limit in F10. Passing checks are
  software evidence, not scientific acceptance. The append-only
  [trial ledger](../results/trial_ledger.jsonl) keeps every run, including invalid ones.

Standing qualifiers, stated once: industry neutralization uses a current-SIC proxy, not
historical industry data; event inputs use a fixed-16:00 session clock and valid-observation
CAR indexing; H4's original holdout was contaminated (F4, D18); and with 17/18 development
months every monthly t-statistic is descriptive (F10). No paid data or market-data key was used.

| # | Finding | Status | Consequence |
|---|---|---|---|
| [F1](#f1-context-specific-covid-knowledge-in-pre-2020-chronobert-vintages) | Pre-2020 ChronoBERT vintages know "COVID" in context | Open | H1 results must also hold under TF-IDF (D3); in-use vintages show no leak, but the probe detects only large leaks |
| [F2](#f2-distress-event-tests-are-invalid-under-a-current-ticker-universe) | A current-ticker universe selects distressed survivors | Invalidating | H5b, H5c and H6(b) are invalid; no fix without delisting-inclusive prices, which the owner declined |
| [F3](#f3-three-data-bugs-caught-by-an-implausible-backtest) | Share-count typos, vendor look-ahead, impossible returns | Resolved | Point-in-time cleaning (D7) and a `data_integrity` referee threat; invalid runs stay in the ledger |
| [F4](#f4-h4-winsorization-used-observations-outside-development) | H4 winsorization saw post-development data | Resolved | Cutoffs fit on development only (D6); H4's original holdout is not untouched |
| [F5](#f5-formation-selected-on-future-outcomes-monthly-residuals-were-not-event-time-signals) | Formation used future outcomes; residuals not event-time | Resolved | Formation-time rules (D8); event-time neutralized signal defined later (D17) |
| [F6](#f6-the-f3-price-return-guard-did-not-cover-daily-event-inputs) | Price guard missed daily event inputs | Resolved | Same guard on daily loaders (D9) |
| [F7](#f7-h0-pair-metadata-disagrees-with-the-bulk-filing-identityacceptance-metadata) | H0 pair and bulk metadata disagree on CIK/time | Resolved | All 404 CIK disagreements resolve to the listed pair CIK that H0 uses; times go to F9 |
| [F8](#f8-single-thread-batch-b-does-not-reproduce-every-recorded-summary-bit-for-bit) | Batch B not bit-for-bit | Resolved | Explained by the numerical-thread setting, now held fixed (D14) |
| [F9](#f9-p0-acceptance-time-authority-is-not-uniformly-certified-by-json-z-fields) | JSON `Z` times are not authoritative | Resolved for H0; 2012-2018 times unqualified | Five early MHLA filings corrected (D16), conclusions unchanged; older times change no H4/H6a assignment post hoc |
| [F10](#f10-synthetic-finite-sample-size-distortion-of-the-registered-tests) | Registered tests over-reject in small samples | Permanent limit | Monthly t-statistics are descriptive; the referee gate stays blocked |

## F1: context-specific "COVID" knowledge in pre-2020 ChronoBERT vintages

**Status: open.** A reproducible probe result. The cause is unconfirmed, and nothing has been
reported to the model authors.

[`scripts/leakprobe.py`](../scripts/leakprobe.py) masks every subtoken of a term whose first
public use is known and compares a context that evokes the term with a control context of the
same surface pattern but unrelated meaning. A vintage trained before the term existed should
not rank it highly in the evoking context.

| Term (first public use) | Vintage | Evoking rank | Control rank |
|---|---|---|---|
| COVID (2020-02-11) | 2018-12-31 / 2019-12-31 | **1** / **1** | 1,163 / 1,400 |
| coronavirus (2020-01-09) | 2018-12-31 / 2019-12-31 | 342 / 302 | 2,665 / 1,444 |
| Qnity | 2022 / 2023 / 2024 (all pre, all in use) | 311 / 611 / 368 | 2,768 / 3,407 / 3,379 |

- The 2018 and 2019 vintages complete "Lockdowns in 2020 were imposed to slow the spread of
  ___-19" with "COVID" at about 94–98% probability, while an unrelated "part number ___-19"
  context ranks it below 1,000th: context-specific knowledge, not a token prior. The same
  vintages do not know "coronavirus", and Brexit is clean, so any leakage is narrow.
- **The in-use vintages (2022-2024) show no context-specific leakage**, but post-coinage
  positive controls also fail (the 2022 vintage doesn't know Kenvue, the 2023 vintage doesn't
  know Solventum), so the probe detects only large leaks. Mounjaro is a subword-prior false
  positive under the rank-only rule; Omicron and ChatGPT are inconclusive.
- Unconfirmed hypothesis: some pre-2020 training documents carry original timestamps but
  contain later revisions, which would spread "COVID-19" while leaving "coronavirus" rare.

[D4](DEVIATIONS.md#d4-referee-scope-and-leak-criterion-for-the-neologism-probe) scopes gating
to the in-use vintages (the all-vintage failure stays visible, non-gating);
[D3](DEVIATIONS.md#d3-leak-proof-robustness-representation-for-h1) requires every H1 result to
also hold under bag-of-words TF-IDF. Next: a broader dated neologism set, and contacting the
ChronoBERT authors before any public claim. Full tables:
[F1](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md#f1-context-specific-covid-knowledge-in-pre-2020-chronobert-vintages),
[F1 update](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md#f1-update-probing-the-vintages-this-project-uses).

## F2: distress-event tests are invalid under a current-ticker universe

**Status: invalidating.** Confirmed by diagnostic; it invalidates the H5b, H5c and H6(b)
development results.

Every H5 development result had the opposite sign to well-established published effects:
late-filing notices showed a mean CAR(+1..+60) of +6.8% (t = 1.5), Item 4.02 +5.9% and Item
4.01 +4.4%. A random-date placebo in the same universe gives CAR(+1..+20) −0.3% (t = −2.1)
and CAR(+1..+60) −0.6% (t = −1.3), so there is no general positive bias. Coverage by event
type, using all SEC filers in the bulk archive, Jan 2023–Jun 2024:

| Filers | Firms | In price-covered universe | Stopped filing 10-Ks before mid-2025 |
|---|---|---|---|
| All 10-K filers | 7,378 | 36.6% | 26.2% |
| NT 10-K/10-Q | 1,822 | 11.0% | 49.3% |
| 8-K Item 4.02 | 329 | 27.1% | 34.3% |
| 8-K Item 4.01 | 1,115 | 20.6% | 30.7% |

The universe uses today's tickers and a public float of at least $200M, so distressed filers
are 1.3–3.3x less likely to be included, and the excluded ones disproportionately later
disappeared; among distressed firms, conditioning on survival selects the rebounders, so the
sign flips. Referee coverage contrasts versus all 10-K filers (NT 0.30, Item 4.02 0.74, Item
4.01 0.56) are below the 0.8 diagnostic floor.

**Consequences.** H5b, H5c and H6(b) cannot be tested with free current-ticker prices. Their
development results are invalid, not evidence against the published effects, and their
holdouts will not be opened under this data. A fix needs delisted-security prices (or deal
consideration for acquired firms); the owner declined paid data on 2026-11-21.

## F3: three data bugs caught by an implausible backtest

**Status: resolved.** The first H0 development run showed long-short means of +20% to +27%
per month, with alpha t-statistics up to 4.6, and was treated as a bug until proven otherwise:

1. **XBRL share-count typos** (PKG filed 89.8 billion shares in one 10-Q, against about 89.8
   million around it). A jump of more than 10x now applies only after a strictly later filing
   confirms it, and same-instant conflicts take the latest reported share date
   ([D7](DEVIATIONS.md#d7-deterministic-point-in-time-share-ties-and-genuinely-later-confirmation)).
2. **Vendor look-ahead:** Yahoo's prices embed later split adjustments; see [DATA_AUDIT](DATA_AUDIT.md).
3. **Impossible returns** below −100% are dropped as data errors.

The invalid runs stay in the ledger, where they count toward the multiple-testing penalty; the
`data_integrity` referee threat fails any long-short mean above 5% per month.

## F4: H4 winsorization used observations outside development

**Status: resolved.** `build_panel()` winsorized ratio variables before selecting the
development period, so future observations changed development cutoffs (reproduced with
synthetic data on 2026-11-13). Cutoffs are now fit on development observations only
([D6](DEVIATIONS.md#d6-fit-h4-winsorization-on-development-observations-only)). Prior H4 ledger
entries are not clean evidence, and H4's original holdout is not untouched (see D18).

## F5: formation selected on future outcomes; monthly residuals were not event-time signals

**Status: resolved.** Removing one next-month return changed a 50-firm formation into 49 firms,
and filing-month cohort residuals used the month's latest filing time, so they were not
observable at each filing's acceptance time. Formation now ignores future return availability,
counts missing returns explicitly and neutralizes with formation-time controls
([D8](DEVIATIONS.md#d8-formation-time-eligibility-neutralization-and-missing-return-accounting));
[D17](#d17-event-time-neutralized-h0-panel-exploratory) later defined a time-safe event-time
signal. These repairs establish no effect and do not repair survivorship.

## F6: the F3 price-return guard did not cover daily event inputs

**Status: resolved.** An exhaustive audit of 2,733 usable daily histories found two returns
below -100% and one non-finite return, plus 503 nonpositive vendor-adjusted observations during
2021-2022 (vendor-level cause not established). Daily loaders now use the same price-ratio
guard, log exclusions and preserve missingness instead of forward-filling
([D9](DEVIATIONS.md#d9-apply-the-existing-price-return-integrity-guard-to-event-inputs)). This
does not validate vendor total returns.

## F7: H0 pair metadata disagrees with the bulk filing identity/acceptance metadata

**Status: resolved for identity; acceptance times are covered in F9.** In the Batch B
claims-roster preflight, accessions and forms matched across 16,226 permitted-development
candidate pairs, but 305 CIK fields and 124 acceptance timestamps differed between the H0 pair
input and current bulk metadata (counts can overlap); all H0 signal rows have 404 CIK
disagreements. The A3 and A4 header audits read all 404 (256, then 148): every one lists both
CIKs, and only the pair CIK, the one H0 joins to prices, is a listed security.
**H0's identity join is right for these filings**; bulk's accession-level dedup kept the
unlisted co-registrant. No CIK or time was remapped
([F9 update 2](#f9-update-2-every-required-accession-qualified-five-stored-early-2026-11-21)).
The 60-case claims selection stopped before sampling at this blocker; its
[roster status](../results/claims_audit_roster.json) records zero cases
([blocker artifact](../results/batch_b_claims_roster_blocker.json)).

## F8: single-thread Batch B does not reproduce every recorded summary bit-for-bit

**Status: resolved.** The single-thread Batch B rerun failed its exact-comparison gates: 12 H4
coefficient/t fields differed (maximum absolute difference **6.466e-13**;
[H4 impact](../results/batch_b_h4_impact.json)), and 16 stored H0 neutralized mean-IC/IC-t
fields differed ([comparison](../results/batch_b_rerun_comparison.json)). No tolerance was
substituted ([archived detail](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md#f8-single-thread-batch-b-does-not-reproduce-every-recorded-summary-bit-for-bit)).

### F8 update: explained by the numerical-thread setting (2026-11-20)

Fresh processes reran the unchanged registered configurations under a decision rule written
before execution ([H0 check](../results/f8_h0_reproducibility.json),
[H4 check](../results/f8_h4_reproducibility.json)). Exact float comparisons showed 0
differences between two single-thread runs, and between single-thread and the committed Batch
B file; library-default threads showed 0 differences from the original baseline `15b8a2d` and
differed from single-thread in exactly the 16 H0 and 12 H4 fields above.

One thread reproduces Batch B and the OpenBLAS default (0.3.34, 16 logical CPUs) reproduces the
original baseline, bit for bit. For H0, 39,984 of 54,684 neutralized residuals differ in the
last bits (at most 1.7e-17); two near-tied pairs swap rank, moving mean IC by 9.1e-8 and
1.1e-6, and returns and alphas are untouched. The H4 check used a development-only extract
([D15](DEVIATIONS.md#d15-one-development-only-h4-extract-for-the-f8-numerical-check),
[receipt](../results/h4_dev_extract.json)) whose 5,270-row panel equals the full-file panel;
building it decoded 3,303 holdout-window outcome rows in memory and wrote none.
[D14](DEVIATIONS.md#d14-hold-the-numerical-thread-setting-fixed-in-exact-reproduction) fixes
the thread setting for exact comparisons; the appended ledger rows repeat existing
configuration hashes, so `n_trials` is unchanged. This is numerical provenance, not acceptance.

## F9: P0 acceptance-time authority is not uniformly certified by JSON Z fields

**Status: resolved for H0; the 2012-2018 H4/H6a times remain unqualified but change no
registered assignment.** The [first audit](../results/p0_acceptance_authority_audit.json)
found the 124 development pair/bulk disagreements were 75 offsets of +4 hours and 49 of +5
hours (bulk minus pair), matching seasonal ET/UTC offsets. Sampled pair times matched the
filing header with bulk 4/5 hours late, and one internally agreeing case
(`0000003545-24-000034`) was five hours late in both sources, so internal agreement cannot
certify a time. The universal-UTC claim was withdrawn and no global offset applied
([archived impact](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md#actual-impact-versus-conditional-column-substitution),
[co-registrants](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md#co-registrants-and-authority-limits)).

### F9 update: header clock basis established; 2,708 accessions qualified (2026-11-20)

Regulation S-T Rule 13(a)(2) ([17 CFR 232.13](https://www.ecfr.gov/current/title-17/section-232.13))
deems a filing submitted after 5:30 p.m. Eastern (standard or daylight, whichever is in effect)
filed the next business day. If the header `ACCEPTANCE-DATETIME` is that Eastern civil clock,
`FILING-DATE` must roll at 17:30 in both seasons; fixed EST would roll at 16:30 in summer and
UTC around 21:30. In the test frozen at `47a6c51` before any request
([CB1 receipt](../results/timestamp_a3_clock_basis_cb1.json)), daylight weekday filings
accepted 16:30–17:30 kept the same filing date (240/240; A3 replication 262/262), weekday
filings accepted 17:35–21:30 rolled forward (196/197; 111/112), and no weekday filing accepted
at or before 17:30 rolled forward (0/1,355; 0/1,277). This rejects the fixed-EST and UTC
readings, assuming EDGAR's own clock was synchronized; nothing is verified against an
external clock. An accession qualifies when its header and index walls agree, convert
uniquely through daylight-saving changes, lie in the frozen candidate envelope and have a
filing date consistent with the 17:30 cutoff. A3 qualified 2,708 of 16,921 required
accessions before gateway errors stopped it ([A3 report](../results/timestamp_full_a3_report.json),
[impact](../results/timestamp_a3_impact.json)); no read accession failed, and none showed
pair-time look-ahead.

### F9 update 2: every required accession qualified; five stored early (2026-11-21)

A4 finished the inventory under a [config](../results/timestamp_full_a4_config.json) frozen
before any request. A report-reader bug left 12 accessions "unresolved" in the
[original report](../results/timestamp_full_a4_report.json); a disclosed
[correction](../results/timestamp_full_a4_correction1.json) that changed no rule produced
[revision 2](../results/timestamp_full_a4_report_r2.json):

| Result (revision 2) | Value |
|---|---:|
| Required accessions qualified | **16,921 of 16,921** |
| CB1 replication on 14,213 new headers: 16:30-17:30 daylight same-day / 17:35-21:30 rolled / early rolls | 2,729/2,729; 1,043/1,058; 0/13,057 |
| F7 disagreements resolved to the listed pair CIK | 404 of 404 |
| Pair time equals the qualified time | 16,818 |
| Pair time reaches a later first close (delay only) | 51 |
| Pair time reaches an **earlier** first close (look-ahead) | **5** |

**The five look-ahead cases** are all MHLA (CIK 1412100) filings from 2023-2024:
`0001412100-23-000056`, `-23-000086`, `-23-000097`, `-24-000014` and `-24-000047`. Both SEC
JSON sources store the Eastern wall-clock time with a UTC label: a 10-Q accepted at 17:07 ET
on 2023-05-09 is stored as 17:07 UTC (13:07 ET), before that day's 16:00 close, so H0 treated
it as tradable one close early. This was real look-ahead in the H0 inputs;
[D16](#d16-rerun-on-corrected-filing-times-2026-11-21) corrected it.

### H4/H6 timing, the event-time H0 panel, the prospective holdout and social sentiment (2026-11-21)

This subsection covers the 2012-2018 H4/H6a timing audit (A5); the day's other items are
[D17](#d17-event-time-neutralized-h0-panel-exploratory), [D18](#d18-prospective-h4h6a-holdout)
and [H7](#h7-social-sentiment-closed-unregistered).

Only 262 of the H4 sample's 2012-2018 filings could change a registered H4/H6a assignment if
their time were 5 hours off. The [A5 audit](../results/timestamp_a5_report.json) read all 524
header and index pages; 110 older filings have no header page (HTTP 404). On the 152 headers
that exist, the Eastern-clock pattern replicates (39/39 same-day, 22/22 rolled, 0/124 early
rolls), but the frozen integrity sub-check failed on two filings accepted 12 and 44 seconds
after 22:00 ET, so under the unchanged rule **0 of 262 qualify**.

A labelled [post-hoc sensitivity](../results/timestamp_a5_posthoc_sensitivity.json) reads those
times as Eastern anyway: 132 of the 262 stored bulk times are 4-5 hours early, 10 are 4 hours
late and 120 are exact. **No H6a development indicator, window or year changes, and no H4
10-K order changes** (109 firms checked), because H4 and H6a compare filings with each other
using dates rather than trading closes. The early times would matter for any future return
test that uses these older bulk times.

## F10: synthetic finite-sample size distortion of the registered tests

**Status: permanent limit. Synthetic and methodological; not project inference.** In the
[Batch A verification](../results/synthetic_inference_calibration.json) (2,000 attempts) of the
registered NW-six-lag monthly alpha and an H4-style clustered panel, monthly null rejection at
the registered |t|>=3.2 bar ranged **4-16%** and panel rates were about **2.04-3.03%**,
versus a nominal **0.1374%**.

[D12](DEVIATIONS.md#d12-require-established-robust-significance-checks-for-future-acceptance)
added established robust tests prospectively under a
[frozen Batch E contract](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#batch-e-established-tests-and-frozen-verification-contract):
the upper 95% CP endpoint of 5% null rejection must be <=7.5% across every fixed DGP. The
[single Batch E run](../results/robust_inference_calibration.json) (seed `2026111401`):

| Geometry | Registered-test worst 95% upper | Robust worst 95% upper | Verdict |
|---|---:|---:|---|
| Monthly T17 | 39.06% | EWC 13.40%; NW-fixed-b 19.08% | All fail |
| Monthly T18 | 38.00% | EWC 12.51%; NW-fixed-b 19.55% | All fail |
| Monthly T28 | 24.91% | EWC 9.65%; NW-fixed-b 13.09% | All fail |
| Panel G7 | 17.59% | IM 6.72%; WCR 8.73% | IM qualifies at 5% only |

For example, with IID monthly data at T17 the registered NW6 test rejects 610/2,000=30.5% at
nominal 5% (EWC 161/2,000=8.05%; NW-fixed-b 280/2,000=14.0%). Power is raw, not size-adjusted:
at T28/EWC a 1.0 SD effect rejects 450/500=90.0% at 5% but 112/500=22.4% at 0.27%. Panel IM
passes only this synthetic 5% criterion, which is not proof of real H4 validity and clears no
other gate. No robust procedure was applied to development data. Nonfinite-statistic handling,
further examples and rare-level rates are
[archived](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md#f10-synthetic-finite-sample-size-distortion-of-the-registered-tests).

### F10 status: a permanent limit of this design (2026-11-20)

The failing `inference.calibration` referee check is **not a pending task** that more
engineering can close. The registered monthly design has only T=17/18 development months, and
the sealed holdout has about 28; every monthly procedure tested fails the frozen 5% size rule
at all three lengths. More simulation cannot add months, opening the holdout for that purpose
is not authorized, and switching method after these results would be a post-result protocol
change. Closing the gap needs a new design with more independent months, such as the
[older-period study](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/RESEARCH_PLAN.md#closing-the-known-gaps),
registered before its data are examined.

## Development results by hypothesis

All results are development-only. The 2026-11-13 reruns used
[execution revision db73f74](https://github.com/nicholas-yi/chronoledger/tree/db73f742214239f4e4b1a0515784279f492da3ec);
the ledger retains all 18 original entries and appends every later check with lineage
([archived timings and hashes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FINDINGS.md#development-rerun-reconciliation-2026-11-13)).

### H0: cosine text change and next-month returns

Net long-low-change/short-high-change portfolios, so positive is the registered direction.
Batch B is the 2026-11-13 rerun; D16 is the rerun on corrected filing times.

| Variant | Monthly observations | Net mean / month, Batch B → D16 | Alpha t, Batch B → D16 |
|---|---:|---:|---:|
| `v1_10K_raw` | 17 | -0.80485% → -0.80497% | -0.4543 → -0.4546 |
| `v2_latest_raw` | 18 | +0.29079% → +0.29079% | +1.4575 → +1.4575 |
| `v2_latest_neutral` | 18 | -0.29411% → -0.29411% | -2.3307 → -2.3307 |
| `v2_10K_neutral` | 17 | -1.68946% → -1.68947% | -2.3592 → -2.3592 |

**None establishes support**; both neutralized variants point the wrong way. D7/D8 changed
ties, eligibility and neutralization, so this is not an exact replication of the old
implementation. No held leg lacks its next-month return, which is not evidence that
survivorship is repaired ([Batch B output](../results/returns_h0_development.json)). `H1n` is
a historical ledger label for neutralized cosine variants, not a claim-level H1 signal.

#### D16 rerun on corrected filing times (2026-11-21)

Under [D16](DEVIATIONS.md#d16-replace-h0-knowledge-times-with-qualified-acceptance-times),
logged before anything ran, every H0 signal with a qualified time took that time
([build receipt](../results/d16_h0_time_correction.json)). 103 of 21,502 times changed: the 5
look-ahead MHLA filings, 51 late ones and 47 that move without changing the first close. The
other 4,581 rows kept their stored time and were confirmed assignment-insensitive. The one
acceptance on a possible early-close afternoon (2022-12-23, 15:19 ET) is on a full trading day
under NYSE Group's published calendar.

The unchanged runner ran once with one thread (D14)
([results](../results/returns_h0_development_d16.json),
[comparison](../results/d16_h0_rerun_comparison.json)); 78 fields changed, all slightly. The
largest movement is in the raw `v1_10K_raw` event panel: t goes from 1.84 to 2.03 with the
coefficient almost unchanged (1.7446 → 1.7451). Its sign is the **opposite** of the Lazy
Prices prediction, it uses 17 month clusters and it is not a registered test, so it supports
nothing. With the registered trial count (10 per family) and 17 aligned months, conditional
deflated Sharpe probabilities ([diagnostics](../results/current_vintage_diagnostics_d16.json))
are 0.035 (`v1_10K_raw`) and 0.195 (`v2_latest_raw`), and 0.024 and 0.001 for the neutralized
variants; the frozen D4 predicate marks both raw variants **not_supported**. PBO is not
estimable below 32 months.

#### D17: event-time neutralized H0 panel (exploratory)

[D17](DEVIATIONS.md#d17-define-the-event-time-neutralized-signal-for-the-h0-event-co-primary)
was registered and tagged before it ran, but after earlier development results, so it is
exploratory ([D17 run](../results/h0_event_neutral_development.json)):

| Variant | Coefficient (expected < 0) | Month-clustered t | Wild bootstrap p | Events |
|---|---:|---:|---:|---:|
| Latest filing | +0.113 | 0.46 | 0.67 | 12,575 |
| 10-K only | +1.366 | 2.60 | 0.13 | 4,181 |

**Neither supports the hypothesis; both point the wrong way.** The 10-K variant's clustered t
of 2.60 shrinks to a bootstrap p of 0.13, the over-rejection F10 predicts with 16 clusters.
Two new H1n configurations were logged, so H1n now counts 12.

### H4: text change and later fundamentals

| Signal -> outcome | Historical t | Rebuilt t | Observations |
|---|---:|---:|---:|
| Neutralized -> dROA | -1.2475 | -1.2007 | 2,655 |
| Neutralized -> earnings decline | -0.0151 | -0.0616 | 2,658 |
| Neutralized -> impairment | +1.1836 | +1.2221 | 2,689 |
| Raw -> dROA | -1.2049 | -1.1520 | 2,655 |
| Raw -> earnings decline | -0.0745 | -0.1836 | 2,658 |
| Raw -> impairment | +1.0191 | +1.0604 | 2,689 |

**No support:** all absolute t values are below 1.23, versus the 3.0 bar. dROA and impairment
have the expected directions; earnings decline is wrong-sign and near zero. With
development-only winsorization (D6), the dROA mean changes from -2.2972% to -4.0996% and the
primary coefficient from -19.9324 to -36.1710 in native score/ROA units. Firm counts are
607/608/614 by outcome, with only seven year clusters ([output](../results/h4_development.json)).
The conclusion reproduces, not the exact estimates (original inputs were unavailable to
decompose the change). A5 changed no H4 10-K order (F9). Every H4 stage stays held.

### H5 and H6: validity

- **H5b, H5c: invalid (F2).** Their development signs oppose the published effects because of
  survivor selection. **H5a** (Friday-evening 8-Ks versus other 8-Ks, +0.97%, t = 2.0) is
  subject to the same selection and is not a replication. H5 was not rerun on 2026-11-13.
- **H6(a)** reproduces the historical entry exactly: adjusted coefficient 0.04202909 (+4.20
  percentage points), t = 1.7377173, 22,745 filings, 499 quiet filings and 1,103 firms;
  observed formal-outcome rates 17.8357% versus 13.7238%. This is below the 3.0 bar. The unit
  is a filing, with year fixed effects and firm-clustered inference, and the broad outcome
  includes amendments that are not earnings restatements ([output](../results/h6_development.json)).
- **H6(b): invalid (F2).** Its pipeline diagnostic (CAR +4.5792%, t = 1.7708, 316 events, 15
  month clusters) is not a return finding.

### D18: prospective H4/H6a holdout

The exposed 2022-2025 windows are retired as confirmatory evidence. Confirmatory H4/H6a
evaluation will use filings accepted from 2026-11-22 to 2027-11-21, evaluated once: H6a not
before 2028-12-31 and H4 not before 2029-03-31. [periods.py](../src/asof/periods.py) enforces
those dates ([D18](DEVIATIONS.md#d18-move-h4-and-h6a-confirmatory-evaluation-to-a-prospective-holdout)).
H6b stays invalid: fixing survivorship needs delisting-inclusive prices, which the owner
declined to buy on 2026-11-21.

### H7: social sentiment, closed unregistered

A [point-in-time pipeline](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/src/asof/social.py)
was built and tested, but no X data was fetched
([design note](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/H7_SOCIAL_SENTIMENT.md)).
The candidate scorer failed qualification on human-labelled finance text
([receipt](../results/sentiment_scorer_validation.json)): on Financial PhraseBank, VADER scores
57.1% accuracy (macro-F1 0.49), below the 61.4% that always predicting "neutral" would get. On
2026-11-21 the owner declined further spending on model or social-media access, so H7 is
closed unregistered: **there is no H7 result, null or positive.**
