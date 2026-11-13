# Data audit: survivorship coverage of free price data

Generated from EDGAR full-index files (2011–2026), SEC's current CIK-ticker map, and the XBRL
frames API (`dei:EntityPublicFloat`). Having a current ticker is an upper bound on whether a free
source has the firm's price history. Firms acquired, merged, taken private, or failed since then
are usually missing.

The float-bucket coverage table is the historical audit that motivated D1, not a
bucket table regenerated during this continuation. Fresh reconstruction,
runtime/lineage checks, and the referee's distress contrasts are identified separately.

Rebuild the quarterly index with `python scripts/master_index.py`. It starts in 2011 and
stops at the current UTC quarter, reusing the EDGAR client's per-URL cache on retries.
Quarters are streamed into `data/master_index_2011_<current year>.parquet`; a failed request
leaves any previous completed output unchanged. This index contains filing metadata, not
prices, and does not open a return holdout.

When `data/raw/bulk/submissions.zip` exists, the H0 `filings` stage reads missing
firms directly from it, including every form, historical page, and exact acceptance
time. It uses the individual submissions API only for firms absent from that archive.
This avoids re-downloading metadata already obtained from the same public source;
malformed requested archive members fail explicitly rather than silently dropping a firm.
Overlapping recent/history pages are deduplicated by accession at ingestion, retaining
the recent-page row first, as in the bulk metadata reader.

### Rebuild provenance and verification

The 2026-11-13 devbox rebuild is a new download, not a byte-for-byte restoration
of the handoff's local caches. Input fingerprints may differ. New H0 ledger entries
include a hash of `data/h0_market_inputs.json`, which fingerprints the guarded
price caches and cached French factor/breakpoint archives without publishing their
contents. H4 also fingerprints the entity metadata used for SIC controls; H6
fingerprints the companyfacts archive and its sample or universe.
New lineage also records Python and core runtime package versions. The historical
entries did not pin that environment, so differences from them must not be attributed
solely to new downloads: code corrections and runtime changes may also contribute.

The SIC field in bulk entity metadata is the **current** classification. It has no
historical knowledge timestamp here. H4 and neutralized H0 use it as a fixed proxy;
the formation-time tests do not establish that it was the classification known
at each historical filing. Those estimates remain conditional development
diagnostics, not clean historical-industry-adjusted confirmatory tests. Resolve
that source/proxy contract before opening applicable holdouts.

Development runners append a ledger entry even if execution raises after an
evaluation starts. `execution_status` describes execution, not scientific validity;
in particular, a completed H6(b) diagnostic remains invalid under F2. Partial
metrics and the failing phase are retained where available; exceptions still
propagate and the run must not be presented as complete.

After rebuilding inputs, run `python scripts/benchmark_h0.py --firms 100` before
the full backtest. It checks numerical equivalence to the pinned handoff revision
on the same corrected shares (D7) and complete-return engineering subsample (D8),
logs the engineering configurations, and writes
`results/h0_optimization_equivalence.json`. Its timings cover the subsample
comparison only. The full backtest's `elapsed_seconds` includes loading and shared
preparation inside `main`, but excludes imports. The 180-second acceptance uses an
external process Stopwatch, including startup; its observations are in the ledger.
Neither benchmark success nor historical CI proves scientific acceptance.
The formation-time repair and the legacy filing-cohort comparison are deliberately
separate: the latter is not an event-time signal and is not used for production
neutralized portfolios. Production reports the 0%, -30%, and -100% missing-return
assumptions and missing-observation counts; these do not repair the missing-firm
selection documented in F2.

Profiling the rebuilt 2,753-ticker price cache found another preparation bottleneck:
the per-window spread loop took 63.0 seconds for 57,195 ticker-months, in addition
to 74.7 seconds loading prices. Spread aggregation is now batched with the same
adjacent-valid-quote formula and minimum of three quotes. An independent real-data
100-ticker comparison (2,069 ticker-months) matched the legacy window calculation
to `rtol=atol=1e-12` and reduced that aggregation from 2.43 seconds to 0.032 seconds.
These are component timings during acquisition, not an end-to-end performance claim.
The benchmark CLI repeats a pinned legacy monthly-panel comparison on its selected
firms and records that evidence separately.

The recorded 100-firm check passed for all four variants across 17 formation
months, including holdings, quintiles, weights, gross returns, and turnover costs.
Its separate monthly-panel check covered 2,091 ticker-months. See
[`results/h0_optimization_equivalence.json`](../results/h0_optimization_equivalence.json)
for the clean code revision, input hashes, environment, timings, and exact comparison
scope. It is an engineering check, not a financial finding.

The loader also handles a listing with no pre-cutoff quotes but later split events:
it returns an empty guarded history, rather than crashing on an empty NumPy index.
The rebuild produced 2,753 cache files and 2,733 nonempty daily histories; cache-file
count alone is not price coverage.

