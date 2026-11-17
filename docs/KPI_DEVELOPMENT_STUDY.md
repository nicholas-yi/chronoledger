# D13 development-only KPI screen

**New exploratory study, not a resumption of the superseded `a9d788f` roster.**
The old case outputs remain quarantined. [D13](DEVIATIONS.md#d13-exploratory-kpi-disclosure-screen-crossed-reserved-calendars)
and D6 permanently qualify claims about future H4/H6(a) holdout work.
No hypothesis, outcome, threshold or registered split changes here.

## Metadata eligibility before content

The [development inventory](../results/kpi_development_cache_inventory.json) found
843 eligible issuer triples, exceeding the owner's minimum of 30. It projected only
2012-2018 filing metadata and checked cache existence; zero document bodies were read
or fingerprinted. Five candidate issuers failed used-context date eligibility.

Every selected annual report and used context must pass the
[shared guard](DOCUMENT_SCOPE.md) for acceptance, knowledge and period-end dates,
each within 2012-01-01 through 2018-12-31. The bulk ingestion stores reported SEC
acceptance in `knowledge_time`; this is explicitly declared in both date roles,
not independent UTC/field-clock certification.

Select up to 64 issuers by SHA256(`2026111702:CIK`) from the development-only eligible
pool, taking the latest eligible annual triple per issuer with 330-400-day gaps.
The comparator uses two prior annual observations, not the paper's three-prior-year
persistence definition. Used context remains at most two primary Item 2.02 8-Ks in
the preceding 120 days. Context dates must pass even if their bodies are uncached.
Calls, exhibits and other public sources are not exhaustively inventoried.

The new private directory is `data\kpi_omission_dev_v1`, separate from quarantine.
Preparation writes the exact roster and a per-document `guard_passes.json`.
Its hashes are recorded in the new plan. Cache size/mtime are pinned without opening
body bytes; content SHA256 is recorded at first guarded execution, not represented
as a pre-execution cryptographic content freeze. Any cache stat change stops execution.

## Frozen method and execution

The [original method](KPI_OMISSION_STUDY.md#frozen-pilot) supplies the same eight
lexical families, numeric-context heuristic, alias-absence candidate rule and
descriptive cosine/Jaccard/length/numeric baselines. Only the source period/roster
is rescoped. Alias presence is not validated reporting; alias absence is not a
semantic omission. Parser and field-clock limitations remain.

```powershell
python scripts\study_kpi_omission.py prepare
# Commit the new source, plan and roster hashes before any body read.
python scripts\study_kpi_omission.py run
```

Both commands require the documented single-thread environment for numerical work.
Run once only, with the owned worker on one logical CPU and a 1 GiB committed-memory
backstop, 240-second cooperative stop and 300-second controller limit. Individual
bodies are capped at 16 MiB; total uncompressed reads at 512 MiB. No download,
SEC request, model, price, return, alpha test or ledger append is permitted.

The worker repeats the guard before each source and appends start/completion
resource receipts, so a failed resource can be identified without replaying it.
Per-case checkpoints preserve completed work. The casebook remains private;
public outputs are aggregate diagnostics and hash receipts. No automatic retry.

## Interpretation limits

This is cache-conditioned exploratory evidence, not a representative accuracy
audit. Selected casebook examples are deliberately enriched. No human annotation
is requested; source-reviewable lexical candidates do not provide gold, validated
precision/recall, market novelty or incremental economic value. No holding-period
search, sign flip, outcome evaluation, training or holdout release follows.

## Executed once: bounded stop, not a completed 64-case study

Source/roster freeze: `bdca2029ef35298df1971470250afdd647835417`.
The [aggregate receipt](../results/kpi_omission_dev_review.json) records the
cooperative wall stop. No continuation, resampling, detector adjustment or retry followed.

| Item | Observed |
|---|---|
| Eligible metadata-only issuer pool | 843 |
| Pinned issuer triples | 64, in a new directory separate from quarantine |
| Pre-body date checks | All 263 pinned records passed: 192 annual and 71 context |
| Pinned acceptance/knowledge range | 2012-11-30 through 2018-12-06 |
| Pinned period-end range | 2012-09-30 through 2018-12-06 |
| Completed cases | 50/64, all with three readable primary-document representations |
| Unvisited cases | 14, not imputed zero or scored failures |
| Resource journal | 207 guarded starts and 207 completions; no unmatched resource |
| Bodies read | 150 annual bodies; zero context bodies (57 visited context objects were uncached) |
| Unvisited resources | 42 annual and 14 context records |
| Frozen soft wall stop | Worker 241.54 seconds against the 240-second cooperative rule |
| Controller wall / worker CPU | 249.28 / 110.42 seconds |
| Sum of separate controller/worker OS RSS peaks | 339.14 MiB |
| Compute affinity | One logical CPU |
| Input/source/protected integrity | Source, roster, guard receipts and protected files unchanged |

The 16 MiB per-body and 512 MiB aggregate limits were not relaxed; the worker reported
440,188,045 uncompressed bytes read. Resource checks passed under the owner's 300-second,
one-CPU, 1 GiB ceiling. "Stopped" is retained because 14 cases were not processed.
The final source passed 584 software tests (two pre-existing warnings) and affected-file Ruff.

### What the screen did and did not show

There was **one lexical candidate**, backlog in `KPI-DEV-049`, among the 50 completed
cases. Sixteen cases had repeated aliases that persisted into the current report.
These are rule outputs, not semantic omission or accuracy estimates.

AI-assisted reading of the already-generated prior-report excerpts for `KPI-DEV-049`
indicates that "backlog" describes an **industry inventory of drilled but uncompleted wells**,
not an issuer-reported company order-book KPI. Nearby numbers included years/commodity
context; the numeric-context rule did not establish a reported company-specific quantity.
That is insufficient evidence to advance this flag as a firm-specific KPI omission.
The original candidate count remains one: it was not retrospectively regraded to zero.

The three displayed alias-persistence contrasts also require interpretation:

- `KPI-DEV-001`: issuer-contract funded/unfunded backlog language;
- `KPI-DEV-004`: investment backlog and pipeline, a different business concept;
- `KPI-DEV-005`: the first captured hit is a table-of-contents entry, illustrating that
  page numbers can satisfy the weak numeric-context heuristic.

This is post-run AI-assisted diagnosis, **not human adjudication**, validated precision,
recall or a population error rate. No raw filing was reread for this review; only
guard-qualified, already-generated excerpts were inspected. No outcomes, market
prices, returns or novelty evaluation were introduced.

The descriptive baseline rank correlations are in the receipt. With only one nonzero
candidate-count case, they mostly encode that case's location in the baseline rankings;
they do not establish nonredundancy, predictive performance or economic value.
All earlier public-history/market-novelty questions remain unresolved: the used context
bodies were not cached, and calls/exhibits/news were not covered.

**Research decision:** do not advance this lexical detector to a return test or train/tune
it toward these exposed cases. A company/metric/value/scope binding specification and
independent measurement validation would be needed. No human effort or further model/data
work is automatically requested by this completion.

### Evidence locations

- Private `data\kpi_omission_dev_v1\guard_passes.json` contains each pinned record's
  acceptance, knowledge and period-end check; its pre/post-run SHA256 is
  `598bf7371eab47ca42d9b8703302313c23bf56b63f4252f885e5a27383d0bd5e`.
- The frozen private manifest SHA256 is
  `0944009c8f230372172c0622b560716fc5ee4db00f09cd0b93c5ae32363b4e92`.
- `resource_receipts.jsonl` records each actual guarded resource start/completion.
- `cases.json` and `casebook.md` contain source locators, fingerprints and excerpts;
  they stay private, not in Git. Their hashes are in the aggregate receipt.

Guard passes are on declared metadata dates, not historical field-clock, source-vintage,
security-identity or semantic certification. Of the 150 readable annual sources, 148
had metadata-only CIK support and two had matching inline CIKs; no identity gate is lifted.
Validated precision/recall, semantic omission prevalence, market novelty and incremental
alpha remain unestablished. Ledger rows remain 74 and the SEC counter remains 3,254.
