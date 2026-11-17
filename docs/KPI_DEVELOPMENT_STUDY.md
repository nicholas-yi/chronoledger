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