### Processed price snapshot and runtime contract

The first full four-variant run produced plausible development estimates but took
298.7 seconds wall-clock (267.5 seconds inside `main`), missing the 180-second
target. Its failed timing acceptance is retained as an `ENGINEERING` ledger entry.
Profiling shared preparation, without re-evaluating strategies, found repeated
vendor JSON decoding and daily DataFrame construction dominated the remaining cost.

The `prices` stage now also builds a lossless processed snapshot. For existing raw
caches, rebuild just that step with `python scripts/h0_data.py price_snapshot`.
It writes three **local-only** files under `data/`: `h0_monthly_prices.parquet`,
`h0_daily_returns.parquet`, and `h0_price_snapshot.json`. No raw or processed prices
are committed or redistributed.

- The manifest pins raw-cache SHA-256 fingerprints, universe selection, processing
  source hashes, cutoff, runtime versions, output checksums, and generation lineage.
- Generation must see unchanged inputs from start to finish. The full monthly
  panel and every daily series, including empty series and exclusion counts, are
  compared with their serialized round-trip before the manifest is published.
- The analysis refuses missing, stale, corrupt, or post-cutoff snapshots. It does
  not silently fall back to raw decoding. Rebuild after changing raw data,
  universe, processing code, or runtime; finish acquisition before generating it.
- The snapshot preserves values and missingness. It adds no sample, return,
  cost, or hypothesis change. Full process timing must include validation and
  loading of this prepared input; acquisition and snapshot construction are
  separately identified data-preparation steps.

The accepted full process took **61.073 seconds wall-clock**, including startup,
all four monthly variants, all three missing-return assumptions each, and raw
descriptive event panels. Time inside `main` was 54.766 seconds. Every numeric
metric in all 12 configurations exactly matched raw preparation (maximum
difference 0). Snapshot generation separately took **154.955 seconds**, with
57,195 monthly rows and 2,733 daily series / 14,433,060 returns round-tripped exactly.
These are local observations with prepared, validated inputs, not portable
hardware guarantees or timings for unexecuted neutralized event panels.

