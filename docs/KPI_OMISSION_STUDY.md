# Cached KPI-omission study

**Separate exploratory study, not H0/H1, human gold or an economic test.**
The owner approved cached-source analysis and implementation only, with no new downloads,
project model inference, training or human effort. No price, return or computed fundamental
outcome dataset was an input. Reserved-source overlaps are disclosed below; this does not
certify exclusion of all outcome-bearing material. Existing holds and failed results stand.

**STOPPED AND QUARANTINED.** The first screen stopped on an HTML-comment parser error.
**The `a9d788f` roster is superseded and must not be used.** The original frozen
plan/manifest and failed receipts remain unchanged; see
[D13](DEVIATIONS.md#d13-exploratory-kpi-disclosure-screen-crossed-reserved-calendars).
The separately authorized [development-only replacement](KPI_DEVELOPMENT_STUDY.md)
uses new paths and a new freeze; it does not release or reinterpret this old evidence.
A subsequent metadata-only review found that the pinned 2021-2024 disclosure roster
overlaps the separately reserved H4/H6(a) calendar even though it predates the return
holdout. No cached-case evidence may be used or published pending Lead/owner review.
The stopped receipt and detailed date/exposure audit remain in ignored
`data\kpi_omission_v1`; they were not committed as scientific results.
The original receipt's static `holdout_opened=false` is not a scope-compliance attestation.
Raw annual HTML can contain reserved fundamental comparatives, and the loaded filing
`Items` metadata can carry H6 event codes. No numerical outcomes or endpoint joins were
computed, but no claim of excluding all outcome-bearing source material is justified.
Preparation also fingerprinted compressed cached objects; the private audit distinguishes
that byte access from the much smaller set of decompressed/parsed document bodies.

Parser fixes are tested on invented fixtures only. A conservative, study-local date gate
now refuses validation/holdout-era disclosures before cache access. It does not silently
replace the original roster or authorize any continuation; the original plan remains
historical and blocked. No actual case was reprocessed after the stop.

## Economic question and competing explanations

Does an unexplained disappearance of a repeatedly discussed firm-specific operating metric
contain information beyond ordinary document change? The intended mechanism is selective
reporting plus incomplete investor attention, not "all textual change is bad."

The [Moving Targets working draft](https://afajof.org/management/viewp.php?n=80332)
provides motivation from earnings calls; this pilot instead examines cached annual filings.
It is not a replication or an assumption that the paper's alpha transfers to this universe.
The [2026 Mimicking Finance paper](https://www.nber.org/papers/w34849) motivates asking which
variation is genuinely incremental, not treating model sophistication as novelty.

Required competing explanations include metric renaming, scope/divestiture changes, a
definition change, relocation into a table, parser/extraction failure, coverage failure,
already-public information and routine reporting variation. An omission is not proof of
deception, fundamental deterioration, surprise to investors or a profitable trade.

## Frozen pilot

The metadata-only preparation inventories cached 10-K bodies with stored knowledge times
from July 2021 through June 2024. For each issuer it takes the latest three cached annual
reports with 330-400-day report-period gaps, increasing stored times and distinct periods.
The first 64 issuers by SHA256(`2026111702:CIK`) are selected before content is read analytically.
Cache availability conditions this universe: it is not a representative sample of all
filers, delisted firms or securities. CIK/source-path agreement is not dated share-class identity.

The two prior annual documents provide **two-observation repeat support**, not the original
paper's three-prior-year persistence definition. All stored clocks remain unqualified.
The [plan](../results/kpi_omission_plan.json) pins the private manifest hash, fixed metric
patterns and selection rule. The manifest contains exact URLs, metadata and compressed-cache
hashes. It is not a network request queue.

Eight fixed lexical families are screened: backlog, same-store sales, subscribers, active
users, net revenue retention, customer retention, customer/subscriber churn and capacity
utilization. Net/gross retention and unrelated metrics are not interchangeable. This list
is a narrow vocabulary, not exhaustive semantic coverage.

A lexical omission candidate requires an alias in both prior documents with nearby digits,
and zero alias occurrences in the current full primary-document text representation.
Nearby digits do not establish an extracted value: years, pages and other quantities can
contaminate that heuristic. Conversely, "we no longer report backlog" retains the alias
and is not a literal disappearance. Such explanation cues are evidence for review, not
automatic benign or adverse labels. Persistence controls mean **alias persistence**, not
validated continued metric reporting.

Every cached body is bounded at 16 MiB uncompressed. Missing, capped, unparsable, empty or
inline-identity-conflicting sources remain unknown, not zero change. Where supplied, inline
CIK/form/period are checked against the manifest; absence of inline identity remains labelled
metadata-only. Negative assertions concern a parsed representation, not proven absence of
the economic concept from all disclosure channels.

## Timeline, baselines and case selection

For each selected issuer the study inventories at most two preceding Item 2.02 primary
8-Ks within 120 days, using stored metadata. Missing caches remain missing. Exhibits,
earnings calls and news are not exhaustively inventoried, and same-day stored clocks are
not certified. An earlier cached alias mention is positive evidence only; a non-hit cannot
establish market novelty, first public disclosure or absence of earlier market knowledge.
`public_history_complete=false` and first public observability remain unresolved.

No fitted models are used. Descriptive baselines are full-document cosine/Jaccard distance,
relative length change and numeric-token-set distance. Numbers are not matched by
entity/metric/period, so the numeric baseline is not a semantic measure of economic news.
Rank associations are descriptive, with no p-values, predictive interpretation or alpha.

The private casebook deliberately selects up to six cases with the largest lexical candidate
counts, three alias-persistence controls and three incomplete cases, with ties by case ID.
This is **case enrichment**, not a random accuracy audit or a tail-precision estimate.
Human gold, validated precision/recall, semantic omission prevalence, cash-flow direction,
uncertainty direction and incremental alpha cannot be supplied by this screen.

## Local workflow and safety

These commands describe the old frozen interface, not permission to continue its quarantined
roster. The current runner implements only the D13 development replacement with new paths;
execution checks every pinned annual and context date before any body access. Do not delete
old receipts or point the new runner at quarantine.

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
python scripts\study_kpi_omission.py prepare
# Commit code, tests and plan before the separately approved content screen:
python scripts\study_kpi_omission.py run
```

Preparation reads only metadata, file existence and compressed-byte fingerprints.
Execution uses only those frozen cache objects; it never creates an EdgarClient.
It reuses the tested Windows owned-worker Job Object with one logical CPU and a 1 GiB
worker committed-memory backstop. Cooperative stops at 240 seconds/900 MiB, a 300-second
controller wall deadline and a 512 MiB total uncompressed-read ceiling bound the pilot.
No existing service or unrelated process is stopped.

Private outputs in `data\kpi_omission_v1` contain the manifest, one-shot attempt receipt,
all case diagnostics and source excerpts with parsed-text offsets/hashes. Raw excerpts
are not committed. Per-case checkpoints preserve a completed prefix on a hard worker stop;
a truncated checkpoint and unvisited cases stay unknown. The public review contains aggregate
counts and output fingerprints.
The existing ledger, SEC counter, A2 report and CS validation receipt are fingerprinted,
not evaluated. Source and protected-file changes fail the run; output files are never
overwritten and a stopped run is not automatically resumed. CLI failure is nonzero.

## Decisions this pilot can and cannot support

It can show whether the vocabulary yields source-reviewable cases in the current cache,
where the representation fails, how much prior-context coverage exists and which cheap
baselines co-move descriptively. AI-assisted readings are explicitly not independent human
adjudication and cannot certify scientific measurement thresholds.

No human work is requested under this scope. With no gold, precision and semantic recall
remain unknown; do not populate them from assistant agreement or synthetic fixtures.
If the corpus lacks the necessary earlier sources, pause the market-novelty claim rather
than imputing a first-observable timestamp.

Later economic work would require a separately approved protocol, adequate measurement,
rights/identity/timing, meaningful net-effect margin and qualified inference/power.
It must compare against the same feasible cheap baseline and separate cash-flow direction,
uncertainty, long/short legs, turnover, borrow, execution latency and break-even costs.
Existing H4 no-support evidence is not converted into support by this narrower proposal.
No holding-period search, sign reversal, retraining or holdout opening follows from this pilot.
