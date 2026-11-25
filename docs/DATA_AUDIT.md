# Data audit

This is the reference for where ChronoLedger's data comes from, how each input was
audited and how the local data was built, current state first. The full working log it
replaces (protocols, approvals, request-by-request accounting, superseded plans) is the
[original DATA_AUDIT.md](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md)
at tag `archive-2026-11`. See [CURRENT_STATUS](CURRENT_STATUS.md) for safe entrypoints and
[ARCHIVE](ARCHIVE.md) for retired code. All empirical results are development-only, return
data after 2024-07-31 is sealed, and nothing here is scientific acceptance or a tradable claim.

## Current status

| Area | Current state | Where |
|---|---|---|
| SEC acceptance times, H0 | All 16,921 timing-sensitive accessions qualified against their filing headers (A4). Five MHLA filings were stored 4-5 hours early. D16 replaced 103 H0 knowledge times and reran H0; no conclusion changed. The H0 knowledge times in use are the D16-corrected ones. | [Timestamp audit](#sec-acceptance-timestamp-audit) |
| SEC acceptance times, H4/H6a (2012-2018) | A5: 0 of 262 timing-sensitive filings qualify under the frozen rule; a post-hoc Eastern reading changes no H4/H6a assignment. | [Timestamp audit](#sec-acceptance-timestamp-audit) |
| Survivorship | Free prices cover today's tickers only. H5b, H5c and H6(b) are invalid under this universe (F2). Return tests use signals from 2023 onward (D1). | [Coverage](#coverage-and-survivorship) |
| Survivorship-free prices | No free source qualifies. The owner declined paid data on 2026-11-21, so F2 stands. | [Source review](#price-vendor-and-survivorship-free-source-review) |
| Price and return integrity | Split look-ahead fixed (F3), share-count typos cleaned, impossible returns excluded at monthly and daily frequency (F6/D9), checksummed price snapshot. | [Integrity](#price-and-return-integrity) |
| Referee | Clock authority passes. The gate is blocked only by monthly calibration (F10), a permanent limit of this design. | [REFEREE.md](../results/REFEREE.md) |
| Holdout | Code refuses price access after 2024-07-31. D18 moved H4/H6a confirmation to a prospective holdout of filings accepted 2026-11-22 to 2027-11-21. | [Holdout boundaries](#holdout-boundaries) |
| H4/H6 file-backed stages | Hard held, even with a valid scope file. | [Access controls](#access-controls) |

## Data sources and provenance

| Source | What it supplies | Used for | Where it is kept |
|---|---|---|---|
| [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) (submissions, XBRL company facts and frames) | Filing metadata, stored acceptance times, `dei:EntityPublicFloat` and `dei:EntityCommonStockSharesOutstanding` | H0 universe, filings and shares; firms missing from the bulk archive | Local HTTP cache under `data/` |
| SEC nightly bulk archives ([bulk_download.py](../scripts/bulk_download.py)) | `submissions.zip` and `companyfacts.zip` for all filers | Entity/filing tables, H4/H6 facts, the referee fixture | `data/raw/bulk/` (local) |
| EDGAR full-index files ([master_index.py](../scripts/master_index.py)) | Quarterly filing index from 2011 | Coverage audits, extraction benchmark | `data/master_index_2011_<year>.parquet` (local) |
| EDGAR filing headers and index pages | `ACCEPTANCE-DATETIME`, `FILING-DATE`, listed CIKs | Timestamp audit only | Raw bodies in ignored `data\timestamp_full_a3` and `data\timestamp_full_a4`, hash-pinned in the reports |
| SEC current CIK-ticker map | Today's tickers | H0 universe and the float coverage audit | Local cache |
| Daily prices: free vendor (Yahoo chart API, [prices.py](../src/asof/prices.py)) | Quotes, dividends, split events | H0/H5/H6(b) returns | Raw caches and processed snapshot, local only |
| [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | FF5 plus momentum factors, NYSE size breakpoints | Factor-adjusted returns, size filter, nominal 16:00 ET trading-date list | Cached archives, local only |

**In git:** code, aggregate receipts in `results/` (counts, hashes, lineage), the
append-only trial ledger and the hash-locked dependency file. **Local only (ignored
`data/`):** raw SEC caches and bulk ZIPs, DuckDB stores, parquet inputs, raw and
processed prices, French archives, private timestamp lists and raw header bodies.

**Handling limits.** SEC data is public, but EDGAR requires a contact User-Agent
(`ASOF_USER_AGENT`) and fair-access pacing (SEC publishes a 10 requests/s ceiling; the
project's limits are lower). Price data is for personal research and never
redistributed; French factors are cited and linked, not re-hosted. Only derived
statistics are published.

**Rebuild provenance.** The 2026-11-13 devbox rebuild was a new download, not a
byte-for-byte restoration of the handoff caches. New H0 ledger entries hash
`data/h0_market_inputs.json`, which fingerprints the guarded price caches and French
archives; H4 fingerprints entity metadata and H6 the companyfacts archive. Lineage records
Python and package versions; historical entries did not, so differences from them are not
attributable solely to new downloads. The bulk SIC field is the **current**
classification, with no historical knowledge time, so H4 and neutralized H0 use it as a
fixed proxy ([archived detail](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#rebuild-provenance-and-verification)).

## Access controls

- **Date contracts.** A shared development-only date envelope ([DOCUMENT_SCOPE](DOCUMENT_SCOPE.md))
  guards SEC, derived-feature, KPI and benchmark reads. Unknown dates fail closed.
- **Fact windows.** The companyfacts readers in [bulk.py](../src/asof/bulk.py) require an
  immutable `FrozenFactWindow`, and `asof ingest` validates a frozen scope before creating
  any client, cache or database. Filtering is **not** byte-level isolation: raw ZIP members
  are still decoded in memory, and there is no OS filesystem or network sandbox.
- **Hard holds.** Every H4 stage (`bulk`, `sample`, `features`, `pairs`, `outcomes`, `test`)
  and every H6 stage stops before reading data. A scope file does not lift a hold.
- **D13 incident.** An exploratory KPI screen read 4-6 raw annual bodies inside the
  H4/H6(a) reserved calendar. With D6 and D15, this is why the 2022-2025 H4/H6a windows
  cannot count as untouched ([D13](DEVIATIONS.md#d13-exploratory-kpi-disclosure-screen-crossed-reserved-calendars)).
- **Ledger and lock.** The [ledger anchor](../results/trial_ledger_chain_anchor.json) pins
  the 74-row prefix SHA-256; later appends are hash-chained under a file lock (not
  tamper-proof). [requirements-dev.lock](../requirements-dev.lock) has 45 exact pins whose
  1,310 SHA-256 hashes matched public PyPI ([receipt](../results/dependency_lock_verification.json)).
  ([Archived detail](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#assurance-and-limits).)

## Coverage and survivorship

Coverage of public-equity issuers by free price data, by public float. Generated from
EDGAR full-index files (2011–2026), SEC's current CIK-ticker map and the XBRL frames API
(`dei:EntityPublicFloat`). Having a current ticker is an upper bound on whether a free
source has the firm's price history.

| Float year | $1M–50M | $50M–500M | >$500M |
|---|---|---|---|
| 2011 | 24% | 37% | 55% |
| 2012 | 26% | 37% | 57% |
| 2013 | 27% | 38% | 58% |
| 2014 | 30% | 40% | 59% |
| 2015 | 35% | 44% | 61% |
| 2016 | 40% | 46% | 66% |
| 2017 | 45% | 49% | 68% |
| 2018 | 48% | 53% | 71% |
| 2019 | 53% | 57% | 76% |
| 2020 | 56% | 61% | 78% |
| 2021 | 56% | 55% | 78% |
| 2022 | 64% | 62% | 84% |
| 2023 | 72% | 76% | 88% |
| 2024 | 84% | 85% | 92% |
| 2025 | 94% | 94% | 97% |

Issuer counts per bucket range from about 1,000 to 2,700 per year. This historical audit
motivated D1; it was not regenerated after the rebuild. Conclusions:

- The original 2011–2018 development period would lose 30–45% of large issuers, including
  acquisition targets (takeover premiums) and failures (large losses). **The direction of
  the bias is unknown**, so delisting-return bounds cannot fully repair it.
  [D1](DEVIATIONS.md#d1-restricting-return-tests-to-periods-with-adequate-free-price-coverage)
  therefore restricts return tests to signals from 2023 onward, where large-issuer coverage
  is 88–97%.
- **F2, the current-ticker universe limit.** The H0 universe uses today's tickers and a
  public float of at least $200M. In January 2023–June 2024 it holds 36.6% of all 7,378
  10-K filers but only 11.0% of NT 10-K/10-Q filers, 27.1% of Item 4.02 filers and 20.6% of
  Item 4.01 filers. Distressed filers are 1.3–3.3x less likely to be included, and the
  excluded ones disproportionately disappeared later. H5b, H5c and H6(b) are therefore
  **invalid**, not evidence against the published effects
  ([F2](FINDINGS.md#f2-distress-event-tests-are-invalid-under-a-current-ticker-universe),
  [placebo](../results/returns_event_diagnostics.json)). A relative-coverage ratio of 0.8
  is only a diagnostic floor; F2 is not lifted because a vendor returns more tickers.
- **Identity.** Pair and bulk metadata disagree on CIK for 404 accessions (305 in
  development). These are co-registrant filings; A4 resolved all 404 to the listed pair
  CIK, which H0 already uses. An SEC-only identity/exit check
  ([sec_identity_oracle.json](../results/sec_identity_oracle.json)) found 12 partial
  textual supports, 8 unresolved cases and zero terminal-payoff certifications.

## SEC acceptance-timestamp audit

### Why it was needed

Across the 21,502 H0 signal rows, 165 acceptance times differ between the SEC bulk
archive and the per-company API, all by +4h (105) or +5h (60); the development slice has
16,226 rows and 124 disagreements. A `Z` suffix does not certify UTC, and agreement is
not proof: one agreeing case was 5h late in **both** sources. The broad JSON-UTC claim
was withdrawn and P0 was blocked
([F9](FINDINGS.md#f9-p0-acceptance-time-authority-is-not-uniformly-certified-by-json-z-fields),
[authority packet](../results/p0_acceptance_authority_audit.json)). An offline
[screen](../results/p0_assignment_plan.json) flagged 17,389 accessions whose assignment
could change (an over-approximation, not a count of errors). The
[audit inventory](../results/timestamp_full_plan.json) covers 16,921 assignment-risk
accessions and 34,354 header/index URLs, including 102 pinned cache hits.

### How a time is qualified

Regulation S-T Rule 13(a)(2) moves a filing submitted after 5:30 p.m. Eastern to the next
business day, so if the header `ACCEPTANCE-DATETIME` is Eastern civil time, its
`FILING-DATE` must roll at 17:30 in both seasons. The clock-basis test CB1
([receipt](../results/timestamp_a3_clock_basis_cb1.json)), frozen before any A3 request,
found daylight weekday filings accepted 16:30–17:30 kept the same date in 240/240 earlier
and 262/262 new headers, with 0/1,355 and 0/1,277 early rolls. That rejects fixed-EST and
UTC readings. (SEC's PDS specification defines an acceptance **date**, not the field clock;
[documentation review](../results/project_closure_review.json).) An accession qualifies
when every archive-path header and index was read, their wall clocks agree and convert
uniquely through daylight-saving changes, lie inside the frozen candidate envelope, and
carry a filing date consistent with the 17:30 cutoff.

### Stages

| Stage | Requests | Outcome | Usage after / ceiling |
|---|---:|---|---:|
| Documentation probe, 2026-11-16 ([review](../results/sec_stage1_refetch_review.json)) | 1, then a 4 MiB refetch | The page does not define acceptance-time format, clock or time zone | 48 / 150 |
| Header pilot, 48 accessions in six pools ([report](../results/header_pilot_reconciled.json)) | 92 new + four cache hits | All 48 header/index walls agree. Under an Eastern assumption, bulk is five hours later (winter) or four (summer) in the disagreement pools; two agreeing records match neither source | 140 / 150 |
| Original full audit, 2026-11-16 ([review](../results/timestamp_full_review.json)) | 1,281 | Stopped on HTTP 503. 641 header/index pairs conditionally complete; all 16,921 still unqualified. 97 dispatch gaps below 0.5 s: a precision miss against our own protocol, not an SEC fair-access breach | 1,421 / 34,402 |
| A1 ([review](../results/timestamp_full_a1_review.json)) | 1,716 | Stopped on a transport timeout. All 108 designated clock disagreements match the API under Eastern; bulk is five hours later in 37 and four in 71. Zero qualified | 3,137 / 34,402 |
| A2 ([review](../results/timestamp_full_a2_review.json)) | 109 | Stopped on a second HTTP 503 after 50 of 3,000 accessions. One-sided 95% upper bound 1.50% on 314 readable cases; 91.26% if the 2,955 unread cases count as errors | 3,246 / 34,402 |
| A3, 2026-11-20 ([report](../results/timestamp_full_a3_report.json)) | 2,800 | CB1 passed on 1,564 earlier headers and replicated on 1,400 new ones. **2,708 of 16,921** qualified; 14,213 unread, none failed. 0 qualified accessions show stored-time look-ahead ([impact](../results/timestamp_a3_impact.json)). Stopped when the six-pause cap was used up | 6,054 / 34,402 |
| A4, 2026-11-20/21 ([revision 2](../results/timestamp_full_a4_report_r2.json)) | 28,616 | Every resource read. **16,921 of 16,921** qualified; 404 of 404 CIK disagreements resolve to the listed pair CIK. **Five MHLA filings stored 4-5 hours early** (look-ahead); 51 reach a later close (delay only) | 34,670 / 35,000 |
| A5, 2026-11-21 ([report](../results/timestamp_a5_report.json)) | 529 | 262 timing-sensitive 2012-2018 H4/H6a filings. 110 have no header page (HTTP 404); the Eastern pattern replicates on the 152 that exist, but the frozen integrity sub-check failed, so **0 of 262 qualify**. A [post-hoc reading](../results/timestamp_a5_posthoc_sensitivity.json) changes no H4/H6a assignment | 35,199 / 35,800 |
| D16 correction, 2026-11-21 ([receipt](../results/d16_h0_time_correction.json)) | 0 | **103 of 21,502** H0 knowledge times replaced: the 5 look-ahead filings, 51 late ones and 47 that move without changing the first close. H0 rerun once with one thread; no conclusion changed ([comparison](../results/d16_h0_rerun_comparison.json)) | — |

The A4 original report left 12 accessions unresolved because of a raw-reader bug for
pinned-cache headers; a disclosed correction produced revision 2 and the original is kept.
All stage runners are archived (for example
[run_full_timestamps_a4.py](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/run_full_timestamps_a4.py)
and [run_timestamp_a5.py](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/run_timestamp_a5.py));
pacing, retry and stop rules are in the
[archived detail](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#approved-full-timestamp-metadata-check).
Other receipts: [original-audit report](../results/timestamp_full_report.json); A3 [config](../results/timestamp_full_a3_config.json),
[pilot gate](../results/timestamp_full_a3_pilot_gate.json) and [amendment](../results/timestamp_full_a3_amendment1.json);
header-pilot [config](../results/header_pilot_config.json) and [status](../results/header_pilot_status.json);
documentation-probe [config](../results/sec_stage1_config.json), [requests](../results/sec_stage1_requests.jsonl),
[review](../results/sec_stage1_review.json) and [refetch config](../results/sec_stage1_refetch_config.json);
P0-era [raw bulk sample](../results/p0_raw_bulk_sample.json), [first](../results/p0_cached_authority_audit.json)
and [completed](../results/p0_cached_authority_audit_v2.json) cached rechecks, and the [staged pilot plan](../results/timestamp_authority_plan.json).

### Current conclusion

- **H0 is resolved.** All 16,921 H0 accessions are qualified and the H0 knowledge times in
  use are the D16-corrected ones. The referee's `time_authority` check passes at level 4,
  including a check that every H0 knowledge time in use equals its qualified time
  ([D16 rerun](FINDINGS.md#d16-rerun-on-corrected-filing-times-2026-11-21)).
- **The MHLA cause.** Both SEC JSON sources stored the Eastern wall-clock time with a UTC
  label: a 10-Q accepted at 17:07 ET on 2023-05-09 was stored as 17:07 UTC, before that
  day's 16:00 close ([F9 update 2](FINDINGS.md#f9-update-2-every-required-accession-qualified-five-stored-early-2026-11-21)).
  The one acceptance on a possible early-close afternoon (2022-12-23, 15:19 ET) fell on a
  full trading day per NYSE Group's published calendar, so its 16:00 close stands.
- **H4/H6a.** H4 and H6a compare filings with each other and use dates rather than
  trading closes, so a shared clock offset cancels. But 132 of the 262 older bulk times
  are 4-5 hours early, which would matter for any future return test on older bulk times
  ([details](FINDINGS.md#h4h6-timing-the-event-time-h0-panel-the-prospective-holdout-and-social-sentiment-2026-11-21)).
- **Limits.** Qualification assumes EDGAR's own clock was synchronized and Rule 13(a)(2)'s
  Eastern basis; no timestamp was checked against an external clock.

## Price and return integrity

- **Split look-ahead (F3).** Yahoo adjusts *all* historical prices for every split up to
  today. A request that stopped at the cutoff returned prices already adjusted for later
  splits but not the split *events*; FFAI showed $1,200 when it traded at pennies. From
  2026-11-13 each request spans the full history; **every quote and dividend after the
  cutoff is discarded in memory before caching**, and only later split events (date and
  ratio) are kept, solely to reverse the vendor's adjustment. The strip function keeps
  only `exchangeTimezoneName` from metadata, because the `meta` object can carry a current
  price. Caches built before this fix should be rebuilt.
  ([Archived detail](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#price-request-change-f3).)
- **Share counts (F3, D7).** XBRL typos (PKG filed 89.8 billion shares against about
  89.8 million) are cleaned point in time: a jump of more than 10x takes effect only after
  a strictly later filing confirms it.
- **Impossible returns (F3, F6, D9).** Monthly returns below −100% are dropped. Daily event
  loaders had bypassed that guard: across 2,733 usable daily histories, two returns were
  below -100% and one was non-finite, and 503 nonpositive vendor-adjusted observations
  fell in 2021-2022. Both frequencies now log and exclude unusable price ratios
  ([F6](FINDINGS.md#f6-the-f3-price-return-guard-did-not-cover-daily-event-inputs)); this
  does not validate the vendor's adjusted series. The referee's `data_integrity` threat
  also fails any long-short mean above 5% per month
  ([F3](FINDINGS.md#f3-three-data-bugs-caught-by-an-implausible-backtest)).
- **Processed snapshot.** The `prices` stage writes `h0_monthly_prices.parquet`,
  `h0_daily_returns.parquet` and `h0_price_snapshot.json` locally
  ([marketdata.py](../src/asof/marketdata.py)). The manifest pins raw-cache SHA-256s,
  universe, processing source hashes, cutoff, runtime versions and output checksums;
  analysis refuses missing, stale, corrupt or post-cutoff snapshots, with no raw fallback.
  The rebuild produced 2,753 cache files but 2,733 nonempty daily histories (file count is
  not coverage); 57,195 monthly rows and 14,433,060 daily returns round-tripped exactly.
  Snapshot generation took 154.955 seconds and the full four-variant H0 run 61.073 seconds
  (local timings). A 100-firm equivalence check against the pinned handoff revision passed
  for all four variants across 17 formation months
  ([h0_optimization_equivalence.json](../results/h0_optimization_equivalence.json)).

### Holdout boundaries

- [`price_end_allowed`](../src/asof/periods.py) refuses analysis price access past
  2024-07-31 unless the holdout is explicitly opened. July 2024 stays visible for June
  formations' return tail, overlapping some nominal July holdout-event labels.
- On 2026-11-12, before the guard existed, AAPL's full daily history was downloaded once,
  used only to confirm the as-traded close on 2014-06-06 and 2020-08-28, then deleted. No
  returns were computed from it.
- [D18](DEVIATIONS.md#d18-move-h4-and-h6a-confirmatory-evaluation-to-a-prospective-holdout)
  retires the 2022-2025 H4/H6a windows as confirmatory evidence. Confirmation uses filings
  accepted from 2026-11-22 to 2027-11-21, evaluated once: H6a not before 2028-12-31 and H4
  not before 2029-03-31. `periods.py` enforces those dates.

## Price-vendor and survivorship-free source review

**Conclusion.** No free source supplies dated security identities, delisted histories and
terminal payoffs with rights compatible with a public, reproducible project. Sharadar was
the primary small-budget candidate (about $39 for one month), conditional on rights, but
**the owner declined paid data on 2026-11-21**, so F2 stands. The review used public
documentation only: no account, key, vendor contact, purchase or data acquisition.

| Source | Documented strengths | Blocking limits |
|---|---|---|
| Tiingo | Raw and adjusted prices, split/dividend cleaning | [Terms](https://www.tiingo.com/tos/) (last updated 2026-11-05): section 1.6(a) bars Starter/trial users from keeping data **or derived outputs** in durable storage; paid data must be deleted on termination; section 1.7 restricts model use, and even the Power plan limits models and outputs to internal purposes. Incompatible with retained caches, receipts and public results |
| Sharadar | Share-class permatickers, ticker histories, dated SIC changes, cash and stock merger consideration | Personal-use terms. Section 8 needs prior written approval to publish data-fitness evaluations; section 10 requires deletion within 30 days after termination. CVRs excluded |
| Norgate | Inactive history, stable `assetid` | No historical ticker/name, historical industry or terminal returns; trial covers only the latest two years |
| EODHD | Cheap price-only fallback | Pre-2018 delistings have EOD only; identities, actions and payoffs need a substantial separate overlay |
| CRSP | Strongest documented complete-return architecture, permanent PERMNO/PERMCO | Institutional entitlement, not a free or personal account |
| Free Yahoo/Stooq-type sources | Quotes, dividends, splits | Inactive coverage, terminal payoffs and dated identity unknown; no redistribution licence |

A 12-case test panel of continuing, merged, delisted and renamed companies is defined in
[price_source_test_panel.json](../results/price_source_test_panel.json); no source was
tested against it. A proposed pilot ceiling (24 cases in six strata, at most 40 securities,
150 requests and 50 MiB) was never approved; owner consent cannot supply missing vendor
rights. Full comparison: [RESEARCH_PLAN](RESEARCH_PLAN.md#historical-equity-source-comparison-draft).

## Data rebuild runbook

**Historical reproduction record, not current launch instructions.** The commands
reproduce the executed 2026-11-13 build and its counts; nothing was rerun for this cleanup.
Current code deliberately holds some stages: do not work around a hold with older code.
Check [CURRENT_STATUS](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/CURRENT_STATUS.md#do-not-confuse-these-entrypoints) and obtain
source, resource and study approval first.

**Prerequisites.** The locked Python 3.12 environment from the [README](../README.md#run-it)
and a contact e-mail in `ASOF_USER_AGENT`, as the SEC requires. Run stages one at a time
and stop on a nonzero exit or unexplained feature errors. Never run two SEC download pools
at once (rate limiters are per process). Use `iter_companyfacts`, not a dictionary of all
firms. Use a full clone with tags: referee chronology checks need the pinned historical
commit and preregistration tags. Do not commit private index URLs.

From the repository root in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\bulk_download.py
.\.venv\Scripts\python.exe scripts\h4_fundamentals.py bulk sample
.\.venv\Scripts\python.exe scripts\master_index.py
cmd /d /c '".venv\Scripts\python.exe" scripts\h0_data.py universe filings features pairs shares prices < NUL > data\h0_rebuild.log 2>&1'
cmd /d /c '".venv\Scripts\python.exe" scripts\h4_fundamentals.py features pairs outcomes < NUL > data\h4_rebuild.log 2>&1'
```

| Step | Current status |
|---|---|
| [bulk_download.py](../scripts/bulk_download.py) | Not held. Downloads `submissions.zip` and `companyfacts.zip` with resume |
| [master_index.py](../scripts/master_index.py) | Not held. Streams 2011 to the current UTC quarter into `data/master_index_2011_<current year>.parquet`; a failed request leaves the previous output unchanged. Filing metadata only |
| [h0_data.py](../scripts/h0_data.py) stages | Not held. `filings` reads missing firms from `submissions.zip` when present and uses the API only for firms absent from it. The stored acceptance field is not certified by import (see the timestamp audit) |
| [h4_fundamentals.py](../scripts/h4_fundamentals.py) `bulk sample` and `features pairs outcomes` | **Hard held** in current code. `bulk` writes `data/bulk_entities.parquet` and `data/bulk_filings.parquet`, which H0 neutralization, H6 and the referee also read, so a fresh clone cannot rebuild those files without a new owner decision |
| D16 corrected signals | **Archived step.** [d16_h0_time_correction.py](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/d16_h0_time_correction.py) wrote `data/h0_signals_d16.parquet` from the A4 revision-2 qualified times (local A4 outputs required). `data/h0_signals.parquet` is left untouched |

`NUL` gives Windows process pools a valid stdin (a closed pipe can break
`ProcessPoolExecutor`). The `prices` stage creates the processed snapshot; if only
processing code or the runtime changed, run `scripts\h0_data.py price_snapshot` instead of
downloading again. A missing, stale or corrupt snapshot error is a stop condition.

**Expected counts (2026-11-13 build).** 48,452 entities, 3,190,805 filtered bulk filings,
a 1,500-CIK H4 sample, 21,502 H0 signal pairs, 10,581 H4 pairs and 19,493 H4 outcome
filings. H0 features covered 32,508 filings; H4 requested 12,184 (10,806 uncached), with
zero feature errors in either build. Fresh downloads or dependency upgrades may change
counts and fingerprints; do not silently reuse a different snapshot or rewrite old trials.

### Referee pilot fixture

The full referee also needs `data/pilot.duckdb`, which neither Git nor the H0/H4 stages
supply. The executed fixture streamed the submissions and company facts of five public
issuers from the local bulk archives into the bitemporal store: 132,527 facts, all sourced
to exact acceptance times (a new verification fixture, not the original handoff pilot).
The [archived build snippet](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#referee-pilot-fixture)
is **no longer runnable as written**: it calls `iter_companyfacts` without a
`FrozenFactWindow`, which current code rejects, and a windowed rebuild would filter facts
and not reproduce the executed fixture. Never append to an existing fixture; build a
separately named database if recovery is needed. [run_bench.py](../scripts/run_bench.py)
also reads this fixture.

### Development execution and outputs

After inspecting rebuild logs and with the fixture in place, H0 runs on the D16-corrected
signals with one numerical thread (D14). Write to a new output path so the recorded
results file is not overwritten:

```powershell
$env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:MKL_NUM_THREADS = "1"
.\.venv\Scripts\python.exe scripts\h0_backtest.py --signals data\h0_signals_d16.parquet --output data\h0_rerun.json
.\.venv\Scripts\python.exe -m asof.referee
```

Every H0 run appends trial-ledger rows, so it is an evaluation, not a smoke test; keep
runners sequential and never edit or remove failed rows. The `benchmark_h0.py` equivalence
step is [archived](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/benchmark_h0.py).
`h4_fundamentals.py test` and [h6_quiet.py](../scripts/h6_quiet.py) are hard held;
[h5_events.py](../scripts/h5_events.py) reads `data/h0.duckdb`. Designs (windows, filters,
controls, CAR -260..-21 / +1..+60) are in the [preregistration](PREREGISTRATION.md),
[v2](PREREGISTRATION_V2.md) and [deviations](DEVIATIONS.md); event windows must end by
2024-07-31, so late development events can drop out.

Outputs: [current H0](../results/returns_h0_development_d16.json), [H0 before D16](../results/returns_h0_development.json),
[H4](../results/h4_development.json), [H6](../results/h6_development.json), [H5](../results/returns_h5_development.json)
and [REFEREE.md](../results/REFEREE.md). Values are native ratios (multiply returns by 100
for percent). A completed run or a technical gate pass is not scientific acceptance.
([Archived detail](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#development-execution-and-output-contract).)

Other kept scripts: [event_diagnostics.py](../scripts/event_diagnostics.py) (placebo),
[leakprobe.py](../scripts/leakprobe.py), [calibrate_tfidf.py](../scripts/calibrate_tfidf.py),
[make_figures.py](../scripts/make_figures.py) (reads `results/` only) and the offline checks
[check_repository.py](../scripts/check_repository.py) and [smoke_wheel.py](../scripts/smoke_wheel.py).

## Known limitations and open items

- **Survivorship (F2).** Permanent under free data; distress-event tests need delisted
  prices and terminal payoffs, and paid data was declined.
- **Monthly calibration (F10).** Registered monthly tests over-reject at 17-28 months; this
  permanent limit alone blocks the referee gate
  ([F10 status](FINDINGS.md#f10-status-a-permanent-limit-of-this-design-2026-11-20)).
- **Older bulk times.** 2012-2018 bulk acceptance times are unqualified (0 of 262) and often
  4-5 hours early; a future return test on them needs header verification.
- **Industry and calendar.** SIC is the current classification, so neutralized H0 and H4
  are conditional on a proxy. Closes use NYSE's rule-based 1:00 p.m. early closes for 2011-2028,
  checked against NYSE's published 2026-2028 dates (D19); other dates are refused rather than
  guessed. Unscheduled closures are taken from the trading calendar in the data, not certified.
- **Vendor quality.** Guards exclude impossible prices but do not validate the vendor's
  adjusted series or dividends.
- **Reproducibility.** Under current holds a fresh clone cannot rebuild the bulk
  entity/filing tables or the referee fixture, and the D16 builder is archived.
- **Open decisions (owner).** A new data source, any held H4/H6 stage, holdout access and
  the July 2024 overlap each need an explicit decision.

## Archived sections

Dropped from the [original file](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md) as superseded, procedural or outside data provenance:

| Original sections | What they held |
|---|---|
| [Assurance and limits](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#assurance-and-limits), [validation tooling scope](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#validation-tooling-scope) | Dated access-control, ledger, lock and lint receipts |
| [Full timestamp check](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#approved-full-timestamp-metadata-check), [48-filing pilot](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#conditional-48-filing-pilot-not-clock-certification), [cached recheck](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#cached-timestamp-recheck), [P0 planner](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#approved-offline-p0-assignment-planner), [P0 verdict](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#batch-c-part-1-p0-integrity-verdict--stop) | Run-by-run timestamp protocols, pacing, pool tables and the original P0 stop |
| [Local-reader memory safeguards](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#local-reader-memory-safeguards), [offline cost and run-contract fixes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#offline-cost-run-contract-and-measurement-fixes) | Model runtime receipts and archived helper modules |
| [Bounded gate advancement](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#bounded-gate-advancement-2026-11-13), [six-package queue](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#six-package-dependency-queue) | Coordination queue, Batch A/B/E records and synthetic calibrations (results now in F10) |
| [Source-pilot contract](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#source-pilot-contract-proposed-not-activated), [rights reconciliation](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#current-source-rights-reconciliation-2026-11-13) | Unactivated identity/payoff pilot design and clause-by-clause vendor terms |
| [Exact source audit](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#exact-source-audit-fixes-versus-unresolved-contracts), [P2 map](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#p2-source-to-contract-and-fixture-map) | Code-level time/industry contract gaps and synthetic fixtures |
| [Next steps and timing](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#approval-only-next-steps-and-timing), [holdout decision packet](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md#holdout-and-reproducibility-decision-packet-release-remains-blocked) | Superseded maturity dates and pre-D18 holdout gates |

Their receipts stay in `results/`: Batch B [factor audit](../results/batch_b_factor_audit.json),
[validation](../results/batch_b_validation.json) and [blocked diagnostic](../results/current_vintage_diagnostics.json);
audit rosters and blank templates ([claims template](../results/claims_annotation_template.csv),
[endpoints roster](../results/endpoints_audit_roster.json), [endpoints template](../results/endpoints_annotation_template.csv));
the [KPI cache inventory](../results/kpi_development_cache_inventory.json); and the
[offline contract fixtures](../results/offline_contract_fixtures.json).