An exhaustive daily-return audit subsequently found a remaining F3 gap, now tracked
as [F6](FINDINGS.md#f6-the-f3-price-return-guard-did-not-cover-daily-event-inputs)
and [D9](DEVIATIONS.md#d9-apply-the-existing-price-return-integrity-guard-to-event-inputs).
Daily event loaders had bypassed the monthly return guard. Both frequencies now
log and exclude unusable vendor price ratios, and the fresh H0 output reports the
daily count. This does not independently validate the vendor's adjusted series.

### Validation tooling scope

Default `ruff check` under Ruff 0.17.4 reports 62 inherited findings, compared with
63 on the pinned handoff source. A per-file/rule/message comparison found no new
findings after cleanup of task-introduced diagnostics. The selected
`E4,E7,E9,F` checks pass; the full default lint is **not** reported as passing.
Unrelated baseline style issues are left unchanged.

## Coverage among public-equity issuers, by public float

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

Issuer counts per bucket range from about 1,000 to 2,700 per year.

## Implications

- The pre-registered development period (2011–2018) would lose 30–45% of large issuers with free data. The missing firms aren't random: they include acquisition targets, which tend to earn takeover premiums, and failures, which tend to earn large losses. **The direction of the bias is unknown**, so delisting-return sensitivity bounds can't fully repair it.
- Validation (2019–2021) and holdout (2022–2026) coverage is higher but still incomplete before 2024.
- **Decision:** the original decision was to wait for a survivorship-free source. It was superseded by deviation D1: return tests run only on signals from 2023 onward, where coverage of large issuers is 88–97%, with delisting sensitivities. See `docs/DEVIATIONS.md`.

## Holdout hygiene disclosure

On 2026-11-12, before the price guard existed, AAPL's full daily price history was downloaded once to validate split handling. That file contained post-2024 prices. It was used only to confirm the as-traded close on 2014-06-06 and on 2020-08-28, then deleted. No returns were computed from it.

From then on, `asof.periods.price_end_allowed` refuses analysis price access past
2024-07-31 unless the holdout is explicitly opened. July 2024 remains visible for
June development formations' return tail. That overlaps some nominal July
holdout-event labels and must be audited before calling those event windows untouched.

## Price-request change (F3)

Yahoo adjusts *all* historical prices for every split up to today. A request that stopped at the development cutoff therefore returned prices already adjusted for later splits, but not the later split *events*. That made as-traded price reconstruction impossible for stocks that split afterward; for example, FFAI showed $1,200 when it traded at pennies.

From 2026-11-13, each request spans the full history. **Every quote and dividend after the cutoff is discarded in memory before caching**, and only split events (date and ratio) are kept. Those later split events are used solely to reverse the vendor's own adjustment. No post-cutoff price, return, or dividend is stored or used.

The devbox rebuild also exposed a metadata gap in that implementation:
Yahoo's `meta` object can contain a current price and current 52-week range even
when the quote arrays are truncated. The strip function now retains only
`exchangeTimezoneName` from metadata, which is all date reconstruction requires.
This correction was made before price acquisition began on this devbox. Historical
cache hygiene is not established by this fix; old price caches should be rebuilt
with the corrected code. No metadata price is used to calculate returns.

## Data rebuild runbook

Use the project Python 3.12 environment and required SEC contact user agent from the README.
Run stages one at a time and stop on a nonzero exit or unexplained feature errors.
Do not run two SEC download pools simultaneously: their rate limiters are per process.
Large companyfacts work must use `iter_companyfacts`, not a dictionary of all firms.
The benchmark and referee chronology checks require the pinned historical commit
and preregistration tags, so use a full clone or explicitly fetch that history.
Do not commit package-mirror URLs or a mirror-derived lockfile.

From the repository root in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\bulk_download.py
.\.venv\Scripts\python.exe scripts\h4_fundamentals.py bulk sample
.\.venv\Scripts\python.exe scripts\master_index.py
cmd /d /c '".venv\Scripts\python.exe" scripts\h0_data.py universe filings features pairs shares prices < NUL > data\h0_rebuild.log 2>&1'
cmd /d /c '".venv\Scripts\python.exe" scripts\h4_fundamentals.py features pairs outcomes < NUL > data\h4_rebuild.log 2>&1'
```

`NUL` supplies Windows process pools with a valid stdin; a closed pipe can break
`ProcessPoolExecutor`. The `prices` stage creates the processed snapshot automatically.
If only processing code/runtime changed, run `scripts\h0_data.py price_snapshot` with
the project interpreter instead of downloading again. Missing/stale/corrupt snapshot
errors are a stop condition, not permission to bypass its validation.

The rebuilt data has 48,452 entities, 3,190,805 filtered bulk filings, a 1,500-CIK H4
sample, 21,502 H0 signal pairs, 10,581 H4 pairs, and 19,493 H4 outcome filings.
H0 features covered 32,508 filings; H4 requested 12,184 (10,806 uncached), with zero
feature errors in either build. Fresh downloads or dependency upgrades may change
counts and fingerprints; do not silently reuse a different snapshot or rewrite old trials.

### Referee pilot fixture

The full referee also needs `data/pilot.duckdb`; it is not supplied by Git or created
by the H0/H4 stages. The executed fixture used these five public issuers' CIKs,
streamed from the same local bulk archives. Run this Python block **once** with the
project interpreter after bulk download:

```python
from asof import store
from asof.bulk import iter_companyfacts, iter_submissions
from asof.config import DATA_DIR

ciks = {320193, 1018724, 1652044, 1045810, 200406}
path = DATA_DIR / "pilot.duckdb"
if path.exists():
    raise FileExistsError("Do not re-ingest over an existing pilot fixture")
con = store.connect(str(path))
try:
    for cik, rows in iter_submissions(ciks):
        store.ingest_submissions(con, rows)
    for cik, facts in iter_companyfacts(ciks):
        store.ingest_facts(con, store.flatten_companyfacts(facts))
    print(con.execute(
        "SELECT knowledge_time_source, COUNT(*) AS facts "
        "FROM xbrl_facts GROUP BY 1").df().to_dict("records"))
finally:
    con.close()
```

The executed fixture had 132,527 facts, all sourced to exact acceptance times.
It is a new verification fixture, not the original handoff pilot. Do not repeatedly
append facts to an existing fixture. Inspect it with the referee, or explicitly
preserve it and rebuild a separately named database if recovery is needed.

### Development execution and output contract

After inspecting rebuild logs and creating the pilot:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_h0.py --firms 100
.\.venv\Scripts\python.exe scripts\h0_backtest.py
.\.venv\Scripts\python.exe scripts\h4_fundamentals.py test
.\.venv\Scripts\python.exe scripts\h6_quiet.py
.\.venv\Scripts\python.exe -m asof.referee
```

Keep evaluation runners sequential so there is one trial-ledger writer. Never edit,
truncate, or remove failed ledger rows. Synthetic holdout-seal tests use temporary
ledgers; they are not project holdout openings.

- **H0:** formation signals accepted 2023-01-01 through 2024-06-30 UTC, returns
  through 2024-07-31 only. Long high similarity / negative residual change is the
  registered low-change leg. Price >= $5, NYSE p20 size cutoff, value weights,
  five quantiles, maximum signal age 365 days. Shares are known at or before
  formation; signals and acquisition events must be strictly earlier. Neutralization
  uses log market cap and an acquisition indicator in the preceding 365 days, with
  the current-SIC proxy. Missing held-leg returns and declared assumptions are reported.
- **H4:** 10-K acceptance window 2012-01-01 through 2018-12-31 23:59:59 UTC.
  Income/assets are matched to regular 10-K accession and fiscal end; next-report
  links require a 300-430-day fiscal-end gap. The code neutralizes by acceptance-year
  cohort with SIC2 and log assets, then uses industry/year effects, log assets, ROA
  and sales growth with firm/year clustered inference. That cohort transformation
  is retrospective, not claimed observable at each filing time. Missing impairment
  tags are treated as zero in the existing label definition, not certified absence.
  D6 fits 1%/99% ratio cutoffs only on development rows. Seven year clusters and
  current-SIC assumptions limit interpretation; F4's historical isolation is not restored.
- **H6(a):** the same 2012-2018 acceptance window, per-filing counting, year effects
  and firm-clustered inference. D5 fixes NI-only, a >1% downward revision and >$1M
  original magnitude, prior-120-day exclusions and mechanical-scale exclusions.
  The broad outcome is a qualifying record in available metadata within 365 days;
  no record is not proof of no real-world event. 4.02-only rates are descriptive.
- **Event panels:** CARs use FF5+UMD with an estimation range -260..-21 and horizon
  +1..+60 under the prototype's valid-observation indexing. The session helper uses
  fixed 16:00 ET closes. Calendar gaps and early closes are not certified by the
  existing invariance tests; qualify that contract before confirmatory/tradable claims.
  Raw panels are descriptive; neutralized panels are not evaluated under D8;
  H6(b) remains invalid under F2 even when its diagnostic completes.
  Complete event windows must end by 2024-07-31, so late development events can be
  omitted rather than completed with sealed prices; inspect event and cluster counts,
  not just the headline signal-date range.

Current outputs are
[`returns_h0_development.json`](../results/returns_h0_development.json),
[`h4_development.json`](../results/h4_development.json),
[`h6_development.json`](../results/h6_development.json), and
[`REFEREE.md`](../results/REFEREE.md). H0 has exactly four variant objects; `monthly`
is the 0% primary, `monthly_missing_return_sensitivity` contains all three assumptions,
and `event_panel_change_on_car60` distinguishes numeric raw diagnostics from
`not_evaluated` status. Ledger `m_`/`e_` metrics distinguish monthly/event quantities.
Coefficients and returns are in native ratio units; multiply return ratios by 100
for percent, and probability coefficients by 100 for percentage points. A one-unit
cosine-change coefficient is not a one-percentage-point score change.

No positive result is manufactured for empty or unsupported samples. Inspect counts,
notes, warnings, execution status and applicable scientific-invalid status; the referee
rejects incomplete or non-finite H0 reports. Do not interpret a completed run or
technical gate pass as scientific acceptance.

## Approval-only next steps and timing

No market-data API key was used and no additional paid service was provisioned or
purchased; computation used the existing environment. A proposed
[Tiingo EOD](https://www.tiingo.com/documentation/end-of-day) pilot first needs owner
approval and confirmation of current licensing, quota, dead-security history and
terminal-payoff support. Start from the historical issuer population, not today's
tickers. Qualify CIK/security/date mappings, share classes, ticker reuse, corporate
actions, missing/delisting treatment, and development-only golden cases before
re-running F2 contrasts. The existing relative-coverage floor of 0.8 is a diagnostic
minimum, not sufficient proof of survivorship-free data. Do not lift F2 just because
one vendor returns more tickers.

Before any applicable holdout: resolve source/industry assumptions, early-close
and calendar-gap contracts, event-time neutralization, outstanding registered
inference/multiple-testing outputs and F4 contamination; review every trial; then
freeze/tag code, configuration, source pins, exact windows, support gates and recovery
policy. Owner approval is a separate gate. A new prospective H4 period may need
registration; do not silently change the original split or call it pristine.

For return tests, the nominal last signal date remains 2026-10-31. The October
monthly formation requires the 2026-11-30 close. Using the
[official scheduled NYSE calendar](https://www.nyse.com/trade/hours-calendars),
a late-October event's first close on 2026-11-02 has its +60th scheduled session
on 2027-01-29: the intervening full closures are 2026-11-26, 2026-12-25,
2027-01-01 and 2027-01-18. Early-close dates still count as sessions.
This is a public-calendar calculation, not access to held-out price outcomes.
Recalculate for actual closures and finalized data; valid-observation windows with
gaps could extend later until that contract is fixed. An early-February-2027 review
is a proposal, not an automatic opening date. H4 and H6(a) have separate label-maturity
and isolation decisions, and July 2024 event-label overlap with the visible development
tail must be resolved explicitly.
