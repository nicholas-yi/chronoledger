# Data audit: survivorship coverage of free price data

**Current override: P0 time-integrity BLOCKED.** The broad JSON-UTC verification
claim is withdrawn; see the [P0 verdict](#batch-c-part-1-p0-integrity-verdict--stop)
and [F9](FINDINGS.md#f9-p0-acceptance-time-authority-is-not-uniformly-certified-by-json-z-fields).
Older rebuild receipts and the frozen preregistration describe historical claims,
not current source-clock certification. The registered first-close rule is unchanged.

### Approved full timestamp metadata check

The user approved the [exact full-check proposal](../results/timestamp_full_plan.json)
on 2026-11-16. The project SEC ceiling changes from 150 to 34,402, with usage
unchanged at 140 before this run. At most 34,252 new metadata requests and ten
documentation requests are approved; unused documentation requests cannot buy
extra filings. This is not a return trial or permission to repair source data.

[The runner](../scripts/run_full_timestamps.py) has separate `freeze`, `run` and
offline `report` phases. `freeze` pins the exact 16,921-accession and 34,354-URL
private lists (including 102 cache hits), metadata universe, registered-calendar
dates, code, existing caches and declared User-Agent hash in a committed config.
The exact private lists remain in ignored data; their committed hashes define the
allowlist. Commit that config and all source/test changes before `run`; `run`
requires the config bytes to match Git and refuses any prior attempt marker.
No automatic resume exists, including after a first-request stop.

The full adapter inherits the pilot's strict transport. It is serial, at most
two starts per second, with a 30-second total request timeout, no redirects and
no retries. It reads at most 64 KiB per metadata resource; at-cap and missing
resources stay unread/unknown and do not stop the next allowed URL. Other
non-success responses, transport failures, scope/budget/integrity errors,
12 hours elapsed, the 4 GiB disk allowance or a detected sleep/suspend stop it.
Windows uptime versus unbiased awake uptime detects suspend differences above
two seconds; the in-flight task is cancelled and recorded, never silently resumed.
Raw bodies and append-only receipts stay private. Every 500 resources and at a
final stop, the runner flushes receipts/outcomes and writes a hash checkpoint.

The proposal names documentation categories, not exact qualifying Filer
Manual/PDS/field-clock URLs. The documentation stage is therefore skipped rather
than guessing URLs. Header conversions remain conditional on Eastern wall time,
not verified UTC. Offline reporting accounts for every selected accession,
including unknown/unattempted rows, and separately labels conditional first-close,
month, eligibility and latest-filing comparisons. The existing nominal 16:00 ET
calendar is not a venue/early-close certification. No price, return or signal
value is used, no ledger row is added, and no data repair, CIK remap, correction
release or backtest rerun follows.

**Stopped result, not a full check:** [the review](../results/timestamp_full_review.json)
and [original report](../results/timestamp_full_report.json) record an HTTP 503 stop at
15:45 ET on 2026-11-16, after 1,281 new attempts (1,280 HTTP 200 and one HTTP 503).
There are 1,289 resource outcomes including eight pinned cache hits; five at-cap bodies
remain unknown. Only 641 header/index pairs are conditionally complete, all matching
both stored clocks under the Eastern assumption. All 16,921 rows remain historically
unqualified; no verified assignment-change count is established. The run did not resume.

The post-run receipt audit also found 97 recorded UTC inter-start gaps below 0.5 seconds,
minimum 0.490596, with up to three recorded starts in a half-open one-second window.
Both the Windows monotonic and wall clocks used here have 15.625 ms resolution.
High-resolution send instants were not logged, so strict two-starts-per-second compliance
cannot be certified; this is not dismissed as harmless rounding. The frozen source is
unchanged. A future limiter needs high-resolution monotonic measurement, a post-wait
recheck and early-wake tests before any separately approved continuation or source amendment.

**Approved amendment A1 (2026-11-16), before further requests.** The original discrepancy
is a precision miss against our own protocol, not a SEC fair-access breach: the recorded
average was about 1.9 requests/s, below SEC's published 10/s ceiling. Calendar-second
counts never exceeded two; sliding windows and quantized timestamps are different.
This context does not retrospectively certify the original half-second spacing.

[The additive A1 runner](../scripts/run_full_timestamps_a1.py) leaves every original
source file and outcome unchanged. Its QPC `perf_counter` limiter rechecks after every
wait and refuses dispatch gaps below 0.667 seconds. Each attempt records application
transport-dispatch QPC time and UTC; these are not wire timestamps. One shared serial
connection pool is borrowed by one-use scoped adapters, so retries do not clear or
bypass the original adapter's stopped/duplicate guards.

A1 permits one same-URL retry after at least 600 QPC seconds for HTTP 503 or 429,
at most five such waits total; a second 503/429 or a sixth required wait stops it.
Other original stop/unknown rules remain. The exact remainder puts 108 designated
clock-disagreement accessions first, 256 CIK disagreements next, then shuffles the
other remaining accessions with seed 2026111603. Previously processed resources,
including five at-cap unknowns, remain protected; only the expressly reeligible old
503 URL may get a new A1 primary attempt. The original 1,289 outcomes are never edited.
The ceiling stays 34,402, starting at 1,421. At most 32,972 primary attempts plus five
retries fit within it. A1 resets only the 12-hour wall clock; the combined old/new
4 GiB budget, 500-resource checkpoints, sleep stop, no automatic continuation,
population, parser and unqualified Eastern-clock assumption remain.

**A1 stopped on a transport timeout, not a completed full audit.**
[The review](../results/timestamp_full_a1_review.json) records 1,716 attempts
(1,713 HTTP 200, two HTTP 503 and one timeout) from 16:12 to 16:53 ET.
Both 503s received their single allowed retry after 600.017792 and 600.002800
QPC seconds and returned HTTP 200; the later timeout was not retried.
All 1,715 QPC dispatch gaps met the 0.667-second minimum (minimum 0.667809400,
median 0.677298300 seconds). No original record/source was edited or re-fetched.
The old 503 URL was not reached in the random remainder and remains pending.

The 37 winter and 71 summer comparisons all match API time under the Eastern
assumption; bulk is respectively five and four hours later. The combined table
has 1,264 unique conditional instants, but zero historically qualified UTC times.
Conditional bulk-side changes are 30 first closes (10 winter, 17 summer, three
CIK-disagreement cases), one formation-eligibility record-month and one latest-filing
firm-month; API-side counts are zero. Actual verified assignment changes remain
undetermined. Counter 3,137/34,402, ledger 74 and all raw data remains ignored;
no repair, correction release, financial rerun or automatic continuation occurred.

**Approved A2 bounded sample, before requests.** A separate user decision selects
the next 3,000 **new** random-rest accession IDs after A1's first 270, in the
unchanged seed-2026111603 order. The A1 timeout is outside that window and remains
pending; the older 503 is attempted only if its existing position falls inside.
Already processed resources are not re-fetched. The user clarified that statistics
cover all internally agreeing random-rest strata, including the boundary pool,
not only the named agreement-sensitive pool.

[A2](../scripts/run_full_timestamps_a2.py) predeclares an exact one-sided 95%
Clopper-Pearson upper bound by pool and overall for a complete conditional header
that disagrees with both stored sources. Its primary n excludes unread/incomplete
pairs, never treating them as error-free. A separate conservative bound treats
every unread **selected** eligible case, including unvisited cases after a stop,
as an error. Both use the fixed union of the 270 A1 and 3,000 A2 accessions.
This definition is prospective for A2 but follows inspection of A1; it is not
a registration predating A1. Readability/stopping limitations, the Eastern
assumption and restriction to the remaining random-rest order remain explicit.

A2 keeps QPC gaps at least 0.667 seconds and the original metadata/clock/parser
contract. It permits one same-URL retry after 60 seconds for timeout or evidenced
connection reset, or 600 seconds for HTTP 503/429. There are at most 20 status
waits and at most two hours of cumulative waiting across both kinds. A second
request error stops; original 404/read-cap unknown handling is unchanged.
The wall cap is four hours; ceiling 34,402, starting usage 3,137, combined 4 GiB,
500-resource checkpoints, sleep stop and no automatic continuation remain.
No repair, price/return use, model run or ledger row is authorized.

**A2 final stop, not the planned sample completed.**
[The review](../results/timestamp_full_a2_review.json) records a second HTTP 503
after the allowed retry: 109 attempts, 100 resources and 50 of 3,000 new accessions.
Eight 600-second waits and one 60-second timeout wait totalled 4,860.300138 QPC
seconds; the first eight retries succeeded, the ninth returned 503 and stopped.
All 108 dispatch gaps met 0.667 seconds (minimum 0.668977, median 0.682458).
Neither prior failed URL was reached; no original completed resource was re-fetched.

The combined sample has 320 visited, 314 readable internally agreeing accessions,
and one conditional disagreement: both stored clocks are five hours later than
the header-derived instant under Eastern, with header/index agreement. Complete-case
one-sided 95% CP upper bounds are 1/304 -> 1.55% for agreement-sensitive, 0/10 ->
25.89% for boundary, and 1/314 -> 1.50% overall. The all-selected sensitivity
counts 2,955 unread/unvisited eligible cases as errors: 2,956/3,269 yields a
91.26% upper bound. These descriptive conditional bounds do not certify selectively
unread cases, a sequentially stopped population or historical UTC. Actual verified
assignment changes remain undetermined. Counter 3,246/34,402; ledger 74; no resume.

### Local-reader memory safeguards

The strict-format experiments are stopped; the default local request helper is the existing
answer-first prompt. Experimental modules and frozen records remain available for review.
The [pinned runtime support receipt](../results/local_model_runtime_support.json) records the
bundled native `llama-server --help` definition: `--cache-ram N`, environment
`LLAMA_ARG_CACHE_RAM`, defaults to 8192 MiB and accepts `0` to disable the prompt cache.
The inspected native build is `6c01da627`, shipped with the pinned Ollama 0.40.16 package;
executable, implementation-DLL and help hashes are recorded. The original support inspection
queried only help/version metadata; the separately approved live smoke is reported below.

[RuntimePolicy](../src/asof/local_model_runtime.py) now defaults that environment setting to
zero, keeps the owned server on 11435, and freezes the setting in future runner contracts.
The [future launcher](../scripts/start_local_reader_server.py) verifies the package fingerprints,
requires an explicit `serve` invocation and writes a PID/policy receipt. The archived comparison
and control runners require that receipt; this does not authorize restarting an old experiment.
It is a native environment option, not a guessed Ollama JSON request field.

Future per-second owned-tree samples also append per-PID parent, creation time, process basename,
working-set/peak/private/commit bytes, CPU time, UTC/monotonic time and safe arm/UID/stage context
to ignored logs; observed starts/exits distinguish PID reuse. Prompt and answer payloads are
rejected from logging context. The existing aggregate memory stop remains.
Mock tests cover configured environment, launch arguments and process records. The
[2026-11-17 live review](../results/project_closure_review.json) completed three tiny invented
prompts in 77.67 seconds from owned-server start. The native log explicitly says the prompt
cache is disabled; 35 real per-PID snapshots observed a 3.90 GiB aggregate peak, one actual
model runner and successful creation-time-verified cleanup. The owned 11435 listener closed.
Compute used four threads; the backend separately reported 15 HTTP service threads, so this
is not a hard four-total-OS-thread quota. Active KV still used 512 MiB.
This closes the missing bounded smoke validation, not long-report memory safety, reader
accuracy, the old memory cause or an OS-enforced quota. Shared 11434 was untouched.
Subsequent startup-failure hardening requires the operator's root creation FILETIME
(`--root-created-filetime`) before any smoke call, so a failed initial native sample
still cleans the verified root. That extra error boundary was tested with mocks,
not another model run; the original three-call receipt remains unchanged.

### Official acceptance-clock documentation review

The [closure review](../results/project_closure_review.json) records eight metered official
documentation GETs, seven complete bodies and one declared-cap stop. The user explicitly
approved one same-manual 32 MiB cap amendment after its 23,159,215-byte size was known;
default metadata/document caps were not widened. Counter is 3,254 of 34,402, ledger 74.
No stopped accession job was resumed.

The PDS specification (May 2025) defines an acceptance **date**, not the needed field clock.
Current introduction/messages chapters and the 961-page historical Volume II version 60
(December 2021) document Eastern operating hours, filing-date cutoffs and acceptance notices.
Text/normalized field-name searches and targeted section review did not establish an explicit
historical timezone definition for the 14-digit acceptance field or certify JSON accuracy.
That is a limit of the reviewed evidence, not proof no definition exists anywhere.
Only the specification PDF was opened from the official ZIP; its two bundled 2025 `.dissem`
filing-example members were not opened, extracted or used. No financial observations were read.
Historical UTC, role/calendar qualification and complete cohort coverage remain unresolved;
no source clock, CIK, input table or financial result was repaired.

**2026-11-14 research plan:** the [research plan](RESEARCH_PLAN.md) records the proposed
experiment workflow and diagram, prerequisites for closing the data/label/power gaps, three
prospective study ideas and candidate data sources. Acquisition stays on free public sources for
now; paid and request-based options were researched from public documentation only. No source is
cleared, no account was requested, no vendor was contacted and no new run, sandbox or holdout
access occurred. A longer internal working draft is kept outside the public repository. The
existing queue, protocols and append-only ledger are unchanged.

### Cached timestamp recheck

The [cached-only recheck](../results/p0_cached_authority_audit_v2.json) covers all
21,502 metadata rows: 22 have an existing own-header cache and 21 have observed
header/index wall-clock agreement. Only 17 of the 17,389 sensitive accessions
have cached headers. Conditional on an Eastern header clock, 21 match the pair
column, seven match bulk, and one matches neither; counts overlap. These are
rechecked old caches, not new independent observations or global clock clearance.

The header parser now rejects short or overlong fields, ambiguous fall clocks and nonexistent
spring clocks rather than guessing; the P0 scenario planner reuses the same
round-trip logic while retaining both valid hypothetical folds. Three synthetic
regressions failed before the fix. Ordinary seasonal conversions are unchanged.
The [first audit attempt](../results/p0_cached_authority_audit.json) stopped at a
large cached index; the completed recheck keeps the 64 KiB read bound and marks
that index explicitly unread/unknown. Zero new SEC requests, timestamp repairs,
CIK remaps, score/price/outcome reads or ledger appends. **P0 remains blocked.**

### Proposed staged timestamp-authority pilot

The [offline plan](../results/timestamp_authority_plan.json) proposes field-clock
qualification first, then 48 metadata-only accessions across six exclusive pools,
including agreeing and insensitive records. All pools have at least eight candidates;
no roster was drawn. At most eight documentation requests plus 96 header/index
requests would fit the remaining 104 of the historical 150-attempt envelope.
**The plan itself made no requests and did not authorize them.**

Field-specific historical clock definitions and the allowed metadata observation
envelope must be settled first. The pilot would stop on blocks, redirects or
transport failures, with no retries, remapping or blanket time shift. The existing
client's retry/redirect behavior needs a tested scoped adapter before use.
A small stratified pilot cannot certify the full cohort; scale-up requires a
separate exact cache-miss inventory and budget. P0 remains blocked.

On November 16, a separately approved [documentation-only freeze](../results/sec_stage1_config.json)
and [tested strict adapter](../src/asof/sec_documentation.py) preceded one live request.
The [receipt](../results/sec_stage1_requests.jsonl) records HTTP 200, but the
page reached the 64 KiB read cap before completion. Its hash identifies only the
observed prefix, not a complete authoritative document. No clock definition was
qualified or quoted, and no retry, alternative URL, filing request or roster followed
([findings](../results/sec_stage1_review.json)). At that stop the cumulative counter was
**47/150**; the ceiling was not permission to spend the remainder.
This was a size-guard stop, not evidence that the SEC blocked access or that a clock
definition does not exist. Clock certification and the filing pilot remain blocked.

The separately approved [4 MiB refetch](../results/sec_stage1_refetch_config.json)
completed the same page in request #48: 69,025 bytes, HTTP 200. Its
[field review](../results/sec_stage1_refetch_review.json) found that acceptance-time
format, clock/time zone and historical applicability are **not defined on this page**.
The page's bulk-update schedule is not an acceptance-clock definition.
The counter is now **48/150**, with no other URL or filing request made.
At that point additional sources and the filing pilot still required a new decision.

### Conditional 48-filing pilot, not clock certification

The subsequent owner-approved [roster](../results/header_pilot_config.json) sampled eight
accessions from each of six exclusive metadata pools with seed 2026111601. The
[reconciled report](../results/header_pilot_reconciled.json) compares cached API-derived
and bulk representations with header times **assuming an Eastern header wall-clock**.
Stage 1 did not document that clock; this is conditional evidence, not a source correction.

| Pool, eight accessions each | Both match assumption | API/pair only | Neither | Unread clocks |
|---|---:|---:|---:|---:|
| CIK disagreement | 8 | 0 | 0 | 0 |
| Calendar boundary or clock issue | 8 | 0 | 0 | 0 |
| Winter source disagreement | 0 | 8 | 0 | 0 |
| Summer source disagreement | 0 | 8 | 0 | 0 |
| Agreeing, assignment-sensitive | 8 | 0 | 0 | 0 |
| Agreeing, assignment-insensitive | 6 | 0 | 2 | 0 |

All 48 own index/header wall clocks agree. Relative to the conditional header UTC,
bulk is five hours later in the winter-disagreement pool and four hours later in
summer; both stored sources are four hours later for the two neither-matching
insensitive records. Internal agreement or insensitivity therefore does not certify
a clock. Eight headers contain multiple CIKs; observed roles were retained without
choosing a new issuer/security mapping.

The pilot used **92 new requests and four pinned cache hits**, reaching **140/150**.
All 96 resources were read within the bound. The initial parser conservatively
marked duplicate SGML/rendered clocks unknown; that [original result](../results/header_pilot_status.json)
and all receipts remain unchanged. A synthetic regression failed before a parser-only
fix; only pinned bytes were reparsed offline, with zero further requests.
No timestamp repair, CIK remap, correction release, portfolio assignment or financial
rerun occurred. Equal-sized stratified pools cannot certify the full cohort or supply
an unweighted population error rate. **P0 stays blocked pending review**; the ten
requests left under the ceiling are not permission to acquire more data.

### Approved offline P0 assignment planner

**2026-11-14: owner selected `p0_first`.** This permits a bounded cached-metadata
screen, not another SEC audit, timestamp repair or empirical evaluation. New
APIs in [p0.py](../src/asof/p0.py) and the
[planner](../scripts/plan_p0_assignments.py) construct R1-style CORRECT/LATE/EARLY
candidate instants from both stored source clocks. Internal agreement is never
treated as authority.

- Named `America/New_York` historical rules; LATE conversion is self-consistent
  at the corrected candidate, not today's offset. Valid fall folds remain
  distinct; nonexistent local clocks are flagged, not shifted.
- Registered nominal 16:00 ET entry uses cached French **date fields only**.
  This is not an independently certified venue/early-close calendar.
- Joint development eligibility and formation freshness use the current runner's
  signal window plus `[close-365d,close)`; exact latest-record possibilities
  preserve stable input order on ties. Include uncertain competing records, not
  merely raw timestamp disagreements or possible winners.
- Prior `[focal-120d,focal)` and future `(focal,focal+365d]` checks vary both
  clocks. These are explicit R1 **metadata** operators, not changes to frozen
  H6 label definitions.
- Input is the original cached H0 signal metadata/order and matching audit
  comparison sidecar. Read only CIK/accession/form/times, never signal scores,
  stock prices/returns or outcomes. Mismatch/duplicate/missing inputs fail
  explicitly; no silent remap/drop.

The independent-accession candidate model is a conservative screening scenario,
not a probability model or a proven description of correlated source errors.
The per-CIK 120/365-day pair screen uses **H0 filing metadata**, not H5 event
filters or independently complete H4/H6 amendment/outcome envelopes. It cannot
clear dated shares/SIC/acquisition-control clocks, co-registrant identity or
source accuracy.

Expected outputs: `results/p0_assignment_plan.json` with aggregate counts,
resource/source lineage and explicit limits; ignored local
`data/p0_assignment_queue.parquet` with accession candidates/context reasons.
An insensitive record is **not certified**. Sensitive counts are possible
assignment changes, **not actual look-ahead size or revised portfolio results**.
No correction is written and no trial row is appended.

Run with OPENBLAS/OMP/MKL/NUMEXPR thread flags set to 1:

```powershell
python scripts\plan_p0_assignments.py
```

The runner checks <=780 CPU seconds and 1 GiB peak RSS before/after bounded blocks,
reserving two minutes of the approved 15 CPU-minute batch envelope for tests.
These are cooperative resource checks, not an installed OS sandbox/quota.
Load is checked before launch; a ceiling or discrepancy preserves an incomplete
report, raises and does not certify an older queue output. No request budget
is consumed. Pre-execution validation passed **51 focused tests in 2.37s** and
configured changed-file Ruff. Execution and final validation receipts are
recorded separately, not implied by these tests.

#### Offline P0 planner execution receipt

The screen completed from clean source
`45d0c441d9c13a505cb18916ce036d4745cc04fd`, with **zero requests, input
repairs, score/price/outcome reads or trial appends**. Results:
[p0_assignment_plan.json](../results/p0_assignment_plan.json); detailed
candidate/accession context stays in ignored `data/p0_assignment_queue.parquet`.

| Count | Observed metadata screen |
|---|---:|
| Full cached H0 rows / stored development rows |21,502 / 16,226 |
| Sensitive accessions, union of all screened reasons |17,389 |
| Sensitive records whose stored source clocks agree |17,230 |
| Sensitive accessions in stored development |13,152 |
| First nominal-close-sensitive accessions |16,762 |
| Formation-eligibility-sensitive accessions / record-month instances |1,029 / 1,041 |
| Potentially changing latest-signal firm-month instances |792 |
| Joint latest-selection context accessions |2,233 |
| Prior120-day uncertain ordered metadata pairs |145 |
| Future365-day uncertain ordered metadata pairs |1,399 |
| Potential future365 windows beyond observed cutoff |10,349 |

Counts overlap; do not sum reason counts as unique affected filings. Source
agreement does not exempt a record. The broad independent-accession error model
is an **over-approximation of possible decisions**, not 17,389 verified errors or
an estimated probability of look-ahead. In particular, 792 is not a changed
portfolio/P&L count. The complete source/identity/price/filter/label pipelines
were not evaluated.

This is not a small enough universal verification queue to certify with the
remaining 104-request envelope: a blanket small header sample cannot establish
all clocks. A later audit must qualify accession-level cached authority and
the error-model scope, plus an explicitly bounded retrieval design. No request
permission or generic correction follows from this result.

The runner also counted 404 CIK disagreements without remapping either source.
Prior/future window counts compare **H0 filing metadata pairs**, not H6 formal
records or observed outcomes; incomplete envelopes are not negative labels.
The preserved tie rule has zero exact latest-timestamp ties in baseline metadata
here, but synthetic tests cover them.

Resources: **13.265625 CPU seconds / 14.625 wall seconds / 209.77734375 MiB peak
RSS**, below the reserved 780-second/1GiB runner limits. Pre-screen shared load 8%;
cooperative budget checks do not create an OS sandbox. Lineage pins the two
metadata inputs and the queue hash. French calendar date fields are reused
under the existing cache contract; their raw-file hashes are not included in
this new report, so it is not a fully isolated snapshot freeze or certified
exchange calendar.

Validation now performed with BLAS/NUMEXPR flags 1:

```powershell
python -m pytest -q tests\test_p0.py tests\test_p0_assignment_plan.py tests\test_timeutil.py tests\test_timing.py tests\test_p0_acceptance_audit.py
python -m pytest -q
python -m ruff check src\asof\p0.py scripts\plan_p0_assignments.py tests\test_p0.py tests\test_p0_assignment_plan.py
```

**51 focused tests passed in 2.37s; 253 full-suite passed in 39.64s**, with two
inherited synthetic rank-deficiency warnings; Ruff passed. These checks prove
the candidate/assignment arithmetic and error paths under declared assumptions,
not real clock authority. Original signal/bulk/share hashes match recorded
lineage; ledger remains 74 rows, P0 HTTP receipt 46 requests. No referee or empirical
runner rerun. P0 and Batch C Part 2 remain blocked; the other three proposed
offline batches were not selected or started.
The persisted report and queue reconcile on accession uniqueness, counts and
queue hash; all **116 local links/anchors** in the updated documents passed.

Generated from EDGAR full-index files (2011–2026), SEC's current CIK-ticker map, and the XBRL
frames API (`dei:EntityPublicFloat`). Having a current ticker is an upper bound on whether a free
source has the firm's price history. Firms acquired, merged, taken private, or failed since then
are usually missing.

### Offline cost, run-contract and measurement fixes

**2026-11-14 owner request: implement the three remaining offline proposals.**
These changes prepare safe evaluation; they do not run a model, repair P0,
adopt a source, annotate gold, train or evaluate a strategy.

#### Cost receipts

[costs.py](../src/asof/costs.py) remains separate from frozen portfolio costs.
Existing long-short calls keep their behavior; an explicitly declared
`exposure="long_only"` reports borrow **not applicable**, rather than requiring
unsupported historical shortability. Nonzero short-borrow costs contradict
long-only and fail; fill evidence and financing costs still apply.

`reconcile_turnover` compares observed absolute traded notional Q with
T=Q/(2*capital), without renormalizing the supplied frozen turnover. The T07
fixture (capital 10,000, Q 2,000, half-spread 4bp, frozen T .2) preserves frozen
spread cost 1.60 versus observed 0.80 and reports **basis_mismatch**, not 1.60+.80
or a silently halved frozen T. Numerical equality tolerance is arithmetic,
not an economic acceptance threshold.

`reconcile_net_return` requires a declared distribution basis. The component
ledger still reports all cash costs; net P&L deducts distributions only if they
are not already in gross total return. Toy spread 4 + fees 1 + borrow 15 + financing 10
+ distributions 50 gives full drag 80; total-return gross -50 deducts only 30 more,
not another 50. Unknown basis or unavailable components returns explicit
unavailable/null fields. The older component break-even field retains its
caller-basis contract; use the new basis-aware receipt for netting.

#### Frozen run-contract checks, not a launcher

[studies.py](../src/asof/studies.py) now provides typed RunRequest, RunPermit,
RunBudget and validation/receipt records. They check exact request identity,
source/config/input hashes, finite budgets, expiry, scope, completed
prerequisites, required gates, access restrictions and development cutoff.
Synthetic permit receipts cannot qualify real work. A validation is bound to
its exact request and cannot be reused to expand another request.

The design-readiness helper remains distinct: execution-contract checks require
**completed**, not merely ready, prerequisite studies. `contract_complete`
means supplied fields/assertions passed validation, **not authentic permission,
physical source verification or proof of an enforced sandbox**. An external
supervisor still has to verify receipts and enforce access/quotas.

`contract_dry_run` compares supplied synthetic usage/metrics and preserves
partial failures and simulated nulls. It launches no callback, process, worker,
network or filesystem operation. A missing output is not zero; budget excess,
expired/mismatched permit and execution failure cannot become successful
evidence. It cannot declare real scientific support.

#### Measurement-only scoring

[measurement.py](../src/asof/measurement.py) evaluates supplied exact claim-ID
sets on paired cases with issuer/time/split and evidence metadata. It is not
a semantic labeler or source-verification service.

- Only complete, declared-verified gold enters scoring. Unknown, unverified
  and incomplete gold have separate counts and never become negative labels.
- Abstention is distinct from an emitted empty prediction: it reduces coverage,
  retains missed gold claims as false negatives and is not an exact match.
- Precision/recall with zero denominator is null, not 100%. Report prediction
  coverage and both unconditional/selected exact-match accuracy together.
- Duplicate cases fail. Explicit half-open chronological boundaries and
  issuer-disjoint partitions are checked; no dates or split inferred.
- Evidence refs and verification flags are caller declarations, not independently
  checked quotes or annotation independence. Split hygiene alone does not prove
  a model's pretraining or historical availability is clean.

The real 60-pair roster/gold audit remains P0/human-protocol blocked. No real
labels were generated or current/future outcomes read by these helpers.

#### Validation and reproducible synthetic receipt

Before the demonstration, **60 focused tests passed in 3.20s** across costs,
studies, measurement, prior independent oracles, D4 and labels. Configured new-file
and selected changed-file Ruff passed. Final full-suite/run receipts will be
recorded after execution; this is not evidence those steps already ran.

The bounded [fixture script](../scripts/check_offline_contracts.py) writes
`results/offline_contract_fixtures.json` from invented unit values only. It
demonstrates blocked request expansion, missing metrics, usage overrun,
preserved partial errors, a simulated null and cost/measurement reconciliation.
It is not real-label accuracy, a training experiment, permission to access
financial data or a real sandbox test. No ledger row is appended.

The demonstration is now complete from clean source
`db2a19f4b820677b8a61b0f4e7d2e273d917837c`:
[offline_contract_fixtures.json](../results/offline_contract_fixtures.json).
All five contract scenarios matched their expected states. The component
ledger reports toy cash costs 80 while total-return P&L deducts only 30 additional
costs; the mismatched turnover receipt retains 1.60/0.80. Two invented measurement
cases give precision 1, recall/coverage .5, showing why selective correctness alone
is inadequate. These are **fixture arithmetic, not measured real performance**.

Final validation: **262 full-suite tests passed in 29.94s**, with two inherited
synthetic rank-deficiency warnings; configured new-file and selected changed-file
Ruff passed. The initial 87% shared CPU load delayed long validation; final
demonstration/full suite began at 24% with single-thread flags. No study, model,
training or source-acquisition job was started.

Original signal/bulk/share hashes and prior tracked results remain unchanged.
Ledger 74 rows, P0 HTTP receipt 46 requests, no input repair or holdout exposure.
These helpers do not clear P0, source/economic/annotation/inference gates. The
separate [free-benchmark research](RESEARCH_PLAN.md#free-benchmarks-for-testing-measurement-on-real-data)
identifies possible real component tests, but release/rights/overlap, native
adapter, frozen baseline and acquisition/run permission remain prerequisites.
All **128 local links/anchors** in the updated documents passed checks. The
fixture's source lineage is clean and previously tracked study outputs are
unchanged. No new scientific finding is inferred from these engineering fixes.

The float-bucket coverage table is the historical audit that motivated D1, not a
bucket table regenerated during this continuation. Fresh reconstruction,
runtime/lineage checks, and the referee's distress contrasts are identified separately.

Rebuild the quarterly index with `python scripts/master_index.py`. It starts in 2011 and
stops at the current UTC quarter, reusing the EDGAR client's per-URL cache on retries.
Quarters are streamed into `data/master_index_2011_<current year>.parquet`; a failed request
leaves any previous completed output unchanged. This index contains filing metadata, not
prices, and does not open a return holdout.

When `data/raw/bulk/submissions.zip` exists, the H0 `filings` stage reads missing
firms directly from it, including every form, historical page, and stored acceptance
field. The field's true instant is not certified by import or by a Z suffix.
It uses the individual submissions API only for firms absent from that archive.
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

**Queue snapshot v0.5 (Batch E robust-test verification; P0 still blocked); stable IDs CL-P1 through CL-P6.** Lead decision
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
| **Lead-D3b/c/d** | Resolved prospectively in Batch A below:20-session first-kept strict overlap, other-firm strictly-prior residual fit, dated SIC/unknown abstention. Legacy paths unchanged; empirical integration still requires registration, dated inputs, support parameters and run permission. Actual fill feasibility remains unproved. |
| **Lead-D4** | Prospective conjunction/supplementary interfaces implemented in A1. Actual project DSR/PBO remain unavailable; registered rules/N are not weakened. |
| **Lead-D5** | Only the fixed A5 synthetic allocation/budget was released and executed; future study economic effects and any further simulation remain registration/approval decisions. |
| **Lead-D6** | Future evidence-status/observation/amendment principles resolved; A2 validator implemented. Real observation evidence and human protocol remain blocked; frozen labels unchanged, discrepancy disclosed in D10. |
| **Lead-D7** | Open: human protocol and claims/endpoint annotation time. |
| **Lead-D8** | Ordered prospective registry implemented in A4; actual study estimators/margins fixed at registration, no outcomes authorized. |
| **Lead-D9** | Future component normalization/helper implemented in A3; actual capital, borrow, fill and cost evidence remain unavailable/unapproved, frozen cost path unchanged. |

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

##### Batch A completion evidence (offline, not project inference)

**A1-A5 completed in the bounded offline scope.** Tested source plus the
pre-execution seed/allocation were committed locally as `196d1df`.
The supplementary manifest and calibration both identify that **clean source**
revision and its runtime. No remote push/tag, empirical study, ledger append,
vendor/human contact or holdout access occurred.

- [`trial_manifest.json`](../results/trial_manifest.json): all56 ledger attempts
  retained; ledger bytes compared equal before/after generation. Registered
  distinct-config counts exactly match the unchanged `ledger.n_trials`: ENGINEERING1,
  H0=10, H1n=10, H4=6, H5a=1, H5b=1, H5c=2, H6=2. These include everything
  originally logged under each hypothesis, not an independence estimate or a
  reduced effective N. Classified28scientific /22repeat_vintage /4engineering /
  2timing; unknown0 for this ledger. Recognized legacy-purpose classification is
  disclosed as inferred, not proof of scientific validity. Historical F2/F3 and
  other limitations persist; no failed/invalid row is erased or promoted.
- Project DSR/PBO remain **unavailable**, with persisted aligned-series missing;
  no return matrix is reconstructed from summaries, no families silently pooled
  and no statistic computed on an attractive subset.
- [`synthetic_inference_calibration.json`](../results/synthetic_inference_calibration.json):
  **complete execution, not a passed calibration**. Exactly2,000attempts over all14
  prespecified streams;1,994finite statistics and6nonfinite panel statistics.
  No redraws; valid denominators198/196 are explicit for the two panel cases.
  Their causes are recorded as nonfinite statistics, not retrospectively explained
  by an unexecuted covariance diagnostic. No warnings were captured in this run.
- **12.625CPU seconds,13.797wall seconds,207,020,032bytes (197.43MiB) observed OS peak
  resident memory**, below900CPU seconds/1GiB; numerical thread settings1. Fresh
  pre-run machine check reported37%CPU load, about38.4GiB free physical memory and
  no matching heavy Python research job. No AfterEvidence heavy-resource permission
  or general scheduler was inferred from this light release.

Rates below are synthetic |t| rejection frequencies. Normal two-sided reference
rates at2.0/3.0/3.2 are **4.5500% /0.2700% /0.1374%**. The last column is plug-in
Monte Carlo SE for the3.2 frequency in **percentage points**; the JSON includes
counts, denominators, nominal rates and SE for every threshold.

| Synthetic case | Finite / attempted | Rejection% at2.0 /3.0 /3.2 | MCSE at3.2 (pp) |
|---|---:|---:|---:|
| iid null,T18 |150/150|26.67 /13.33 /10.67|2.52|
| iid null,T28 |150/150|20.67 /8.67 /7.33|2.13|
| AR0.3 null,T18 |150/150|32.00 /18.67 /16.00|2.99|
| AR0.3 null,T28 |150/150|18.67 /7.33 /6.00|1.94|
| scaled-t3 null,T18 |150/150|28.67 /14.67 /12.67|2.72|
| scaled-t3 null,T28 |150/150|12.67 /6.67 /6.00|1.94|
| factor exposure null,T18 |150/150|30.00 /14.67 /12.00|2.65|
| factor exposure null,T28 |150/150|18.67 /5.33 /4.00|1.60|
| iid power0.5SD,T18 |100/100|69.00 /46.00 /43.00|4.95|
| iid power1.0SD,T18 |100/100|97.00 /90.00 /88.00|3.25|
| iid power0.5SD,T28 |100/100|77.00 /55.00 /50.00|5.00|
| iid power1.0SD,T28 |100/100|100.00 /100.00 /100.00|0.00|
| panel null,no year shock |198/200|10.10 /3.54 /3.03|1.22|
| panel null,year shock |196/200|10.20 /3.06 /2.04|1.01|

**Interpretation:** these fixed short-series/few-cluster synthetic designs do not
support treating the normal-reference bars as well-calibrated rejection levels.
Power is reported together with that over-rejection, not as evidence the procedure
is reliable or a project signal works. A plug-in SE of0 at observed100% is not
certainty about true power; rare nominal tails are poorly resolved by100-200draws.
No threshold, source estimator, seed, allocation or historical conclusion was
adjusted to make this result better. Any inference-method alternative needs its
own accepted design and bounded authorization; no additional simulation budget
was created.

Evidence commands after source commit:

```powershell
.\.venv\Scripts\python.exe -m asof.trial_manifest
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"
.\.venv\Scripts\python.exe scripts\calibrate_inference.py
```

Final artifact checks verified all14allocations, requested/attempted totals,
finite+invalid reconciliation, per-threshold denominators and unchanged registered
counts/ledger. They are output checks, not a new experiment or a second set of
replicates. Existing reports, raw-data cutoffs, D3a planner and all failures remain
identifiable. **Next:** Lead reviews this evidence and the queued Batch B scope;
no human/vendor contact, source access, empirical integration or reserved
authorization follows automatically.

##### Independent oracle cross-check R1 (synthetic only)

The later authorized cross-check read **CL-ORACLES-20261113-R1 — Independent
correctness pack**, completed Research response
`aff80bff-cc5c-464e-8a10-f2493581179e`, in all five pages in the
[existing Research chat](agent-host-session://ahp-session/951260e2-fb65-4741-bc73-7ba69cbfc778?chat=8b3fbed7-849c-4ebb-8c14-aa755f6b3045).
This is independent proposed review material, not owner approval, real gold,
source entitlement or permission to change frozen definitions.

Initial tests of22applicable synthetic cases gave **5failures /17passes**.
The fixes below concern only offline helpers; **no Batch B stopped step,
manifest generation on project data, empirical study, calibration, source request,
annotation or referee was rerun**.

| Oracle / result | Correction or explicitly retained boundary |
|---|---|
| P3-D01..D10 | All ten formal-H1 conjunction cases are encoded in [test_independent_oracles.py](../tests/test_independent_oracles.py). Genuine D07 bug: a known failed assumption was masked by missing TF-IDF. Known failure now dominates unknown evidence; missing alone still yields `unavailable` (oracle `undetermined`). Directed event t negates raw increasing-change t. API `supported` means only the supplied conjunction predicate, not global scientific acceptance. D09 monthly3.1/event3.3 passes with all other gates; D02 3.1/3.1 fails. Supplementary Holm neither rescues nor replaces it. |
| P3-M03 | Missing purpose is now `unknown`, not inferred scientific from a known hypothesis label and not engineering. Registered N still counts every distinct logged config independently of this annotation. The real74-attempt manifest is **not regenerated** here: its earlier inferred-purpose partition remains historical evidence pinned to its generator, not certification by this correction. |
| P3-M09 | Before overwriting an existing manifest, the CLI checks its persisted registered counts and attempt count. A reduced/incomplete ledger export raises and leaves the previous manifest bytes intact. The hypothetical raw2/distinct2 versus registered3 case preserves3, rejects reconciliation, and does not compute statistics. The pure in-memory classifier without a supplied receipt cannot infer omitted history; it must not be used to reset an authoritative registered count. |
| P3-M01/M04/M05/M06/M08 | Existing/new tests retain duplicate and changed-vintage attempts/lineages and registered counts, preserve failures/missing outputs, reject endpoint pooling and keep short PBO blocked. `repeat_vintage` is an attempt annotation, **not proven equivalence**, permission to choose latest, or an independence estimate. Availability's `available` plus `inputs_only_not_computed` maps to the oracle's conditional `eligible_not_computed`; it is not a DSR/PBO result or independent proof of a persisted file. |
| P3-M02/M05/M07 interface limits | The helper prioritizes unavailable/incomplete-family reasons; the pack sometimes labels PBO not_estimable with an additional family blocker. Both disallow inference. A single supplied matrix cannot certify an external required-calendar receipt or undo a caller's prior silent intersection. Such receipt reconciliation remains an integration requirement; no zero filling/calendar intersection was introduced in this cross-check. Batch B DSR remains stopped. |
| P5-R01/R02/R03/R04/R05/R06/R07 | Adversarial tests reject missing rights/authorization, bad formal-H1 identity, missing two-ended links or calibration. R02 adds an explicit optional `requested_outcomes` check: B0 measurement cannot authorize requested returns. R04 now blocks X1 presented under H1/H1n instead of its distinct study. A supplied `run_ready=true` does not bypass required gates. No study executes. |
| P5-R08 boundary | The API has no coverage-ratio-to-qualification conversion. `qualified_sources=True` must mean independently supported source qualification, not merely0.81 coverage. The checker validates declared gates, not the truth of source receipts; rights/identity/payoffs remain unresolved. No test fabricates those receipts or declares F2 cleared. |
| P4-E01..E05 | Synthetic missing/zero NI, missing impairment, in-window early positive and incomplete follow-up cases pass. Added zero-NI4->0/100assets yields decline1 and dROA-0.04 in a wholly mocked H4 panel. A censored200day envelope keeps null, not an observed negative. No real label/data changed. |
| P4-C01..C14/E06 | The invented semantic pairs are **not implemented claim-labeling performance tests**: no numeric/entity/modality semantic classifier or real adjudicated gold is supplied here. Administrative versus substantive endpoints remain separate; historical broad10-K/A and prior10-Q/A discrepancy remain as documented. Do not manufacture a substantive endpoint or precision/recall score from this pack. D7/human protocol still blocked. |
| P6-T01/T02/T03/T05/T06 | Hand-derived dollar costs and break-even cases pass with the **declared** half-L1/gross-traded convention and supplied incremental cashflow basis. The short toy has30execution/carry cost plus50distribution debit,80cash drag. Already-distribution-inclusive gross P&L deducts30, not another50. Unknown borrow/fill stays unavailable. No actual trade, annual-rate inference or frozen cost change. |
| P6-T04/T07 interface limits | Long-only borrow=`not_applicable` is not represented by the current bool/unknown borrow evidence field; do not forge availability to clear it. T07 preserves the two input-basis results1.60versus0.80; a **joint** observed-Q/frozen-T mismatch flag needs that additional receipt/interface. It is not automatically implemented by one-basis arithmetic. No silent halving, addition of both spread lines or universal claim about the existing frozen turnover basis. |
| P2-B01..B04 | The independent scheduled-overlap/other-firm/SIC expectations agree with the recorded future contracts, but those future overlap/peer/SIC algorithms are not implemented or evaluated by this turn. The separate D3a planner and all old runner defaults remain untouched. No minimum support threshold or new price input inferred. |

Final focused command, numerical threads1:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_independent_oracles.py tests\test_trial_manifest.py tests\test_studies.py tests\test_costs.py tests\test_labels.py tests\test_h4_development.py
```

**56passed**; configured changed-file Ruff and selected `E4,E7,E9,F` passed.
This is not a fresh full-suite179pass or referee result. The host initially
reported88%CPU load; no heavy job, simulation, model or full-suite rerun was
launched. All synthetic receipt/ledger writes use temporary directories.
The original real ledger, manifests, study outputs, rosters and referee remain
unchanged. F7/F8 source/numerical blockers remain unresolved; the correction
does not reopen DSR or the holdout. Only the single authorized further evidence
handoff to Lead follows; no other chats, schedules or acknowledgment loop.

##### Batch B bounded development plan (recorded before draws/reruns)

Batch B releases exactly: B1 cached-factor impact inspection and one unchanged
H4 test run after D11; B2 output-only monthly-series persistence and one validated-
snapshot H0 run with exact legacy-summary comparison; B3 metadata-only blinded
rosters/templates; B4 SEC-only candidate identity/exit oracles; B5 full single-thread
tests, selected lint and bounded referee comparison. No held-out observations,
vendor/key/account/paid access, human contact, push, tag or publication is released.
Check load before commands expected over one minute and defer competing heavy work.

**Roster seed20261113, fixed before selection.** Independent `SeedSequence`
spawn keys0=claims,1=endpoint feasibility,2=SEC candidates. Sort candidates by
CIK/acceptance/accession; sample eligible issuers uniformly without replacement,
then one eligible row per sampled issuer. Preserve shortfalls, no replacement
from favorable outcomes. No signal-value, price, return, model-score or endpoint-
value column is used to select these rosters.

- Claims:30existing10-K pairs then30existing same-quarter/year-ago10-Q pairs,
  no issuer repeated across the60. Current acceptance2023-01-01..2024-06-30UTC.
  Use the existing pair's previous accession; verify document/form/time metadata.
  10-Q year-ago metadata uses the existing340-390day report-date rule, not a
  newly invented calendar-quarter filter. Existing current-ticker conditioning
  is disclosed rather than called a new historical-universe sample.
- Separate endpoint20case feasibility: five each in H4 next-annual-report metadata
  available versus absent in the **2012-2018 selection envelope**, and H6-style
  regular filings whose nominal365day follow-up ends inside versus outside that
  envelope. Use the existing H4 issuer sample, dates/forms/accessions only.
  These categories are neither endpoint labels nor independently verified complete
  observation; a report outside the selection envelope is not a nonexistent report.
- SEC-only P1: target four cases in each original stratum. Continuing and multiple-
  class candidates come from development10-K metadata; acquisition candidates from
  Item2.01 and distress candidates from Item1.03. Metadata cannot distinguish cash
  from stock consideration: preassign candidate slots and preserve contradictory/
  unknown text evidence rather than redraw to fill a stratum. Historical ticker
  reuse is infeasible from this metadata alone; report it, do not substitute.
  All event acceptances2023-01-01..2024-06-30, evidence filings accepted<=2024-07-31.
  At most300actual SEC HTTP attempts, including retries, at<=2requests/sec through
  the cached project client/contact user agent. No provider/price request. Exact
  consideration is not inferred from missing quotes; text hits are candidate
  evidence, not independent gold or terminal-payoff completeness.

**B2 diagnostic scope fixed before returns are persisted:** retain all17/18
original months per configuration. Within each existing H0/H1n family, align the
current six configurations by calendar intersection only for a separately labeled
development DSR diagnostic. Use the unchanged registered per-hypothesis N, not
six independent strategies, and disclose that SR variance is estimated from this
current-vintage slice with identical sensitivity streams. Full historical-family
DSR remains unavailable while invalid/older aligned streams are absent.
PBO remains not_estimable below32aligned months. Do not feed raw descriptive
event panels into the required neutralized co-primary: D4 reports unavailable
where that registered evidence is missing; H1n is not formal H1. No support claim.

##### Batch B completion and stopped gates

This is a **mixed completion**, not an all-gates-pass claim. B1/H4 and B2/H0 each
ran exactly once from source checkpoint `fb0a333`; no source/config/date/scoring
change or empirical retry followed discrepancies.

| Step | Evidence / current status |
|---|---|
| B1 factor impact | [Factor audit](../results/batch_b_factor_audit.json):15,375permitted-prefix rows,1963-07-01..2024-07-31; zero missing/nonfinite values in all7columns. Both daily archive fingerprints and the recorded market manifest matched. No CAR missing-factor parity effect for panels using this vintage; no certification of earlier unfingerprinted laptop vintages or scheduled-calendar completeness. |
| B1 H4 | D11 logged/committed before run.399current-NI-missing rows all lack ROA and fail the existing control gate. All sample counts/means matched;12coef/t fields changed, maxabs6.466e-13. **Exact comparison stopped**, numerical cause not adjudicated. [Impact](../results/batch_b_h4_impact.json). |
| B2 H0 | One validated-snapshot run appends12existing-config attempts and persists210monthly net/gross rows with month labels. Net/gross/alpha/event summaries exactly matched; neutralized IC/IC-t differ in16stored fields (four unique metric paths). **B2 stopped without DSR**, no tolerance/tie/rounding or thread retuning. [Comparison](../results/batch_b_rerun_comparison.json), [blocked diagnostic](../results/current_vintage_diagnostics.json). PBO not_estimable below32months; required neutralized co-primary remains unrun. |
| B3 claims | **Stopped before draw:** among16,226candidate pairs,305CIK and124acceptance fields disagree with bulk metadata, with0missing accessions/0form differences. Counts may overlap. [Examples/counts](../results/batch_b_claims_roster_blocker.json); [claims roster](../results/claims_audit_roster.json) has0cases/blocked status and [template](../results/claims_annotation_template.csv) header only. No preferred resampling/remapping. |
| B3 endpoints | Independent fixed stream1 produced20unique-issuer metadata cases,5in each prespecified envelope/report category; [roster](../results/endpoints_audit_roster.json) and [blank template](../results/endpoints_annotation_template.csv). No NI/impairment/quiet/formal-endpoint values selected or annotated; envelope categories do not certify label observation completeness. |
| B4 SEC-only | [Candidate evidence](../results/sec_identity_oracle.json):20preselected slots,16actual HTTP attempts, project limiter<=2requests/sec and cap300.12partial textual supports/8unresolved; **zero independent gold/terminal-payoff certifications**. Ticker-reuse stratum has4infeasible slots, not replacements. Cash/share mentions come only from the selected Item2.01 text; no provider, prices, exact terminal values or F2 clearance. Raw documents stay in ignored cache; only short evidence quotes/accessions/URLs retained here. |
| B5 local validation | Full `pytest -q` with numerical threads1: **179passed,2existing synthetic rank-deficiency warnings**. Selected Ruff on8Batch B Python files passed; prior new-file configured lint passed. No new packages. The [validation record](../results/batch_b_validation.json) contains the actual bounded referee comparison and command/result provenance. |

CI was **not** rerun (no push). Existing model/extraction/H5/H6 results are inherited,
not rerun by Batch B. All56pre-Batch-B ledger lines remain unchanged, with6H4 and
12H0append-only attempts:74total, classified as repeat_vintage for the new attempts;
registered distinct-config counts unchanged. The supplementary manifest's
unavailable-inference fields reflect no series supplied to that classifier, not
denial that the new current-only JSON series exist. Full historical aligned series
and exact B2 reconciliation remain missing requirements.

Machine checks before H4/H0/SEC/full-tests reported4%/9%/21%/6%CPU respectively
and no competing named research workload. The initial Batch B check reported51%;
no process was terminated. No new simulation budget was consumed. Referee runs
only if expected under15minutes, with a900second timeout and HTTP disabled; its
actual result is recorded independently. Technical PASS, if reported, **does not**
clear F7/F8. The referee protocol was not changed after observing those blockers.

Interpretation and next owner/Lead decisions: adjudicate the CIK/acceptance sources
and numerical/near-tie provenance without changing rules to make results match;
decide any later bounded diagnostic before rerunning affected work. No source was
declared authoritative or silently substituted. P1 licensing/identity/payoff and
P4 human/observation gates remain unmet; no labels were assigned, no vendor/human
contact made, no key/account/spend/push/tag/publication authorized. Holdout stays
sealed and prices<=2024-07-31. See [F7/F8](FINDINGS.md#f7-h0-pair-metadata-disagrees-with-the-bulk-filing-identityacceptance-metadata).

##### Batch C Part 1: P0 integrity verdict — STOP

**P0 BLOCKED; Parts 2-3 not started.** The universal JSON-"true UTC" claim is
withdrawn, not silently repaired. [F9](FINDINGS.md#f9-p0-acceptance-time-authority-is-not-uniformly-certified-by-json-z-fields)
and the [authority packet](../results/p0_acceptance_authority_audit.json) distinguish
raw source disagreement, directly checked header/index observations, conditional
column substitution and still-unknown global impact. No production timestamp,
CIK, universe, share/price snapshot or ledger row was changed. No H0/H4/H5/H6,
near-tie, DSR, manifest-refresh or calibration run followed the P0 stop.

| P0 check | Observed evidence / limitation |
|---|---|
| Full H0 signal metadata | 21,502 rows, 165 timestamp disagreements: 105 at +4h / 60 at +5h (bulk minus pair). The recorded development slice has 16,226 rows and 124 disagreements: 75 at +4h / 49 at +5h, matching the seasonal ET offset. [Raw bulk sample](../results/p0_raw_bulk_sample.json) already contains shifted Z strings; not merely a pandas display conversion. |
| Own-header/index sample | 26 planned across differing/agreeing, EDT/EST, several submitter prefixes and historical H4 metadata; 23 attempted. There are 22 header/index wall matches: 21 ET-derived UTC instants match pair, 7 match bulk. All 14 sampled differing cases favor pair. One agreeing case (`0000003545-24-000034`) is 5h late in **both** internal paths. The first historical H4 header URL returned 404 and stopped network sample expansion; all four historical-H4 checks remain incomplete. |
| Authority/timezone sources | Official PDS specification section 2.1 calls Acceptance Time EST; the 2023 SEC rule describes EST/EDT currently effective (both indexed official PDF text, not newly parsed PDFs). SEC ET operating-clock page read directly through project client; raw header/index wall fields retrieved directly. No universal JSON-field correctness follows; no new PDF dependency installed. |
| Source paths | 118 original cached API records inspected: 112 root-recent / 6 historical-page, all equal stored pair and not bulk. Six other differing CIKs lacked that API cache. Cache/value consistency is not a recorded ingest-branch receipt. Both API and bulk paths populated the DB; path provenance was not persisted per row, and source disagreement is nonuniform. |
| Actual versus conditional impact | 22 successful header/index cases have 0 pair-to-ET-header first-close/eligibility changes and 0 **sample-local** latest-filing changes. This is **not** a global zero-look-ahead finding or a full-cross-section selector check. Pair-to-bulk substitution instead changes 22 development closes / 2 latest-signal firm-month choices (31 closes for full signal table); those are conditional alternatives, not authoritative correction impacts. Price/size filters, scores, weights and returns were not evaluated. |
| Other event tables | 49,821 H5 DB/bulk-overlap events: 235 time disagreements, 16 conditional close changes. 222,729 older 2012-2018 overlap rows: 5,637 time disagreements in both directions, 939 conditional close changes and 3 UTC-year changes. All 5,270 H4 development pairs agree with their bulk source, a tautological path check; H6a shares that source. 24,432 regular/amendment input rows counted. Bulk-only filers and H6 quiet-selected events not exhaustively certified or rerun. |
| Co-registrants | No full-H0 signal accession under two CIKs. There are 404 full / 305 development CIK disagreements; 4 sampled co-filed headers list both CIKs. Bulk's accession-only dedup loses that one-to-many relationship. Bulk-side CIKs have 0 rows in the current price universe/share metadata; 380 pair-side rows have share metadata. CIK 6201 maps to AAL; 4515 is absent. No blind remap or duplicate deletion is justified. |

**Why no generic fix:** a Z suffix, agreement between tables, a submitter prefix,
or a single 4/5-hour transform cannot distinguish the valid and shifted records.
Raw source field values can already be wrong, and an agreeing pair/bulk case
demonstrates that selecting either entire column can fail. The bounded sample
does not identify every affected record or a complete safe canonical mapping.
Neither early-pair look-ahead nor universal conservative delay is asserted for
the whole population. A header-validated repair needs a qualified record-level
scope before another empirical evaluation; no convenient side is chosen here.

Read-only audit utility:
[`p0_acceptance_audit.py`](../scripts/p0_acceptance_audit.py).
Synthetic parser/impact tests validate seasonal conversion and strict-close/
latest-signal counting **under declared timezone assumptions**, not source truth.
The existing time parser's behavior remains unchanged; its documentation now
states that parsing Z syntax is not source-clock certification.

The collector requires operator-prepared, ignored metadata comparison/sample
sidecars and the existing caches; it is not a standalone fresh-repo rebuild.
Its collection lineage records the dirty `8642597` worktree. The final JSON also
contains explicitly identified offline verdict/aggregation annotations. Do not
replay its networked `main` as a validation command: it consumes the persisted
request budget and overwrites the report. Preserve the existing packet first.

An audit-only correction added CIK/accession to the sampled impact calculation
and made missing identity fail rather than report an unmeasured zero. Recalculation
from the same saved 22 headers confirmed the zero sample-local counts above;
it made **no new SEC requests**. A synthetic same-eligibility/reordered-signal
case confirms that latest selection can change even without a close change.

**Validation now performed** (single-thread BLAS flags set to 1):

```powershell
python -m pytest -q tests\test_p0_acceptance_audit.py tests\test_timeutil.py tests\test_sec_identity_audit.py
python -m pytest -q
python -m ruff check scripts\p0_acceptance_audit.py tests\test_p0_acceptance_audit.py
python -m ruff check --select E4,E7,E9,F scripts\p0_acceptance_audit.py tests\test_p0_acceptance_audit.py src\asof\timeutil.py
```

Results: **18 focused passed in 2.28s; 213 full-suite passed in 29.54s**, including
post-`8642597` code; both Ruff commands passed. Two inherited synthetic
rank-deficiency warnings remain. These are local code/arithmetic checks, not
source-clock, cloud-execution or scientific-acceptance certification. The prior
referee was not rerun because research inputs did not change; its existing PASS
does not cover this P0 source-integrity stop.
All 111 local links/anchors in the three updated documents passed checks.
The three new JSON packets parsed; the ledger remains at 74 rows, original
signal/bulk/share input hashes match the latest recorded lineage, and the prior
ledger, manifest, H0 results and referee files have no tracked changes.

**Requests/resources:** 46 audited project-client HTTP attempts cumulatively,
cap 150, rate <=2/sec including redirects/retries; 104 remain unspent, not a new
authorization. Receipt in ignored `data/p0_SEC_request_receipt.json`; raw API/
header/index caches and metadata comparison sidecars remain local. Header sample
run started after a 20% CPU/no-competing-research-job check; final full-suite
validation started at 4% CPU with no competing research job detected. No companyfacts load,
vendor/price request or research/calibration job was started by P0. Synthetic
unit fixtures are validation, not executions of the queued C1/C2 experiments.

**Queued but NOT executed, preserving order:**

- Part 2: Lead accepts H4's <=6.5e-13 differences as numerical-equivalent/no material
  missing-NI impact; that is an adjudication receipt, not another H4 run.
  The formation-only near-tie diagnostic, current-vintage DSR, claims draw and
  exactly-once corrected manifest refresh remain **P0-blocked**. The 74-row
  real ledger and older manifest are unchanged; corrected CLI guard is active
  but was not invoked on them.
- Part 3's c* plan was never executed and is now **SUPERSEDED** by user-approved
  Batch E. Do not run its historical 216,000 + 30,000 + 4,000 allocation.
  The independent synthetic significance-test contract below replaces it; this
  does not release P0 or Part 2 and does not alter frozen statistics/N/signs/splits.
- A new generic ingestion correction is not adjudicated, so no numbered
  time-correction deviation, input rebuild or H0 rerun is falsely logged as done.
  D12 is now the prospective robust-test requirement; a later accepted
  timestamp repair still needs the next free numbered deviation before rerunning.

The single Part 1 handoff reports this integrity verdict. The final Parts 2-3 handoff
is not fabricated for unexecuted work; further scope requires Lead review.
Source rights, human annotation, keys/spending/publication/push/tags and
holdout access remain owner-reserved; the holdout stays sealed.

##### Batch E: established tests and frozen verification contract

**Prospective source/seed/allocation freeze, before E3 execution.** Approval:
2026-11-13 23:57 ET through Lead, with the subsequent floor/ceil/tail correction.
[D12](DEVIATIONS.md#d12-require-established-robust-significance-checks-for-future-acceptance)
supersedes the never-run Lead-D10 c* plan. No P0 SEC header requests, Batch C
Part 2 diagnostics/manifest/rosters, or application to real development data.

Implementation:
[`robust_inference.py`](../src/asof/robust_inference.py),
[`KV numeric table`](../src/asof/nw_fixed_b_kv2005.csv),
[`verification runner`](../scripts/verify_robust_inference.py).
The functions require already eligible finite arrays; they do not merge dates,
drop missing rows, infer exposure/source quality or launch a study.

| Procedure | Reference and exact contract |
|---|---|
| EWC | LLWS (2018), eq.(10), footnote3: score/bread with all regressors; floor nu=0.4*T^(2/3), type-II cosines, unrestricted residuals, t_nu. nu=2/2/3 at T=17/18/28. No extra cosine, ordinary-normal fallback or silent degeneracy. |
| NW-fixed-b | LLWS eqs.(3),(6): ceil S=1.3*sqrt(T), maxlags S-1, weights1-j/S. Registered six lags remains S=7. KV working paper Table I, p24, linear interpolation **in b only**, correct right-tail versus absolute-tail interpretation. Two-sided5% uses97.5th percentile; two-sided1%/0.27% unavailable because99.5th/rarer percentiles are absent. No unverified polynomial, new simulation or tail extrapolation. |
| H4 IM | IM(2010) eq.(2): seven explicitly registered groups, unweighted mean of separately identified common-target coefficients, t_6. Preserve within-group nuisance span; absorb only constants/redundancy, never drop failed groups or the signal. Group assumptions not established by code. |
| WCR | Webb(2014) eq.(4), MNW(2021) restricted algorithm; CV1 re-studentization. Six equiprobable weights ±sqrt(1/2),±1,±sqrt(3/2). Enumerate when support<=10,000; otherwise explicit seed, inclusive absolute tail, plus-one MC. Invalid variances are retained as unavailable, not dropped or silently PSD-repaired. |
| Future decisions | Monthly EWC decides (NW diagnostic); H4 IM decides; event WCR at month clusters decides with IM-by-month **reported only**. q>14 is not covered by the unrestricted one-sided5% IM guarantee. Explicit registered endpoint thresholds, qualified assumptions, reliable geometry and attainable level required. Low-nu EWC rare-level qualification stays undetermined; bootstrap resolution is not small-cluster validity. |

Primary sources read directly (PDF SHA256 pin; full PDFs remain session research
scratch, not redistributed in Git):

- [LLWS author manuscript, 2018-07-14](https://www.princeton.edu/~mwatson/papers/LLSW_har_JBES_Final_071418.pdf):
  `8175998586eb78737eaafd6e1053d708a213d5bed31cd749a630a41c71131b6f`.
- [KV Cornell WP05-08, January2005](https://cae.economics.cornell.edu/05-08.pdf):
  `3c73702215d03a4cd9a14d4b8d7743021a9928e369bf9af41293dbfb5b5a4356`.
- [IM published paper, 2010](https://www.princeton.edu/~umueller/tstat.pdf):
  `6d51d57e899e1f695e86a66a9ec68fd7164d189deb7f1d2314425fb0c8ac864a`.
- [Webb working paper, 2014-11-13](https://www.econ.queensu.ca/sites/econ.queensu.ca/files/qed_wp_1315.pdf):
  `8cd7cbbafc43159e56464e6bb6dd2efa6f1ff71328308222c05961e0d45b2427`.
- [MNW multiway author draft, 2019-09-13 / published2021](https://econ.queensu.ca/pub/faculty/mackinnon/working-papers/qed_wp_1415.pdf):
  `e38a18e8017cd46a8c434182e0cd7602a0cda812368a17746f85a8d49fb90610`.
- [Canay-Santos-Shaikh, 2021](https://ivancanay.com/papers/wild-bootstrap-clusters-2021.pdf):
  `c5eec171d29c4bab0d58a9794bc580ca1b316c8ff695a95877ab05551256ed91`.

The attributed KV asset contains numeric table facts, not copied implementation
code. Interpolation reproduces three-decimal published tabulation, not an
infinite-precision distribution. Author-supplement NW tables were inspected but
are **not** the adopted critical-value source after Lead's correction. No new
runtime dependency; research-only pypdf/font decoding tools were restored after
missing-tool/TLS failures, outside the package manifest.

**Frozen E3 seed:** `2026111401`. Deterministic SeedSequence child streams per
case, separate data/bootstrap streams; all procedures see the same dataset.
No seed/level/bandwidth/estimator/adoption tuning after results.

| Allocation | Data replicates | Inner bootstrap draws | Charge |
|---|---:|---:|---:|
| Classical iid OLS harness: T17/18/28,1334/1333/1333 |4,000|0|4,000|
| Monthly null:4DGPs x3T x2,000 |24,000|0|24,000|
| Monthly iid power:3T x4effects x500 |6,000|0|6,000|
| Panel null:2DGPs x250 |500|199,500|200,000|
| Panel iid power:4effects x10 |40|15,960|16,000|
| **Total ceiling** |**34,540**|**215,460**|**250,000**|

A charge is one data-generation attempt **plus every nested bootstrap draw**;
three paired tests of one dataset are not three independent MC observations.
Webb B=399; G=7 has279,936 support vectors, so full enumeration is not feasible
under this experiment's budget. Early-invalid fits may leave unspent charges;
they do not authorize reallocating toward a favorable result.

Monthly DGPs exactly retain Batch A's iid Gaussian, stationary AR(1)phi=.3,
scaled t3, and common-factor exposure generation: six iid factor regressors
(SD.02), error SD.03, and exposures[.8,.4,-.2,.3,.1,.2]. Panel DGPs retain40firms
over7years, four Gaussian covariates, SIC-like4groups/year FE, firm intercepts,
and either no year shock or the prior heterogeneous-loading year shock.
The registered comparison is the actual `nw_alpha(lags=6)` and H4-style two-way
firm/year statistic, using normal reference levels. Panel WCR is **one-way year
CV1**, not a claim to preserve cross-year firm dependence. IM-by-period is not
the old pooled estimator. Positive planted power effects are .25/.5/.75/1.0 SD;
panel10replicates/effect gives very wide intervals, not an economic power study.

Harness first: classical OLS t with T-7 df at5%/1%; six exact-binomial checks
(three T, two levels), familywise99% Bonferroni reference interval; zero invalids.
Failure stops the experiment, retains evidence and forbids a seed retry.

Report null rates at5%/1% primary and0.27% with MCSE and two-sided95%
Clopper-Pearson intervals. Unsupported levels have unavailable counts and null
rates, never false zero-rejection claims. Invalid estimates stay in the attempt
history and are not redrawn or non-rejections. For **adoption only**, use a
worst-case upper bound treating uncomputed draws as possible rejections.
Prespecified adoption: reliable at this geometry iff the upper95% CP endpoint
of5% null rejection is<=7.5% across **all** fixed DGPs; otherwise unreliable.
Incomplete verification is not_evaluated. This label covers only the synthetic
geometry/5% criterion, not rare tails, real dependence or scientific acceptance.

Hard limits:<=250,000 charges,<=2,700CPU seconds,<=2GiB OS peak resident memory,
single pytest/runner process with BLAS thread flags1; check before/after every
small fit/block and stop at the first observed ceiling. Check machine load before
launch; AfterEvidence's authorized network-bound work is not a CPU release for
unrelated jobs. Only prespecified synthetic fits; no empirical/source-price,
model-training or holdout job.

Safe run only after this seed/allocation/source revision is locally committed:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python scripts\verify_robust_inference.py
```

Expected output: `results/robust_inference_calibration.json`, labeled SYNTHETIC;
complete/incomplete status, actual charge breakdown, resource observations,
harness result, per-case unavailable/invalid/warnings, intervals and fixed
adoption labels. Errors/ceilings preserve partial evidence and raise; no ledger
row, DSR/PBO, accepted hypothesis or live-data evidence is produced. No rerun
toward preferred size/power. **Freeze receipt: this contract said not run yet
when committed before E3; the current execution status is below.**

Pre-freeze validation: **63 focused tests passed in 15.43s** across robust
inference, resource guards, original inference, D4 predicates and independent
oracle fixtures. Configured new-file and selected changed-file Ruff passed.
Wheel inspection confirmed the attributed KV numeric asset is included.
This checks code/formula contracts, not statistical size or live assumptions.

##### Batch E completion: bounded run complete, adoption mostly failed

The single approved E3 run used clean commit
`1499865544a1a46004dfa391002409efb0869370` and the frozen seed/allocation above:

- **34,540 data attempts + 215,460 bootstrap draws = 250,000 charges**, no unused
  allowance, no redraw or retry toward preferred rates.
- **156.78125 CPU seconds / 158.922 wall seconds; 687.78125 MiB peak RSS**.
  Both CPU and memory ceilings respected; pre-launch shared CPU load 2%.
- **Classical harness passed:** at 5% the three geometries rejected 58/1334,
  61/1333, 52/1333; at 1%: 12/1334, 9/1333, 14/1333. All met the frozen exact-binomial
  familywise 99% checks against t(T-7), with no invalid classical statistics.
- [Output](../results/robust_inference_calibration.json) contains clean generation
  lineage, per-DGP/procedure/level counts and CP intervals, invalid/unavailable
  reasons, critical values, resource charges and fixed adoption labels.

**Adoption:** registered NW6, EWC and NW-fixed-b all fail the 5% bound at
T17/18/28. Worst upper 95% bounds are respectively:

| T | Registered NW6 | EWC | NW-fixed-b |
|---|---:|---:|---:|
|17|39.06%|13.40%|19.08%|
|18|38.00%|12.51%|19.55%|
|28|24.91%|9.65%|13.09%|

Panel G7 IM's worst bound 6.72% meets <=7.5%; WCR 8.73% and registered two-way 17.59%
do not. The WCR point 5.2% no-shock rate is below the tolerance; its **upper bound**
fails, so this is conservative qualification failure, not proof of excessive
population size. IM's label is limited to these two invented DGPs and5%, not
real year independence, rare tails, common targets or scientific approval.

The registered panel had 7 nonfinite statistics per null DGP; all 14 remain
unavailable. All monthly, IM and WCR estimates were finite. Unsupported
NW-fixed-b 1%/0.27% reference levels remain unavailable, not zero rejections.
Raw power curves are not size-adjusted: a higher rejection rate from an oversized
test is not stronger scientific power. Panel 10 replicates/effect yields wide CIs.
[F10](FINDINGS.md#f10-synthetic-finite-sample-size-distortion-of-the-registered-tests)
gives provenance-linked observed/expected examples and non-claims.

**Validation actually rerun:** final full `python -m pytest -q` → **234 passed,
two inherited synthetic rank-deficiency warnings, 36.71s**, one process with
BLAS/NUMEXPR flags 1. Configured new-file Ruff and E4/E7/E9/F on directly changed
existing Python files passed. Wheel inspection verified the KV asset. Added
matrix-sandwich and exact two-cluster reference assertions validate formulas,
not size or real-data assumptions. Pylance's reference request timed out; no
editor/static-analysis pass is claimed.
The initial post-run suite passed233tests before one reporting-guard test was
added. Final review corrected only failed-fit metadata: panel observation count
is280 rather than7groups, and missing Student df is not labeled with a normal
critical value. No Student failure or LinAlgError occurred in the executed
experiment; its reference metadata is unchanged. Methods, statistics, seed,
allocation and adoption rule remain as frozen; no E3 rerun after these reporting
fixes. Generated results retain their honest clean1499865 lineage.

Integrity checks: all33cases completed their assigned counts; per-level valid
plus unavailable denominators reconcile to attempts; all unsupported NW levels
remain null-rate rather than false zeros.130local document links/anchors checked.
Ledger74, original signal/bulk/share hashes and prior tracked empirical/manifest/
referee outputs are unchanged. P0 receipt stays46requests.

**Unchanged/held:** ledger 74 rows, registered N/design/statistics/signs, empirical
outputs and priors; no P0 request/repair, no development procedure/DSR/near-tie/
manifest/claims run, no holdout access, keys, paid data, vendor/human contact,
publication/push/tags. No scientific acceptance or release hold was lifted.
The c* allocation remains superseded and unexecuted. Any next qualification or
different sample geometry needs a prospective owner/Lead decision, not tuning
this completed run.

##### Late R3 oracle cross-check: same report, no new evaluation

The subsequent completion payload repeats
`CL-P0-POWER-ORACLES-20261113-R1`, already read in full before Batch E.
Under the previously authorized single cross-check turn, four additional
deterministic cases now cover default nu=0 (unsupported, no promotion to1),
the alternating-series Bartlett variance, and equal-weight IM estimates
[0,1,2] / [0,1,2,3,4,5,6]. **21 focused robust-inference tests passed in4.32s;
Ruff passed.** No discrepancy or implementation change was needed.

R3's explicit-nu1/nu2 illustrations are not the public fixed-rule API:
they do not authorize overriding floor nu. Default T4 degeneracy, regression
score/bread, bandwidth/maxlag, interpolated KV references, q/tail conditions,
nondeciding IM-by-month and exact small-cluster WCR cases remain covered.
Webb's reported >=2/6^G is a lower bound; inclusive constant-weight/scaling
ties can force a larger floor, as the code and exact two-cluster oracle report.

No R1 timestamp fixtures/proposals were implemented, no SEC request or real-data
access, no E3/referee/full-suite rerun or trial append. The last full-suite
234-test result and frozen synthetic artifact retain their original scope.
Only tests and this receipt change; methods, tables, decisions, adoption outcomes,
ledger and all P0/holdout/resource/publication holds remain unchanged.

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
**P0 is an additional hard stop:** filing-level clock authority, qualified
record-level correction scope and actual anchor/formation impact must be resolved
before an affected evaluation. Internal timestamp equality, unit tests and the
old referee PASS do not clear [F9](FINDINGS.md#f9-p0-acceptance-time-authority-is-not-uniformly-certified-by-json-z-fields).
Lead-D10's c* plan is **superseded, not pending execution**. The [D12 established
robust-test gate](DEVIATIONS.md#d12-require-established-robust-significance-checks-for-future-acceptance)
instead requires matching qualified significance checks without weakening any
original statistic/N/sign/threshold rule. Batch E synthetic validation does not
authorize applying the procedures to unresolved development inputs or opening
the holdout. It cannot establish source, group-independence or economic readiness.
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
