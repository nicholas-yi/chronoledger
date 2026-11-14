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
[Tiingo EOD](https://www.tiingo.com/documentation/end-of-day) pilot was a historical
suggestion, not an approved source. The [current rights reconciliation](#current-source-rights-reconciliation-2026-11-13)
now blocks the assumption that a free account can support a durable reproducible
pilot, including its derived artifacts. Owner approval is necessary but cannot
waive vendor rights; purchase is not a substitute for public-project permission.
Any future pilot needs both applicable rights and scoped owner approval, plus
confirmed quota, dead-security history and terminal-payoff support. Start from the historical issuer population, not today's
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

## Bounded gate advancement (2026-11-13)

Chronology note: the original bounded review and later rights review below retain
their own validation/scope history. Current release status is the **v0.2 queue**
and **Lead-D3a synthetic planner** subsection; those supersede earlier "pending
cards" or design-only timing statuses, not historical results or permissions.

**Status: local, uncommitted contract work and synthetic validation only.**
The prior completed execution checkpoint remains `97b36c5`, with the study/snapshot
source and final referee source already recorded above. The existing Execution
chat is the sole default code/data/run writer. The Lead's "do all three" activation
authorizes this bounded advancement, **not** key use, acquisition, paid services,
held-out outcomes, publication, a commit, or an empirical rerun.

No original study or acquisition job was active at the start of this turn.
No backtest, model, referee, full test suite, raw/processed dataset inspection, bulk
fingerprint scan, new empirical trial, or vendor pilot was run. Existing result
numbers and the 123-test/technical-referee checkpoint elsewhere are inherited
evidence; they were not re-established for this dirty worktree.

### Six-package dependency queue

**Staged programme, not permission to execute blocked operations.** This queue
records the user's 2026-11-13 17:53 ET activation. Execution remains the only
default repo/data/run writer; Research supplies read-only design cards, Lead
reconciles design choices, and the owner retains reserved permissions. No new
queue service, chat, agent or planning file is created.

**Queue snapshot v0.3 (Batch A offline release); stable IDs CL-P1 through CL-P6.** Lead decision
**Lead-D1** accepts this organization only. These `Lead-D*` identifiers are
coordination decisions, **not** pre-registration deviations D1-D9 or new tags.
Research's **CL-P1 through CL-P6 decision-ready design cards v1**, completed
response `a8dca7e0-bccd-493d-89b9-2aefef5b5705`, have now been read in all four
pages by Execution; Lead reports full design review of those cards and the P2 map.
This is design review, not independent source revalidation, acceptance of every
scientific alternative, an empirical run release, or provider clearance.
The owner's explicit `timing_scope='separate-synthetic-planner'` decision releases
**only Lead-D3a's opt-in synthetic implementation** documented below.

Stages refer to the named deliverable: `design` = unresolved specification;
`ready` = reviewable artifact with stated prerequisites, not run permission;
`blocked` = named execution gate unmet; `completed` = evidenced work actually
finished, not an accepted proposal. The v1 card readiness claims remain
attributed to Research, not independent scientific validation. Lead-D3a is
implemented and synthetically verified; historical-runner integration and every
empirical operation remain blocked. No package is empirically run-ready.

| Package / owner | Concrete deliverable and stage | Dependencies | Validation / acceptance evidence needed | Exact blockers and next executable action |
|---|---|---|---|---|
| **CL-P1 / P1: rights, identity, payoffs.** Research design; Lead review; owner rights/access; Execution any later pilot. | `ready` **as reported** for substantive design; rights/access `blocked`: provider/channel/retention/disclosure contract, historical denominator, dated issue/class mapping and terminal-payoff protocol. | Design independent of P2/P3; actual source pilot requires accepted P1 plus explicit scoped key/rights/budget/cutoff and resource permission. | Rights support required artifacts and review; date-valid identity/action oracles, explicit unknown terminal values; any future pilot meets its prespecified case gates. Population F2 diagnostic is separate and insufficient alone. | No compatible public-project rights, recipient/inquiry approval, key/access permission or AfterEvidence arbitration. **Next:** reconcile final P1 card with current-rights section and decide Lead-D2; no vendor contact/API. |
| **CL-P2 / P2: point-in-time contract.** Execution implementation; Lead/owner resolve remaining alternatives. | **Lead-D3a `completed`: opt-in synthetic planner only.** Research interface card v1 / Execution contract v0.2. [Planner and focused validation](#lead-d3a-opt-in-synthetic-planner-v02) verified; historical-runner integration `blocked`. | This synthetic implementation had its own explicit owner release. Any empirical application still needs accepted applicable P2/P1/P3/P6 and separate scope/resources; neutralization/overlap are not released. | Strict UTC/ready/deadline, supplied early close/DST, fixed post-entry/estimation slots, missing/censored support and legacy separation tested. No fit or fill claim. | Lead-D3b/rest of D3 and D6 remain open. **Next:** Lead reviews verified planner evidence; no further timing/control/overlap defaults or runner integration without authorization. |
| **CL-P3 / P3: inference, power, trials.** Research design; Lead statistical review; Execution any authorized null checks. | `ready` **as reported** for inference/power/trial design; empirical inference `blocked`: estimand, dependence/family map, multiplicity interface and aligned-return requirements. | Design independent of P1/P2. Actual synthetic null checks require accepted P3 and finite CPU budget; heavy work also needs verified arbitration. Empirical inference needs qualified inputs/P2 and separate authorization. | Prespecified calibration/power targets, simulation precision/stop rules, dependence assumptions and transparent repeats/engineering/invalid-trial accounting. Few periods cannot be repaired by procedure selection. | Lead-D4/D5 multiplicity/effect/tail/null choices and CPU budget unresolved. **Next:** reconcile final P3 card and taxonomy on paper; no project DSR/PBO, simulation or trial append. |
| **CL-P4 / P4: blinded measurement and endpoints.** Research protocol; Lead review; owner human-time/protocol approval; Execution permitted selection/provenance. | `ready` **as reported** for proposed60-pair claims audit and **separate20-case endpoint feasibility** protocol; human/observation-envelope work `blocked`. | Design can advance alongside P1/P2/P3/P6. Actual gold work requires accepted P4, allowed metadata/text, frozen metadata-only selection and separately approved human protocol/time; vendor use also needs P1. | Traceable spans/accessions/periods/entities, no future-outcome disclosure, independent labels/adjudication and error/selection accounting. Endpoint follow-up/observability is separate from claim accuracy; neither supplies an alpha result. | Lead-D6/D7 observation/amendment definitions and human-time approval unresolved. **Next:** reconcile final protocols and blinding/envelope decisions before any actual roster, annotator contact or labeling. |
| **CL-P5 / P5: baselines, formal H1, network, uncertainty.** Research design; Lead prioritization; Execution sole implementation/evaluation writer. | `ready` **as reported** for registry/DAG; outcome studies `blocked`: cheap baselines, original formal H1, separately specified extensions/network/uncertainty branches. | Every outcome study needs applicable qualified sources/P1, accepted P2 + P3, validated P4 measurement where applicable, P6 economic gate, prospective specification and explicit run/resource authorization. Network additionally needs gold dated links and both-ended identities; uncertainty needs sufficient independently authorized calibration. | Same samples/windows/costs, locked baselines/incremental target, D3 where applicable, independent calibration and reported abstention mass. Formal H1 retains its original protocol. | Dependencies and Lead-D8 study/margin decisions unmet; no H1/graph/uncertainty result assumed. **Next:** reconcile final registry into original H1 versus proposed new study IDs; no evaluation or new scoring. |
| **CL-P6 / P6: economic implementability.** Research design; Lead review; owner capital/rights decisions; Execution any later checks. | `ready` **as reported** for economic specification; cost/shortability claims `blocked`: auction/exposure/turnover, spread versus impact/fees/borrow/financing, halt and terminal-action contract. | Design can advance in parallel with P4 and P1/P2/P3. Actual calculations need accepted assumptions and authorized source/resource scope. P5 outcome claims depend on applicable P6 gate. | Separate observed inputs from assumptions; prespecified capital/participation and cost stress/break-even targets; no executable long-short claim without historical shortability/fill evidence. | Lead-D9 cost/borrow/size choices and source rights unresolved; spread proxy is not all-in cost. **Next:** reconcile final P6 card with P2-X and list unsupported inputs; no broker/data call. |

**Operational DAG (all empirical operations remain queued `blocked`, not started):**
P1 pilot <- accepted P1 + compatible rights + scoped owner key/budget/cutoff approval;
P2 empirical clock/runner integration <- remaining accepted P2 choices + separate
assignment (Lead-D3a pure synthetic planner is completed, not this integration);
P3 null checks <- accepted P3 + finite CPU budget;
P4 gold work <- accepted P4 + approved metadata-only selection/human protocol;
P6 economic checks <- accepted P6 + applicable source rights/execution evidence;
P5 outcome studies <- applicable qualified sources + P2 + P3 + measurement + P6,
plus prospective specification and explicit empirical run/resource authorization.
Network and uncertainty retain the extra P5 prerequisites above. Independent
design roots are P1, P2 and P3; P4 and P6 design need not wait for them.
No blocked operation is silently dropped or considered approved by being queued.

**Resource and scope gate common to all operations:** AfterEvidence's exact route
and arbitration remain unverified; heavy CPU/data/model/API work is blocked.
Source rights cannot be supplied by user consent. Annotation/human work, keys,
spending, any holdout access and publication require their own permission.
Price <= 2024-07-31, frozen signal splits/scoring/hypotheses, F2/F4/F6/current-SIC
and July-2024 overlap remain binding. November 30 / January 29 are conditional
maturity milestones, not permission. No hourly scheduling exists; no monitors
or new chats are part of this queue.

**Research integration:** Execution read the entire completed original dossier
response `9b2a1459-1102-418b-8bf3-cc13b09688db` in the
[existing Research chat](agent-host-session://ahp-session/951260e2-fb65-4741-bc73-7ba69cbfc778?chat=8b3fbed7-849c-4ebb-8c14-aa755f6b3045).
Its source/rights, few-cluster, measurement, baseline and economic prerequisites
inform this queue; its illustrative power and proposed numerical gates are not
new project results or accepted thresholds. The completed **design cards v1**
response `a8dca7e0-bccd-493d-89b9-2aefef5b5705` was subsequently read fully for
v0.2, including CL-P1/3/4/5/6. Lead's full design review does not release source
rights, scientific alternatives, human time or empirical operations.
CL-P5 v1's subregistry remains proposed: CL-P5-B0 cheap baselines, CL-P5-H1 original
formal H1, CL-P5-X1 new extension, CL-P5-G1 dated network and CL-P5-U1 uncertainty.
Their dependencies and gates above persist. Prep is not activated.

**Historical receipt versus current review:** in the v0.1 turn the final cards
were still streaming and only the handoff was available. In this v0.2 turn the
named completed response was paginated once; no Research/Prep wakeup or polling
was needed. Proposed resource ceilings below remain proposals, not budgets.

| Reported proposed ceiling | Status and independent release gate |
|---|---|
| CL-P1:24 cases / six strata / <=40 securities / <=150 requests / <=50 MiB | Proposed envelope only; not a roster, entitlement or rights clearance. Actual access requires compatible rights, explicit scoped owner permission and verified resource coordination. |
| CL-P3: <=2,000 future synthetic replicates / <=15 CPU minutes / <=1 GiB RAM | Proposed caps, **not an approved budget** or null allocation. Lead-D4/D5, bounded resource approval and arbitration where needed precede any simulation. |
| CL-P4: proposed60-pair claims audit; separate20-case endpoint feasibility; <=30 claims-person-hours + <=12 endpoint-person-hours | Proposed sizes/time caps, **not human authorization**. Lead-D6/D7 observation evidence, blinding/selection, annotators and approved human time remain separate. Do not mix the endpoint sample with claim pairs or score them as a completed gold set. |

**Accepted accounting/representation invariants, not new empirical rules:**
preserve the registered distinct-configuration N and every original, invalid and
failed trial. Add transparent engineering/repeat-vintage/scientific classification
only without hidden exclusions or substitutions through an "effective N".
The registered v2 >=3.2 threshold is **not automatically an exact Holm p-value
algorithm**; its implementation interface remains open. `H1n` is not formal H1.
Unknown observations are proposed audit-schema null + reason/censored states,
not authorization to relabel empirical outcomes. Preserve the frozen
missing-impairment policy and disclose the 10-Q/A discrepancy until decided.

| Lead decision ID | Status / next decision (separate from numbered preregistration deviations) |
|---|---|
| **Lead-D1** | Accepted **queue organization only**: stable CL-P IDs, versioned designs, readiness versus decision-blocked state and proposed ceilings. No operational gate released. |
| **Lead-D2** | Open: source-rights inquiry wording and exact recipient approval, before contact. |
| **Lead-D3a** | Explicit owner selection `separate-synthetic-planner`; implemented and synthetically verified **only** for the separate opt-in API below. No legacy defaults or empirical runner changed. |
| **Lead-D3b / rest of D3** | Open: empirical timing integration/availability evidence, actual execution/auction feasibility, overlap/dedup, SIC and filing-time neutralization choices. D6 label/observation decisions remain separate. |
| **Lead-D4** | Open: exact multiplicity interfaces without rewriting the registered threshold/N. |
| **Lead-D5** | Open: economic effect sizes, tails, power and null allocation; proposed compute caps are not permission. |
| **Lead-D6** | Open: observation-completeness evidence, censoring and amendment/endpoint definitions. |
| **Lead-D7** | Open: human protocol and claims/endpoint annotation time. |
| **Lead-D8** | Open: study registry and incremental margins before outcome evaluations. |
| **Lead-D9** | Open: costs, historical borrow/shortability and capital/size contract. |

#### Batch A prospective decisions and bounded release

The 2026-11-13 Batch A instruction supersedes the earlier open-status entries
only as specified here. These are **Lead coordination/design decisions**, not
renumbered preregistration deviations. Frozen studies and their recorded
interpretations remain unchanged. Offline helpers below are pending implementation
and validation until the completion record is filled; queued is not empirical-ready.

| Decision | Prospective resolution / retained stop |
|---|---|
| Lead-D3b | Future overlap uses20 scheduled-session distance from last **kept** event, merging iff distance<20. Exactly20 retained; no transitive chaining. Longer outcome overlap belongs to inference, not dedup horizon. Historical calendar approximation unchanged. |
| Lead-D3c | Future focal filing scored out-of-fit against **other firms'** latest eligible signals strictly before focal time, age<=365days; controls strictly known before then: dated SIC2, log size at last prior close, prior365day Item2.01. Equal-time fit observations excluded. Minimum support is a required registration input, no default. No neutralized event evaluation without registration and dated SIC. |
| Lead-D3d | Future unknown dated SIC means no neutralized score/abstain; retain raw and report counts. Current SIC remains conditional historical proxy. Source/rights gate persists. |
| Lead-D4 | A future success decision is the conjunction of v1 sign/threshold/all3 delisting assumptions/referee and literal v2 co-primary expected-direction >=3.2, other same sign and applicable D3 agreement. No weaker H0 route. One-sided registered-direction normal-reference Holm outputs are supplementary/non-decisive. Preserve registered distinct-config N and all trials. DSR/PBO require persisted aligned comparable series; PBO16 requires>=32aligned months, otherwise not_estimable. Historical functions/results not overwritten. |
| Lead-D5 | Each future study still fixes its actual economic effect at registration. Only the exact synthetic allocation/budget below is now released; no empirical power or dataset extension. |
| Lead-D6 | Future evidence labels: verified positives may precede full follow-up; negatives require complete observation evidence. Missing impairment tag unknown unless explicit-zero/complete-statement evidence. Administrative/substantive amendments distinct; future quiet construct excludes10-K/A and10-Q/A. Frozen H4/H6 labels unchanged; historical10-Q/A wording discrepancy disclosed as deviationD10 after results. |
| Lead-D8 | B0 measurement/no returns -> original formal H1 readiness -> X1 -> G1 -> U1. Fix margins/estimators at registration; all relevant source/time/measurement/economic gates still apply. |
| Lead-D9 | Frozen costs unchanged. Future component ledger, break-even one-way cost and prespecified long-only contrast; no executable long-short conclusion without historical borrow/fill evidence. |
| Lead-D2 / D7 | Still owner-only: vendor inquiry wording/recipient and human annotation scope/time. Draft questions are not sent; no recruitment or access. |

**Released offline Batch A deliverables:** supplementary read-only trial classifier
and decision/availability helpers (A1); future label-evidence validator (A2);
component-cost/turnover helper (A3); data-free study readiness registry (A4);
bounded synthetic calibration (A5). No empirical configuration/trial row,
vendor/human contact, key/account, spend, publication, push or tag is released.
Local commits may be made only after focused validation, with the required trailer.
The existing seven-file patch and synthetic planner are preserved.

##### Synthetic calibration specification recorded before execution

**SYNTHETIC ONLY; not project inference or ledger trials.** Seed **2026111322**.
Fourteen ordered case streams use `SeedSequence(seed).spawn(14)` in the order
below; no replacement draws for invalid estimates and no allocation changes after
outcomes. Maximum2,000 replicates,15CPUminutes,1GiB process resident memory,
one numerical thread; stop at the first observed ceiling and persist incomplete
counts/reason. No automatic budget expansion or empirical-data fitting.

| Case order / allocation | Fixed synthetic generating process |
|---|---|
| Monthly null: DGP order iid normal, AR(1)phi0.3, variance-scaled t3, common-factor exposure; each T18 then T28;150 per cell =1,200 | Six iid factor regressors N(0,0.02²). Idiosyncratic monthly SD0.03. iid error N(0,1); stationary AR initial N(0,1), innovations scaled sqrt(1-0.3²); t3 divided by sqrt3. Common-factor case adds factors dot(0.8,0.4,-0.2,0.3,0.1,0.2). All true alphas zero. |
| Monthly power: T18 then T28, each effect0.5 then1.0 SD;100 per cell =400 | iid normal errors SD0.03, true alpha effect*0.03, zero factor slopes; six nuisance factors as above. These effects are synthetic design scales, not accepted economic targets. |
| Panel null: no year shock then year-common-shock;200 per cell =400 |40firms x7years, one annual row each. Independent standard-Gaussian focal regressor and3controls with coefficients(0.2,-0.1,0.3); industry=firm modulo4, true industry effects zero. Standard-Gaussian firm component and idiosyncratic error. Common-shock case adds (0.6+0.3*standard-Gaussian firm_loading)*standard-Gaussian year shock. Include industry/year effects, matching H4-style control/FE and firm/year two-way cluster geometry; focal coefficient zero. Year effects absorb the homogeneous shock component, not heterogeneous loadings. |

Monthly estimation uses the existing `nw_alpha` (intercept+six factors, HAC6).
Panel uses the same statsmodels OLS plus industry/year dummies and firm/year
two-way clustered covariance construction as the H4 runner, without importing
or running that runner. For |t|>=2.0/3.0/3.2 report valid-sample rejection rates,
normal-reference two-sided nominal tail, Monte Carlo SE and invalid/warning counts.
Invalid/non-finite estimates are not counted as non-rejections or redrawn.
Power is a rejection frequency, not a project-effectiveness claim. Retain all
case outcomes, including poor calibration, with environment and resource usage.
The output is `results/synthetic_inference_calibration.json`; no project ledger
row is written.

Machine check before implementation:16logical CPUs, reported25%CPU load,
about39.9GiB free physical memory, no matching active Python research job.
Recheck before calibration; defer if competing heavy work appears. This exact
light offline release does not establish a general AfterEvidence route or lift
the heavy/API/model gate.

##### Batch A helper interfaces and verification

| Released helper | Exact offline behavior / boundary |
|---|---|
| [trial_manifest.py](../src/asof/trial_manifest.py): `build_manifest`, module CLI | Pure classifier preserves every ledger attempt and unchanged distinct-config N per hypothesis. Scientific/repeat_vintage/engineering/timing/unknown classes are supplementary; missing/failed/explicit invalid output status is retained, no matrix invented from summaries. CLI reads the existing ledger, never writes it, and creates only `results/trial_manifest.json` with generation lineage and unavailable project inference. Unknown purpose stays unknown; a recognized legacy hypothesis without an explicit purpose is classified with that inference disclosed. |
| Same module: `co_primary_decision`, `inference_availability` | Future supplied evidence only; D4 conjunction, expected-negative increasing-change event statistic and positive monthly/scenario/TF-IDF orientation explicit. All3 scenario effects required; formal H1 cannot waive D3 or accept H1n alias. Normal one-sided Holm values supplementary, not decisive. DSR/PBO availability requires declared persisted, complete, comparable aligned nondegenerate monthly series; PBO16 with<32months is not_estimable. No DSR/PBO estimate or historical success decision computed. |
| [labels.py](../src/asof/labels.py): `LabelEvidence`, `validate_label` | Validates declared evidence/status, not underlying documents. Positive needs references and verified positive; formal endpoint checks aware signal/event times in(signal,signal+365d]. Negative needs complete observation, and formal negative also a mature observed envelope plus follow-up evidence. Missing impairment needs zero/complete-statement evidence for a negative. Unknown/censored is null+reason. No real label or frozen H4/H6 policy changed. |
| [costs.py](../src/asof/costs.py): `component_costs` | Explicit common capital/cost currency; return costs are fractions of capital. `one_way` turnover is half L1/gross traded fraction; spread cost2*halfspread*T equals halfspread*L1. Spread charged once; fee/impact bps per absolute traded notional, already-accrued signed holding bps per capital/period. No inferred annualization/FX. Break-even is all-in one-way execution bps after holding costs, not another cost. Unknown borrow/fills/components return unavailable, not zero totals. Caller flags do not verify historical feasibility. |
| [studies.py](../src/asof/studies.py): `STUDIES`, `study_readiness` | B0 -> formal-H1 readiness -> X1 -> G1 -> U1, with explicit prerequisite statuses and gates. A blocked/missing prerequisite cannot yield ready; H1n is not formal H1. B0 is measurement/no outcomes. Gold/two-ended identity and independent-calibration gates are additional. Pure gate checks do not launch jobs or grant real permission. |
| [calibrate_inference.py](../scripts/calibrate_inference.py) | Runs only the fixed seed/allocation above, with pre/post-fit CPU and OS peak resident-memory checks and no data loaders. Nonfinite/numerical outcomes and warnings are retained; no redraw or favorable subset claim. First resource ceiling stops the run and preserves incomplete status. Not project DSR/PBO, not a ledger evaluation, and no market-data access. |

Focused validation before evidence generation:

```powershell
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
.\.venv\Scripts\python.exe -m pytest -q tests\test_trial_manifest.py tests\test_labels.py tests\test_costs.py tests\test_studies.py tests\test_inference.py tests\test_h4_development.py tests\test_events.py tests\test_timing.py tests\test_timeutil.py tests\test_backtest.py::test_long_short_signs_and_costs
```

Initial result: **73 passed**; after tightening formal365day timestamp/envelope
validation, the same focused command passed **76 tests**. Configured Ruff on the
nine new Batch A source/test files and selected `E4,E7,E9,F` on all15 changed Python
files passed. The OS peak-resident-memory guard probe returned17,752,064bytes
before scientific-library loading, verifying a nonzero process-memory reading;
actual calibration peak is measured separately.
No full suite/referee/backtest was run. The ordinary synthetic holdout-seal
unit test uses only temporary synthetic ledgers. Existing development estimates
are not revalidated by these tests. **A1-A4 helpers implemented and focused-test
verified; A1 artifact generation and A5 execution pending at this source checkpoint.**
Actual manifest/calibration generation and final artifact validation are recorded
separately after execution.

##### Draft rights inquiry v1 (not sent; recipient unapproved)

**To:** null, pending explicit owner selection/approval under Lead-D2.
This generic draft is not approval to email, log in, open an account or accept terms:

> We are considering a small personal research workflow with public source code,
> no client assets, and no distribution of raw provider data. Before any access,
> please identify the applicable agreement, channel and table/history entitlements.
> Does it expressly permit the proposed historical identity/action/payoff checks,
> retaining reproducibility evidence and independent review, including public or
> private disclosure of aggregate source-fitness conclusions? Which data, return
> matrices, logs, fingerprints, model parameters and derived outputs may be retained
> during/after subscription, by whom and for how long? What deletion obligations
> or reviewer licenses apply? Are predictive-model use and publication separately
> licensed? How are dated security/class/CIK links, ticker reuse, historical SIC,
> corrections and terminal cash/shares/elections/CVR/recovery components supported?
> What request/symbol/byte limits apply to an owner-approved development-only
> metadata-first investigation, never beyond its authorized cutoff? Please state
> unsupported use cases and any needed written permissions before any purchase.

No recipient/vendor is selected, no terms waived, no product recommendation or
fitness test result is implied. Lead-D2 and D7 remain owner-only.

### Source-pilot contract: proposed, not activated

The minimal next source decision is a **development-only coverage and identity
qualification**, not an alpha search or an F2 release. Research's deeper primary-source
dossier is a separate read-only workstream; Lead must reconcile its recommendations
with this contract before Execution runs any approved pilot.
The [subsequent dated rights gate](#current-source-rights-reconciliation-2026-11-13)
takes precedence over this earlier generic storage/pilot envelope. A durable local
cache, preserved evidence receipt, trial metric, hash or derived result is not
authorized merely because this contract calls for reproducibility.

Official documentation consulted in this turn:

- [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces):
  public submissions/XBRL access and nightly bulk updates; typical dissemination/API
  processing delays do not make filing acceptance identical to actual executable
  access. Direct retrieval returned HTTP 403; the relevant official indexed text
  was available. No SEC filing/price dataset was downloaded.
- [Tiingo EOD documentation](https://www.tiingo.com/documentation/end-of-day):
  historical-price requests and raw/adjusted prices are documented; metadata
  `startDate`/`endDate` describe available price history, not proven identity
  continuity or a terminal payoff. Direct retrieval exposed a JavaScript shell;
  claims here use indexed official documentation, not a successful API experiment.
- [Tiingo general documentation](https://www.tiingo.com/documentation/general/overview):
  a supported-symbol list is updated daily, and account/redistribution terms impose
  restrictions. A current list, advertised breadth, or "free tier" is not a
  survivorship-free historical security master. Current plan, quotas and permitted
  storage/derived publication remain unverified. No login, token or API endpoint
  was used, and absence of an explicit guarantee is treated as unknown, not proof
  that a provider cannot supply it.
- [NYSE official calendar](https://www.nyse.com/trade/hours-calendars):
  normal closes are 16:00 ET and specified early closes are 13:00 ET. This verifies
  that a fixed-16:00 helper is not a general exchange-session clock; it does not
  choose a replacement for the frozen prototype or authorize outcome access.

**Proposed authorization envelope, to be approved explicitly before acquisition:**
one provider/plan, one bounded identifier list, one declared date interval per
identifier, exact endpoints/fields, maximum request count and elapsed time, allowed
cache location, personally supplied credential mechanism, and zero-cost cap unless
separately approved. All requested stock-price dates must be <= 2024-07-31; event
signals remain in 2023-01-01 through 2024-06-30 UTC. Neither lookups nor retries may
silently request latest/full history, reuse discovered credentials, upgrade a plan,
or store post-cutoff price metadata. If historical split reconstruction cannot be
done within that approved request contract, stop and return the source limitation.

**Historical denominator and counting contract:**

1. Retain the all-10-K-filer and NT/4.01/4.02 issuer populations underlying F2,
   keyed by CIK and exact development acceptance time, before any provider/current
   ticker/price match. Keep unmatched/ambiguous issuers in the denominator.
   Record the precise existing form/date/float definitions from their pinned
   source; a different common-equity or size screen is a separately approved
   population, not a retroactive repair of the original F2 comparison.
2. Separately report issuer coverage, security/class mapping coverage, usable
   estimation-window coverage, complete outcome-window coverage, and terminal-value
   coverage. Issuer count is not event count; one CIK may have several securities,
   and a second share class must not silently double-count an issuer.
3. Before any vendor response, freeze a deterministic development-only pilot roster
   across ordinary continuing issuers, dead/acquired issuers and distress groups,
   with all excluded/unknown mappings recorded. A small or deliberately stratified
   golden-case roster cannot estimate population coverage or satisfy F2.
4. On an approved population audit, compute each distress group's issuer coverage
   divided by the common all-10-K issuer coverage. Report numerator, denominator,
   years, missing/ambiguous statuses and zero-denominator failure. Relative coverage
   >= 0.8 is only F2's diagnostic floor, not proof of unbiased prices or causal
   comparability. Do not lift F2 or drop failed cases to obtain that ratio.

**Required dated mapping/evidence record (local-only provider content):**
CIK; stable security identifier or an explicit provider limitation; share class and
instrument type; exchange; vendor symbol and valid-from/to; economic/action date;
filing/accession/source URL and public-availability time supporting each mapping;
retrieval time and source vintage; predecessor/successor link, corporate-action
terms and confidence/status. Current metadata cannot be backdated into knowledge
time. Unresolved ticker reuse, simultaneous classes, successor identities or action
terms must fail matching, not inherit the nearest/current ticker. Do not coalesce
different securities simply because their issuer CIK matches.

**Golden-case acceptance requirements (proposed fixture categories, not observed
case results):**

| Category | Required independent oracle and failure check |
|---|---|
| Ordinary continuing common equity | Dated class/exchange identity and corporate-action-free continuity; do not treat any listed instrument as common equity |
| Reused ticker | Two distinct identities/valid intervals; prove that history is not spliced across them |
| Multiple share classes / ADR or preferred contrast | Distinct security/class/unit mapping; issuer-level holdings policy cannot be invented from vendor availability |
| Split, reverse split, cash dividend | Independently sourced ex-date/ratio/cash terms; reconcile as-traded levels and total-return arithmetic without double adjustment |
| Cash acquisition | Last trade and effective/cash-consideration dates, amount and payout entitlement; missing final trade is not a zero or -100% payoff |
| Stock or mixed acquisition | Conversion ratio, successor identity and cash terms; state missing successor observations rather than manufacture a terminal return |
| Bankruptcy / cancellation / OTC transition | Actual cancellation/remaining-claim or continuing-trading evidence; absence of quotes alone does not establish a total loss |
| Halt / provider truncation / unknown disposition | Explicit unresolved missing terminal value; never carry the last price forever or classify a vendor coverage end as delisting |

Real identifiers and expected actions must be frozen from independent public,
pre-cutoff evidence by an approved later task, not invented here or selected after
vendor returns are seen. Check observed-versus-expected mappings, chronology,
action arithmetic and terminal entitlement before any inference. Record available
eventual-payoff evidence separately from information available at formation.
No case was acquired, mapped, priced or adjudicated in this turn.

**Pilot exit/recovery:** owner-approved terms/limits and AfterEvidence resource
arbitration first; stop on authentication, quota, ambiguous identity, unsupported
terminal-value, license or cutoff failures. Keep request/error receipts without
secrets in local-only storage. Record explicit blocked status; do not switch vendors,
substitute zero returns, expand the pilot or retry past an agreed budget. Actual
configuration evaluations, if later authorized, use the existing append-only ledger;
this paper contract itself adds no trial.

### Exact source audit: fixes versus unresolved contracts

The table is based on source text, not an outcome re-analysis. All unimplemented
alternatives require Lead design review and explicit scope before Execution work;
hypothesis-affecting changes require a pre-evaluation timing/deviation record.

| Area / inspected source | Exact current behavior and classification | Gate and owner |
|---|---|---|
| P2 source/time/industry contracts | Exact symbols, registered text, alternative semantics and expected fixture outputs are in the [P2 map](#p2-source-to-contract-and-fixture-map), replacing generic clock/SIC/gap warnings. | Lead/owner resolve choices before implementation. None is silently selected. |
| Fast CAR missing factors | Reference `car` drops incomplete factor/return rows, but fast engine originally masked only missing returns, causing an SVD failure or NaN on synthetic missing factors. **Corrected locally to reference parity**, without changing the observation-count window definition. | Execution: focused synthetic regression tests only. No claim historical factor files contain such gaps or prior results changed. |
| Event-time neutralization | P2-N below maps the missing event contract to formation residuals and candidate cross-sections. Event outputs remain `not_evaluated`. | No reuse of later formation residuals; `H1n` is not formal claim-level H1. |
| H4 transformations: `stage_sample`, `build_panel`, `stage_test` | D6 restricts winsorization to development, but it is still fitted over the full development cohort; neutralization is by acceptance year, not each filing instant. The preregistered random sample uses maximum float across the available archive and a multiyear filing window. This is retrospective sample/design conditioning, not a source-time universe invariant. | Preserve v2 and D6 history; Lead/owner must distinguish retrospective association from a new observable real-time estimand. Do not reselect the sample or silently claim causal/PIT compliance. |
| H4 missing NI: `build_panel` | Missing `NI(t)` formerly emitted observed no-decline when `NI(t+1)` existed. **Corrected locally:** both must be observed for `NI(t+1) < NI(t)`; equal observed incomes still give zero. | Execution: synthetic cases, no empirical label rebuild. Existing current-ROA controls may already exclude such rows; impact is unmeasured. |
| H4 impairment and outcomes | `nxt.gw_impair.fillna(0)` maps an absent tag to no impairment. Next-period outcomes are matched by regular 10-K accession/fiscal end with 300-430-day gaps, not independently certified for every missing/comparative case. Absence of a concept is not verified zero. | Research/Lead must define evidence for true zero vs unavailable taxonomy/filing, first-report ties, units and coverage before a missingness change. No new threshold, zero policy or labels chosen. |
| H6(a): `part_a`, `quiet_down_revisions` | No matched formal record in 365 days becomes zero without an independent observation-completeness flag; non-detection of quiet revision likewise depends on facts availability. 10-K/A includes Part III changes. Implementation excludes 10-Q/A in the prior 120 days too; v2/D5 wording names 10-K/A, so this extra amendment exclusion needs reconciliation. | Lead/owner decide censoring, usable-facts support and amendment definitions, not an automatic conversion of all nonrecords to known negatives or a new filter. |
| H5 overlap | P2-O below specifies session versus calendar, 20 versus 60, boundary and chaining candidate fixtures. | No H5 rerun or unilateral overlap-rule repair authorized here. |
| Co-primary / Holm | Monthly alpha/IC and raw event coefficients are diagnostics. No success decision or full family Holm calculation is emitted; v2 requires expected direction, both co-primary signs and its registered >=3.2 rule, with D3 agreement where applicable. That stated threshold is not automatically an exact Holm p-value algorithm; H4/H5 families have separate correction text. | Lead-D4 must settle the interface without unapproved threshold changes or double-adjustment. Do not select the better-sign variant or call negative alpha a successful opposite strategy. |
| Project DSR/PBO: `inference`, `ledger`, `monthly_test` | Functions and synthetic checks exist, but empirical runners do not produce actual project DSR/PBO. H0 returns are reduced to summary metrics, not a persisted aligned trial-return matrix. `n_trials` counts distinct config hashes per hypothesis (not ledger rows, code/data vintages or independent trials); engineering-purpose configs can share that hypothesis label. | Lead/Research define auditable trial family, dependence, repeated vintages/engineering distinctions, aligned periods and missing/invalid-run policy. Never remove failed/invalid history or invent return series from means/alpha. No empirical computation here. |

### P2 source-to-contract and fixture map

**Candidate map retained; all historical empirical behavior unchanged by Lead-D3a.**
The prior mapping turn made no source/test change. The later explicit owner choice
now implements only the [separate synthetic planner subset](#lead-d3a-opt-in-synthetic-planner-v02).
It does not select all alternatives below or revalidate recorded studies.
The earlier two local corrections and their prior 13-test result remain separate;
the H4 subset was not rerun by this release. Inherited 123-test CI/referee/study
results are evidence for their pinned revisions. Candidate outputs below remain
specifications except the covered synthetic subset identified in the new contract.

Registered references: [v1 section 2](PREREGISTRATION.md#2-sample-and-time)
requires the first 16:00 ET close strictly after acceptance;
[v1 section 4](PREREGISTRATION.md#4-portfolio-construction-fixed) fixes monthly
month-end formation; [v2 section 2](PREREGISTRATION_V2.md#2-specification-changes-to-existing-hypotheses-pre-data)
fixes monthly neutralization and event co-primary range -260..-21 / +1..+60;
[v2 section 4](PREREGISTRATION_V2.md#4-h5-and-h6-design) says first close after
acceptance and merging events within 20 trading days.
[D8](DEVIATIONS.md#d8-formation-time-eligibility-neutralization-and-missing-return-accounting)
withholds the neutralized event test. These texts cannot be resolved by selecting
the candidate with attractive estimates; any change affecting the registered
estimand needs an explicit pre-evaluation design/deviation decision.

| ID / source symbols | Exact existing behavior / registered tension | Candidate contract requiring a recorded choice |
|---|---|---|
| **P2-A availability.** [edgar.py](../src/asof/edgar.py): `get_bytes`, `submissions`; [store.py](../src/asof/store.py): `ingest_submissions`; [timeutil.py](../src/asof/timeutil.py): `parse_acceptance_utc` | Acceptance is parsed from a UTC `Z` timestamp and stored as `knowledge_time`. HTTP caching preserves response content, not a historical dissemination/strategy-access/processing clock. Typical SEC API delays are not per-event latency evidence. v1 uses acceptance. | A0: preserve acceptance-only *measurement proxy*. A1: separately retain acceptance, observed public availability and justified historical processing latency, with decision time after all required inputs are available. Missing availability is unknown/abstain or a separately approved scenario, never an invented timestamp. Do not overwrite knowledge time or backdate 2026 processing into historical deployability. |
| **P2-S sessions/DST.** [timeutil.py](../src/asof/timeutil.py): `ET`, `close_time_utc`, `first_tradable_close`; [backtest.py](../src/asof/backtest.py): `form_portfolios` | `ZoneInfo` converts ET correctly but every supplied date gets a 16:00 close. The helper is given a factor-date list, not an exchange schedule; formation uses the maximum observed `last_day`, not a certified session calendar. | S0: retain the literal fixed-16:00 measurement convention and its limitations. S1: explicitly version exchange sessions, holidays/early closes/timezones and use the actual close, strict `decision_time < close`, with no invented weekend/holiday session. Decide instrument venue and missing-calendar failure policy. |
| **P2-X execution.** Same time/formation symbols; [h5_events.py](../scripts/h5_events.py): `load_events` | Strict-before-close does not demonstrate auction/order feasibility, feature runtime, fill price or short availability. H5(a)'s Friday `hour >= 16` is a registered clock category, not "after any early close." | X0: descriptive close-based label, no executable-fill claim. X1: an independently specified permitted auction/decision deadline and processing budget, with next eligible session if missed. P6 owns costs/fill/borrow evidence. Do not silently redefine H5(a) to after-13:00 on early closes. |
| **P2-E event anchor.** [h0_backtest.py](../scripts/h0_backtest.py): `event_test`; [h5_events.py](../scripts/h5_events.py): nested `cars`; [events.py](../src/asof/events.py): `car`, `CarEngine.car` | First close after acceptance becomes `event_day`; both engines then sum observations strictly after that anchor. If that firm lacks an anchor observation they move to its next complete row. v2 first-close wording and +1 notation need a consistent return-interval definition. | E0: enter/anchor at close C0, earn C0-to-C1 onward. E1: measure the abnormal return *ending* at the first available close as a news-reaction label; it includes a pre-entry interval and cannot be called a return from entry at C0. Record chosen horizon and separate trading from measurement interpretations. |
| **P2-G gaps/estimation/censoring.** [events.py](../src/asof/events.py): `car`, `CarEngine.car`; [periods.py](../src/asof/periods.py): `price_end_allowed` | Joint complete observations are selected before positional offsets. -260..-21 and +1..+60 therefore count complete rows; a gap can shift the anchor, lengthen elapsed exposure or estimation lookback. Missing late rows return NaN when a full complete-row horizon is unavailable. | G0: explicitly preserve the prototype complete-observation estimand. G1: scheduled-session offsets, fixed anchor, reason-coded missing estimation/outcome rows, minimum support and full-window censoring. G2: any imputation/partial-window outcome is a separate design, not an automatic G1 repair. No candidate can fetch past 2024-07-31 or pretend a shortened window is the full label. |
| **P2-O overlaps.** [h5_events.py](../scripts/h5_events.py): `merge_overlaps`, `main` | Uses `int(days * 1.4)` calendar days against the last *kept* event. H5(a) supplies 20, H5(b)/(c) 60; v2 says 20 trading days. Neither exact-20 boundary nor transitive chaining is settled by "merge into the first." | O0: retain disclosed prototype approximation only as historical behavior. O1: 20 scheduled-session distance from last kept event; decide `<20` versus `<=20`. O2: transitive overlapping clusters anchored to their first event; explicitly distinguish it from O1. A 60-session dedup rule would require separate justification, not inheritance from CAR horizon. |
| **P2-I industry/unknowns.** [h0_backtest.py](../scripts/h0_backtest.py): `load_inputs`, `neutralize_formations`; [h4_fundamentals.py](../scripts/h4_fundamentals.py): `build_panel` | Bulk current `sic` is converted to a two-character string; no historical effective/knowledge intervals are supplied and missing values can become a string category. v2 asks for SIC2, not current-data backdating. | I0: retain a declared current-SIC proxy for conditional diagnostics. I1: dated classification plus public-availability time, joined as-of under P1 rights. If unknown, separately choose explicit unknown category, score abstention/exclusion, or a separately reported raw-only path; none is silently substituted or used to change eligibility. |
| **P2-N event-time neutralization.** [h0_backtest.py](../scripts/h0_backtest.py): `add_neutral`, `neutralize_formations`, `main`; [events.py](../src/asof/events.py): `neutralize` | Legacy `add_neutral` uses acceptance-month cohorts/max time. Production fits formation-month eligible latest signals under a fixed SIC mapping. Neutralized event outputs are withheld; v2 defines monthly residualization but does not specify a causal filing-time cohort. | N0: continue `not_evaluated`, preserving monthly design. N1: a prior-period reference fit available before event time scores the new filing. N2: contemporaneous as-of cross-section including only available signals (state whether focal event joins fit). Fix firm/latest-vs-event weighting, support, industry/size/acquisition availability and strict/tied-time rules first. Never reuse a later cohort/formation residual at earlier acceptance. |

#### P2 proposed fixtures and candidate outputs

All examples are **synthetic definitions**, not inspected filings/prices or new
configurations. `C0,C1,...` are successive *supplied* session closes; `Ri` is the
simple return from `C(i-1)` to `Ci`. Toy abnormal returns below assume zero
expected return and adequate independent synthetic estimation history. Equality
conventions and unsupported inputs must yield an explicit reason, not a
success-shaped fallback. Dates used for timezone arithmetic carry no stock outcomes.

| Fixture / relevant choices | Defined inputs | Expected candidate outputs (not executed) |
|---|---|---|
| **F-A1 acceptance versus availability** | Acceptance = C0 minus 30 seconds; first observed dissemination/access = C0 plus 5 seconds; processing 2 seconds. | A0 anchors measurement at C0. A1 decision at C0+7 seconds cannot enter C0 and chooses C1 if otherwise eligible. Unknown dissemination: A0 stays explicitly proxy; A1 returns unavailable, not acceptance plus a typical SEC delay. |
| **F-S1 early-close / strict boundary** | Synthetic Friday schedule closes 13:00 ET; next session Monday 16:00. Filings at Friday 12:59, 13:00 and 14:00. | S0's fixed 16:00 maps all three to Friday's synthetic close. S1 maps 12:59 to Friday13:00 and both equality13:00 and14:00 to Monday16:00 under strict-later rule. At a supplied holiday/weekend neither candidate may invent a new session. H5(a)'s registered16:00 category is unchanged by either session-label test. |
| **F-S2 timezone and invalid input** | Supplied normal sessions 2023-03-10 and 2023-03-13; ET close16:00, before/after DST transition. A UTC-midnight instant is converted to its ET date. | Both S0/S1 use21:00UTC for March10 and20:00UTC for March13, not a fixed UTC hour. Compare UTC instants, not date prefixes. Existing parser rejects strings without `Z`; existing helper rejects naive datetimes. These invariants are not a new experiment or a change to strict-close policy. |
| **F-X1 auction deadline** | C0=16:00; synthetic order deadline15:50; acceptance15:58, public access15:58:10, processing20 seconds; no supported earlier order. | X0 may label relative to C0 but asserts no fill. Under X1, decision15:58:30 misses deadline: next otherwise eligible close, not C0. A decision exactly at the deadline needs the explicitly chosen inclusive/exclusive rule; public-before-close alone is insufficient. |
| **F-E1 entry versus reaction** | C0 is first eligible close. R0=0.01, R1=0.02, R2=0.04; horizon2, zero expected returns. | E0 sums R1+R2 =0.06 and ends C2, matching current post-anchor indexing on complete data. E1 sums R0+R1 =0.03 and ends C1 as a reaction label, **not** earned by entry at C0. Neither is silently called the other. |
| **F-G1 post-event gap** | Anchor C0 observed; R1=0.01, R2 missing, R3=0.03; horizon2. | G0 uses next two complete returns, ends C3, sum0.04. A G1 full scheduled-window policy ends C2 with missing outcome/reason; it does not extend to C3. A proposed G2 zero-imputation would give0.01 or a partial-window result could report one observed return, but neither represents an approved full-window label. |
| **F-G2 missing anchor / fixed estimation** | No firm observation at scheduled C0; complete firm rows resume C1. Separately remove one factor/return row in scheduled estimation slots -260..-21. | Current G0 moves the anchor to C1 and counts subsequent complete rows; its240-row estimation window can reach farther back. G1 retains scheduled anchor and slot bounds: unobservable return intervals/support are reason-coded missing or censored under the accepted support rule, not shifted. Missing-factor fast/reference parity is the earlier fix, not a session solution. |
| **F-G3 sealed tail** | Required C2 for a full horizon is after2024-07-31; only C0/C1 permitted on disk. | Full-window G0/G1 cannot complete: missing/censored and no later fetch. Any G2 shortened label must be separately named/approved; its observed prefix cannot be reported as the original full horizon. No real holdout test is part of this fixture specification. |
| **F-O1 wrong horizon / boundary** | Two events25 scheduled sessions apart and40 calendar days apart in a supplied synthetic calendar. Separately place an event exactly20 sessions after first. | Current H5(b)/(c) `60*1.4=84` calendar threshold merges the40-day pair. O1's20-session rule retains it. At exactly20, strict `<20` retains; inclusive `<=20` merges. Record a choice, not an inferred interpretation of "within." |
| **F-O2 transitive chain** | Events at session indices0,15,30. | First-kept20-session O1 retains0 and30, dropping15. Transitive O2 links both gaps and retains cluster anchor0 only. This is a different clustering rule, not an optimization. |
| **F-I1 availability and unknown SIC** | Prior code28 known before event D1; code35 effective D0 but first publicly available D2, with D0<D1<D2. A second issuer has no dated code. | I1 at D1 uses28; effective-date-only35 leaks availability and fails that fixture. I0/current proxy35 is a declared different information set, not certified PIT. For the second issuer, explicit-unknown retains it as unknown; abstention/exclusion produces no neutralized score; raw-only leaves the raw diagnostic separate. Pick one before evaluation, never infer missing SIC as observed zero/classification. |
| **F-N1 no future cohort / focal fit** | At focal time t,12 prior eligible reference firms have score0; focal score1 becomes available at t; one future filing has score100. Intercept-only schematic isolates the fit-scope choice, not a replacement for required v2 controls. | N0 outputs `not_evaluated`. N1 prior-fit mean0 scores focal residual1. N2 including all13 available firms has mean1/13 and focal residual12/13. Score100 is excluded from both at t; adding it cannot alter the earlier fit. Actual full-control tests would also fix weights, SIC unknown policy, size/MA availability, tied times and minimum support before execution. |

**P2 decisions ready for Lead:** accept or reject a named candidate for each row,
its information-set/return-interval meaning, tie/unknown/support handling, and
whether it preserves the original claim or requires a separately identified design.
The map is not an implicit recommendation to change all clocks to one candidate.
Current tests for DST/strict-before-close and formation invariance in
[test_timeutil.py](../tests/test_timeutil.py) and
[test_h0_backtest.py](../tests/test_h0_backtest.py) are useful prior art, not proof
of these unimplemented semantics. Only after design acceptance may Execution
add the smallest synthetic cases (threads1) and a bounded implementation; later
empirical evaluation is a separate gate.

#### Lead-D3a opt-in synthetic planner v0.2

**Selected by explicit owner decision and implemented with synthetic validation.**
This is a new opt-in planning path, **not** a migration of v1/v2, a changed event
estimand in historical runners, or acceptance of neutralization/overlap policies.
API: [asof.timing.plan_return_window](../src/asof/timing.py), returning immutable
`ReturnWindowPlan` and `ReturnSlot` records. Only the new
[test_timing.py](../tests/test_timing.py) imports it; no H0/H4/H5/H6 runner,
`timeutil`, `car` or `CarEngine` was changed in this implementation turn.

**Explicit inputs, no data ingestion:** ordered unique timezone-aware session
closes; `information_ready`; an aware `observation_cutoff`; sets/collections of
available firm closing observations and complete factor/RF return-row timestamps;
positive integer `horizon`; ordered negative `estimation_offsets`; and optional
session-to-order-deadline timestamps. No calendar package, network, file/data
loader, factor fit, price/return value or model is used. The approved usage is
caller-provided synthetic schedules/support only; the API cannot certify that a
caller-supplied calendar or availability assertion is historically true.

- Instants are normalized and returned in UTC. The first supplied close C0 must
  be **strictly after** readiness; a supplied deadline for that session must also
  be strictly later. Equality skips the session. Missing deadlines remain
  `order_deadline=None`, not inferred evidence. Even a satisfied supplied deadline
  confers **no order/fill/borrow/capacity claim**. Readiness is not inferred from
  acceptance, typical SEC latency, current runtime or an undocumented auction rule.
- The anchor is a hypothetical entry at C0, selected without looking at firm or
  factor support. Outcome offsets +1..+H represent **C0 -> C1 through
  C(H-1) -> CH**, never the return ending at C0. Estimation offsets remain named,
  fixed scheduled return slots relative to C0. A return ending at Ck requires
  firm closes at C(k-1) and Ck plus the factor/RF row ending at Ck; the preceding
  price close may lie before the first estimation offset and must not be invented.
- Every requested slot retains `offset`, UTC `start`/`end` (or `None` if outside
  the supplied schedule), `status` and reason codes. Available counts are reported
  by `estimation_support`/`outcome_support`; there is **no chosen minimum support
  threshold**, fitting, factor estimate, computed return or partial-window score.
  Complete metadata support is not sufficient scientific or trading evidence.
- Statuses: `complete` = all requested support plus anchor available; `missing` =
  known in-schedule/pre-cutoff observations absent; `unavailable` = no eligible
  anchor or required schedule bounds absent; `censored` = known requested bounds
  or anchor exceed the cutoff. If several issues coexist, root status precedence
  is censored, unavailable, missing, complete; slot/anchor reasons preserve detail.
  Reasons distinguish missing anchor, firm interval start/end, factor row,
  schedule boundary and cutoff. No anchor shift, session compression, extended
  lookback/horizon, zero imputation or shortened full label occurs.
- Invalid inputs raise explicit `ValueError`: naive timestamps, unordered/duplicate
  UTC closes, invalid horizon/estimation offsets, unsupported observation timestamps,
  observations after the supplied cutoff, or a deadline outside its session/after
  close. An empty/exhausted or short supplied schedule is a valid unavailable
  plan, not an invalid-input success. Omitted internal sessions cannot be inferred
  without a real schedule source; this API does not fabricate them.
- `price_end_allowed` validates the cutoff's UTC date against **2024-07-31**,
  with no override argument exposed. A later cutoff raises `HoldoutAccessError`.
  Future **schedule metadata only** may specify a requested tail so it can be
  reported censored; firm/factor support beyond the supplied cutoff is rejected,
  and nothing is fetched. These guard tests use synthetic timestamps, not a
  project holdout ledger or any held-out observation.

**Validation actually executed now (single numerical thread):**

```powershell
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
.\.venv\Scripts\python.exe -m pytest -q tests\test_timing.py tests\test_timeutil.py tests\test_events.py
.\.venv\Scripts\python.exe -m pytest -q tests\test_timing.py
.\.venv\Scripts\python.exe -m ruff check src\asof\timing.py tests\test_timing.py
.\.venv\Scripts\python.exe -m ruff check --select E4,E7,E9,F src\asof\timing.py tests\test_timing.py
```

The first combined run passed **37 tests** (initial planner tests plus related
legacy timing/CAR tests). Changed-file configured Ruff then identified one
adjacent-pair iteration style issue, corrected with stdlib `pairwise`; no new
dependency was installed. Final planner tests, including the added exhausted
schedule case, passed **20 tests**; both final changed-file lint commands passed.
Cases cover strict ready/deadline equality, supplied synthetic early close and DST,
post-entry interval bounds, missing anchor/outcome/estimation/factors without
shifting, empty/short/exhausted schedules, invalid input and a censored synthetic
cutoff tail. No empirical performance benchmark or full suite was run.
Pylance's file syntax request timed out; the real test imports passed, but no
Pylance/editor/type-check success is claimed.

**Release boundary:** uncommitted code and synthetic tests only, with no ledger
rows, source/provider changes, data scans/hashes, refits, simulations, model/API
work, study rerun, commit/tag/push or publication. CL-P1/3/4/5/6 remain queued
behind their existing external/scientific gates. Lead-D2, D4-D9 and the remainder
of D3 (including D3b/D6 neutralization/overlap/label issues) remain open.
Heavy work still needs verified AfterEvidence arbitration; no such route, new
budget or hourly scheduler is supplied by this implementation.

### Holdout and reproducibility decision packet: release remains blocked

The decision is **NO OPENING AUTHORIZATION**, not a new experiment or a new seal.
These independent gates must be recorded before any future command is approved:

1. **Isolation/window gate (owner + Lead):** price cutoff stays 2024-07-31;
   development signal dates and hypothesis signs/thresholds stay frozen. July
   2024 visible prices for development tails overlap nominal return holdout labels.
   Register the overlap/isolation decision without inspecting more outcomes.
   H4's original full-panel winsorization contamination persists as historical fact;
   code repair is not an untouched holdout, and no new dates/tags/resealing are
   inferred from this review.
2. **H4 and H6(a) maturity are separate (Lead/owner):** for H4, audit each
   candidate filing's next fiscal-year regular first report and availability,
   not a generic 60-day stock horizon. For H6(a), require an independently complete
   365-day follow-up window from each acceptance, plus defined observation support.
   A 2025-06-30 acceptance's nominal 365-day anniversary is 2026-06-30, not proof
   that all labels/archives are complete or isolated. Do not fetch these outcomes.
3. **Source/method gate (Lead):** F2, F6 vendor-quality limits, historical/unknown SIC,
   session/early-close/gap/anchor semantics, event-time neutralization, retrospective
   H4 conditioning, missing-vs-zero support, amendment/overlap rules and incomplete
   co-primary/DSR/PBO remain distinct blockers. A technical-referee pass or
   >=0.8 coverage ratio does not waive them.
4. **Freeze packet (Execution only after approval):** pin clean source commit,
   preregistration/deviation revisions, runtime and processing-source fingerprints,
   exact schemas/universe/mappings/availability times, data vintages and historical
   exposure inventory; identify trial families, support gates, cost components,
   zero/missing/invalid states, output dictionary, allowed commands/resources and
   stop conditions. Record existing history rather than rewrite it. No snapshot
   rebuild, new hash/tag or freeze is executed here.
5. **Permission and maturity gate (owner):** 2026-11-30 monthly return tail and
   2027-01-29 scheduled +60-session tail remain conditional milestones from the
   previously documented calendar assumptions. Actual closure/gap/finalization
   contracts and separate H4/H6(a) decisions still control. Neither "do all" nor a
   mature date approves key use, costs, publication or any holdout access.
6. **Recovery before any later run (Execution + Lead):** stale snapshot, incomplete
   mapping/labels, unexpected source revision, failed support gate or accidental
   exposure means stop, retain evidence, scope affected hypotheses/periods and
   request an owner decision. Preserve failed trial rows once an evaluation has
   started. Do not extend dates, replace unknowns with favorable defaults, erase
   history, silently substitute a source, or reopen a single-use evaluation.

### Coordination, validation and next owner actions

AfterEvidence's exact route and current resource arbitration were **not verified**
in this project's known context. No unrelated session was contacted and no heavy
CPU/data/model/API work was authorized. The focused synthetic test command set
`OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1`; it did not read research datasets.

No supported host scheduler/automation API was discovered; only native session
context/status/messaging capabilities are available for this coordination. **Hourly
check-ins are not configured.** No sleeps, cron/poll loops, services, new chats or
idle-chat wakeups were installed. One completion evidence handoff to the verified
Lead chat is the agreed fallback, not a scheduling claim. Prep remains idle until
activated with verified evidence.

Validation in this turn:

- Before correction, six targeted synthetic cases gave **3 failed / 3 passed**:
  missing market-factor SVD failure, missing RF NaN mismatch, and missing-current-NI
  false zero.
- After correction, `python -m pytest -q tests\test_events.py tests\test_h4_development.py`
  gave **13 passed**. This includes the existing synthetic planted-CAR, gap,
  neutralization, small speed check and future-H4-outcome invariance cases.
- `python -m ruff check --select E4,E7,E9,F src\asof\events.py scripts\h4_fundamentals.py tests\test_events.py tests\test_h4_development.py`
  passed. No full lint or full
  suite was run, and prior empirical/CI/referee results are not updated evidence
  for these uncommitted corrections.

Next decisions: Research finishes the independently assigned dossier; Lead reconciles
and ranks its recommendations against this source/method packet; the owner settles
ambiguous source/estimand/isolation and scoped key/resource/publication permissions.
Execution can then queue only explicitly approved work, after verified AfterEvidence
arbitration where needed. No pilot, new empirical configuration or holdout work is
queued by this packet.

## Current source rights reconciliation (2026-11-13)

**Documentation-only follow-up; no acquisition or provider fitness evaluation.**
This is a local revision, not a commit, publication, license recommendation,
legal opinion, or acceptance of any provider/account terms on the user's behalf.
The earlier seven-file patch and its synthetic-test evidence are preserved; no
code, data, result, trial, tag, hypothesis, score or date was changed by this follow-up.
No tests, referee, backtests, hashes/data scans, account access, keys, models or
paid resources were used. Existing studies are historical evidence for their
recorded revisions, not validation of the current dirty worktree.

### Evidence provenance and limits

The Lead relayed Research's completion handoff and a proposed roadmap. At that
docs-only follow-up's one bounded context read, Research turn 3 was still `inProgress`; a completed pageable
report was not available. Execution did not poll, wake Research, or claim to have
read its completed full dossier at that time. The synthesis and proposed pilot
ceilings were then attributed to that handoff. The later six-package turn read
the complete original report and reconciled its proposed envelope below; new
decision cards and account-specific rights still await review.
The decisive public documents listed here were separately
retrieved directly on 2026-11-13, without submitting private material or requesting
any market data. Directly checked clauses are distinguished from that provisional
handoff, not evidence that a provider meets the project's coverage requirements.

| Public source and section | Retrieval and applicable uncertainty |
|---|---|
| [Tiingo Terms of Use](https://www.tiingo.com/tos/), header, amendment notice, sections 1.4(h), 1.6(a)-(c), 1.7(a)-(d) | Direct rendered text retrieved, including the 1.6/1.7 continuation. Header says effective 2022-01-16, last updated **2026-11-05**. Notice provisions distinguish new and existing users; applicable account dates, notices and Supplemental Terms are unknown. This is the current posted text, not a finding about a particular user's binding agreement. |
| [Sharadar Personal Use License Terms](https://sharadar.com/terms.html), sections 2, 4, 6, 8, 10 and 18 | Direct rendered text retrieved. No revision date was visible in the reviewed text; **2026-11-13 is retrieval date**, not an invented update date. Scope and actual entitlement must be confirmed for the chosen purchase channel/account. |
| [Sharadar FAQ](https://sharadar.com/docs/faqs), ticker changes, acquisition consideration, historical industry, and Personal Use questions | Direct rendered text retrieved. These are provider documentation claims, not independently verified data quality, historical availability, or licensed publication rights. FAQ descriptions do not override the license's restrictions. |
| [Norgate Data FAQ](https://norgatedata.com/data-package-faq.php), `trial-data-length`, `custom-trial-data`, `symbol-historical`, `symbol-static-identifier`, `historical-classifications`, `delisting-return` | Direct rendered sections retrieved, including the later delisting section. No revision date established. Read-only product-scope review, not a trial or completeness test. |
| [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases/) | Direct official link redirected to [Morningstar's CRSP product page](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases), describing permanent identifiers and active/inactive securities. Product documentation is not access permission; no personal, academic or employer entitlement is presumed or sought. |

Earlier SEC and Tiingo API-documentation assertions in the bounded packet were
based partly on indexed official text (SEC direct 403; Tiingo API JavaScript shell).
That limitation remains; the **terms** checks above are new direct-text verification,
not an upgrade of those earlier endpoint/coverage claims to empirical validation.

### Tiingo: free/trial reproducibility is not established by transient access

- **Durable retention:** section 1.6(a) says Starter/trial users may not retain
  data in "persistent or durable storage." It expressly applies the same limit
  to Derived Products and requires removal before the process/job/session ends.
  Consequently, the ordinary project workflow of raw caches, processed snapshots,
  retained metrics, logs, receipts and reproducible derived artifacts is **not
  authorized by the posted Starter/trial terms**. Storing only aggregate results
  or a hash is not a blanket workaround.
- **Paid is not permanent:** section 1.6(b) limits data retention to eligible
  active paid rights and requires deletion on termination/downgrade; exceptions
  described there are not offered for Starter or Power. Section 1.6(c) permits
  some non-substituting, non-reconstructive paid-plan derivatives conditionally,
  not all outputs, transformed datasets or hashes. It specifically restricts
  validating/reconciling another dataset with Tiingo data. Existing snapshot/hash
  or cross-source reconciliation machinery must not be reused on an assumption
  that any paid subscription grants those rights.
- **Model use and disclosure:** sections 1.7(a), (c) and (d) add separate model
  restrictions. Starter/trial plans lack the Power predictive-model permission.
  Power's permission requires models and outputs to be used "solely for your
  own internal purposes"; it does not establish a right to expose a model or its
  outputs in this public project. Conditional derivative examples in 1.6(c) do
  not waive the additional 1.7 model/output conditions. Which activities fall
  within these definitions requires applicable-rights review, not a unilateral
  reclassification of a predictive study as a permitted calculation.
- **Benchmarking and assistant access:** sections 1.4(h) and 1.7(d) impose
  additional restrictions on service/data analysis and AI/model benchmarking.
  Section 1.7(b)'s conditional reference use of AI tools is distinct from training
  or distributing models, and does not waive retention rules. No provider data
  should be submitted to a chat, tool, retrieval index or evaluation dataset based
  on this public terms review. No such data was submitted here.

The historical suggestion "try a free Tiingo account and keep reproducible public
results" is therefore **withdrawn as a viable default premise under the current
posted terms**, not erased from project history. No account-specific conclusion,
grandfathering, written exception, purchase or alternative plan is endorsed.
User consent can authorize project actions but cannot grant missing vendor rights.

### Sharadar, Norgate and CRSP: distinguish product fields from usable rights

**Sharadar documented fields.** The FAQ describes separate share-class
permatickers, rewired ticker histories and recorded ticker-change actions; historical
SIC changes are represented by `sicchangefrom`/`sicchangeto`. Merger consideration
has cash and share components, with election alternatives distinguished from
additive mixed terms. It explicitly says "Contingent value rights are not included."
These features are relevant to the proposed identity/exit checklist, not proof of
coverage or PIT CIK/security joins. Action dates also do not by themselves establish
the public knowledge times needed for formation-time joins. No named security,
row, merger amount, return or coverage ratio was retrieved or tested.

**Sharadar rights.** The direct Personal Use terms' sections 2 and 4 restrict use
and redistribution, including professional/organizational use; the fit of a public
portfolio project is not resolved by its personal ownership. Section 8 requires
"prior written approval of Sharadar" for external disclosure of service/data testing
or fitness conclusions. An F2 coverage or golden-case service evaluation must not
be performed and then published under an assumption that aggregate metrics escape
that condition. This section documents public terms and provider statements only;
it contains no such empirical service-fitness conclusions.

Section 10 requires deletion of data and reproducible substitutes within 30 days
after termination while allowing specified non-reconstructive research outputs,
backtests, models and similar works to be kept. Section 6's attribution/output
language and those retention exceptions do **not** override section 8 or establish
blanket public-project rights. A reproducibility plan must reconcile permitted
retention with what can lawfully be preserved, not promise indefinite cache access.
Direct Sharadar terms/FAQ and Nasdaq-delivered product entitlements must not be
conflated: verify the actual channel, field/history coverage and applicable
agreement without borrowing rights or schema guarantees from the other channel.

**Norgate documented limitations.** Its FAQ states that prior ticker/name histories
and previous industry classifications are not provided, although a stable `assetid`
is available in supported environments. It also says terminal economic
return/recovery/final-outcome information is not supplied. Its suggested
last-available-bar convention is **not adopted**: changing a payoff estimand to
that convention would need scientific approval and could reintroduce a
future-delisting liquidation assumption. The trial is limited to two years of
history, with no custom extension according to the FAQ. Research's relayed handoff
describes that trial window as rolling; on that interpretation it does not reach
the permitted 2023 through June-2024 signal interval as of this review. The directly
retrieved section did not establish exact trial start/end dates, so those remain
unverified, not permission to inspect a trial or substitute later observations.
These are documented
scope limits, not measured provider fitness, a purchase recommendation, or a
conclusion about every separately contracted package.

**CRSP** remains a licensed methodological/reference possibility, not an assumed
free, personal, institutional or employer resource. Product descriptions alone do
not establish usable access, retention, redistribution or code/data-sharing rights.

### Proposed small pilot envelope: subordinate to rights, not an approved roster

Research's Lead-relayed proposal is adopted here **only as a proposed ceiling**
within the earlier historical-denominator/mapping/golden-case contract. Subsequent
access to the complete original dossier now supplies its exact proposed strata;
this is still not an accepted source pilot or new numerical gate:

- **24 metadata-selected development-era cases in six identity/exit strata**;
  at most **40 securities, 150 requests and 50 MiB** of response payload. These are
  project ceilings, not vendor quotas or permission. Confirmed entitlement/rate,
  permitted storage and explicit owner budget could be more restrictive and take
  precedence; count attempts/retries and bytes toward the envelope.
- The original dossier proposes four cases in each of: continuous eligible common
  stock; cash acquisition; stock/mixed merger; OTC transition/bankruptcy; ticker
  change/reuse; and multiple share classes/issuer succession. This replaces only
  Execution's provisional grouping, not a frozen roster. Split/distribution and
  unresolved-terminal oracles in the earlier golden-case checklist still apply.
  The dossier also proposes a ceiling of ten requests/hour; confirmed lower vendor
  limits take precedence and this is not an entitlement. The newly assigned P1
  card still needs Lead reconciliation before allocation/actual identifiers can
  be frozen from permitted metadata, not returns.
- Proposed identity gate: **24/24 date-valid identity resolutions**, with no
  silent drop/replacement of failed cases; explicit pass/fail/unresolved status
  and independent pre-cutoff oracles for every terminal-value case. Do not fetch
  later outcomes to finish an immature case; mark it unresolved. The separate
  terminal-payoff and rights gates cannot be inferred from identity success.
- A pass would establish at most bounded feasibility for the documented cases,
  **not** population coverage, absence of survivorship, F2 clearance or hypothesis
  support. It does not alter F2's denominator or its >=0.8 diagnostic floor.

Nothing is run or queued. No roster is frozen, credential sought, entitlement
inferred, data retained, pilot result published, or owner/vendor consent obtained.
If rights cannot support the proposed reproducibility and disclosure, stop before
acquisition: do not replace the required workflow with an unreviewed transient
trial, pay for an assumed exception, or publish a prohibited service evaluation.

### Lead priority order and unresolved release gates

The accepted **ordering of proposed work**, not authorization to execute it, is:

1. **Rights plus historical identity and terminal-payoff feasibility.** Resolve
   provider/channel/account terms, retention, reproducible artifacts, assistant/model
   use, permitted validation and disclosure before choosing a source or pilot.
2. **Calendar, dissemination, event anchor, gaps and label observability.** Settle
   early closes, actual availability versus acceptance, session versus complete-row
   horizons, H4 missing-vs-zero and H6(a) follow-up support without outcome-guided tuning.
3. **Power, dependence, trial families and co-primary inference.** Reconcile
   multiple-testing counts/correlated repeats/engineering trials, recoverable aligned
   return evidence, Holm/co-primary definitions and what the sample can identify.
4. **Blinded human labels and cheap structural baselines.** Consider only a separately
   specified development-only labeling/blinding plan and inexpensive non-LLM
   comparators; neither new labels nor new signal/model configurations are authorized.
5. **Complex modeling only after preregistered evidence gates.** No new model,
   download, training or broad experiment is justified by these source descriptions.

**Owner decisions still required:** written/applicable vendor rights where needed
and scoped personal access/spending/publication approval; a compliant retention and
reproducibility policy; the ambiguous method/inference contracts in the preceding
packet; July-2024 overlap and historical H4 contamination (repair is not pristine);
and separate H4 next-report versus H6(a) 365-day label maturity/isolation decisions.
The price cutoff remains **2024-07-31**, with no later outcomes inspected.
November 30, 2026 and January 29, 2027 remain conditional maturity milestones,
not opening dates or permission. No splits, dates, scores, hypotheses or tags change.

**Coordination/verification status:** AfterEvidence routing/arbitration remains
unverified, heavy resources remain blocked, and no supported hourly scheduler
exists in the exposed tools. No monitor, new agent/chat, message to Lead, or
Research/Prep activation was created by that follow-up. That turn stopped without
the final report; the [six-package queue](#six-package-dependency-queue) records
subsequent integration of the completed original dossier and design cards v1.
Account-specific rights interpretation and the remaining scientific/operational
decisions remain pending; full design review is not their acceptance.
No code tests or studies were rerun: the previous 13 focused synthetic
passes remain exactly that earlier evidence, not new validation of a source license.
