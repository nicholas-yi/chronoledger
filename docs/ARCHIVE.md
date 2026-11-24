# Archive

Completed one-shot runs, superseded versions and long-form working notes were removed from the
main tree on 2026-11-24 to keep the code readable. Nothing was deleted from history. All of it is
preserved, unchanged, at the git tag
[`archive-2026-11`](https://github.com/nicholas-yi/chronoledger/tree/archive-2026-11).

**Reproducing an archived run:** each result receipt records the commit it was frozen at
(`freeze_commit` or `lineage.git_commit`). Check out that commit, not `master`, to rerun it.
No result, trial-ledger row, deviation or holdout rule changed in the cleanup.

## What stays in the main tree

- The research pipeline: SEC data builds, H0 signals and backtests, the held H4/H6 runners
  (needed for the [D18 prospective holdout](DEVIATIONS.md#d18-move-h4-and-h6a-confirmatory-evaluation-to-a-prospective-holdout)),
  the leak probe, the extraction benchmark and the figures.
- The `asof` library, including the referee, inference, robust tests and the final reader.
- Maintenance checks and the tests for everything above.

## Archived code

| Area | What it was | Outcome, where recorded |
|---|---|---|
| SEC timestamp audit | Header pilot, the original full audit and continuations A1-A5, their planners, identity and acceptance audits, and the D16 time correction | All 16,921 H0 accessions qualified; 103 H0 knowledge times corrected (D16); 0/262 older H4/H6a filings qualified with no assignment changes. [FINDINGS](FINDINGS.md), [DATA_AUDIT](DATA_AUDIT.md) |
| Reproducibility diagnostics | F8 H0 and D15 H4 thread checks, Batch B reconciliation, optimized-H0 verification | Differences explained by BLAS thread count; exact reproduction single-threaded. [FINDINGS](FINDINGS.md) |
| Inference calibration | Batch A and Batch E synthetic calibrations | Monthly tests oversize at 17-28 months (F10, a permanent limit). Results kept in [results/robust_inference_calibration.json](../results/robust_inference_calibration.json) |
| D17 event-time panel | One-shot exploratory runner | Neither variant points the expected way. Method kept as [`asof.event_neutral`](../src/asof/event_neutral.py) |
| Reader experiments | Positive controls, contract, modes, presence, roles, columns, REAL1-REAL3, TAT-QA/FinQA diagnostics, HHEM benchmark, AI-reviewer rounds, claim/notation/integrity validators | Final reader and its regression replay stay. [FOCUSED_READER](FOCUSED_READER.md) |
| Quant frontier runs | Synthetic benchmark and development feasibility runners | Toolkit stays as [`asof.research`](../src/asof/research); runs were mechanical checks, not economic validation |
| KPI omission screens | Cached-text exploratory screens | Exploratory only; no hypothesis or return test |
| Scaffolding never used by a study | Study registry, scheduled-window planner, cost arithmetic, label validator, SEC documentation probe, audit confidence sets, social-sentiment client | Closed or unused; H7 was closed unregistered on 2026-11-21 |

## Archived documents

| Document | Summary |
|---|---|
| [QUANT_RESEARCH_FRONTIERS_2026_11](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/QUANT_RESEARCH_FRONTIERS_2026_11.md) | Research synthesis of nine study directions beyond text change; not a registration |
| [RESEARCH_REVIEW_2026_11](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/RESEARCH_REVIEW_2026_11.md) | Literature-backed upgrade recommendations; the adopted ones are in [RESEARCH_PLAN](RESEARCH_PLAN.md) |
| [QUANT_SYNTHETIC_VALIDATION](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/QUANT_SYNTHETIC_VALIDATION.md) and [results](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/QUANT_SYNTHETIC_RESULTS.md) | Frozen known-truth benchmark for the toolkit, and its observed results |
| [QUANT_DEV_FEASIBILITY](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/QUANT_DEV_FEASIBILITY.md) and [results](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/QUANT_DEV_FEASIBILITY_RESULTS.md) | 50 exposed issuer triples: lexical features computable; independent gold and complete histories absent |
| [QUANT_EMPIRICAL_PILOT](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/QUANT_EMPIRICAL_PILOT.md) | Proposed gold-dependent pilot; blocked on independent human reviewers |
| [KPI_OMISSION_STUDY](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/KPI_OMISSION_STUDY.md) and [KPI_DEVELOPMENT_STUDY](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/KPI_DEVELOPMENT_STUDY.md) | Exploratory cached-text screens (see D13) |
| [AUDIT_CONFIDENCE_SEQUENCE](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/AUDIT_CONFIDENCE_SEQUENCE.md) | Offline finite-population confidence sets for a future timestamp audit; superseded by the full audit |
| [H7_SOCIAL_SENTIMENT](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/H7_SOCIAL_SENTIMENT.md) | Closed unregistered: VADER failed qualification and paid access was declined |
| Full [DATA_AUDIT](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/DATA_AUDIT.md) and [FOCUSED_READER](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md) | Run-by-run notebooks; the main-tree versions are condensed summaries |
