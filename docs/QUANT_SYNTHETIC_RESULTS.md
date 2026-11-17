# CL-QF-SYN-01: observed synthetic validation results

**2026-11-17. Completed synthetic QA, not empirical economic validation.**

The user approved one bounded run and a separately gated empirical pilot plan.
The [design](QUANT_SYNTHETIC_VALIDATION.md), seed, allocation, oracles, baselines,
controller and source were committed at
`2885d77d8416009231034883ac2c0e92471ea528` before benchmark draws.
The [raw receipt](../results/quant_frontiers_validation.json) records the source
hashes, full allocation, all nine cell outcomes and resource evidence.

**Result:** complete; all nine cells finished their frozen allocations with zero
recorded QA failures. Source matching and resource checks passed. No tuning, seed
change, automatic rerun, source repair or empirical study followed the result.
`economic_claim_validated` remains false.

## What was observed

| Area | Completed / planned | Observed result and interpretation |
|---|---:|---|
| A: state/belief | 64 / 64 | Exact expected Brier risk: correct assumed model 0.169608; ignore new evidence 0.198316; wrong disclosure model 0.249246. Correct Bayes benefits from its known true probabilities; wrong assumptions can be worse than ignoring evidence. No semantic reading or real investor expectation was measured. |
| B: arrival clock | 256 / 256 events | Time-rescaling DKW distance 0.091472, below frozen bound 0.101726. Wrong constant-calendar distance 0.186044. The latter was a diagnostic, not a required rejection. This is one known-parameter uncensored synthetic process, not evidence that Hawkes fits filings. |
| C: path order | 64 / 64 | Maximum analytic area error 4.44e-16; future-prefix checks passed. The full lag twin also recovered the two-event area: no incremental predictive advantage for signatures was established. |
| D: network | 64 / 64 | Maximum propagation-versus-Neumann-series error 1.33e-15. Reversing the directed exposure produced mean vector error 0.295721 in arbitrary invented units. This verifies a specified transmission equation, not real links or causal equity effects. |
| E: pricing | 64 / 64 | Maximum discounted-VAR-series error 1.33e-15. Equating risk-neutral and physical measures produced mean vector error 0.349550 under the constructed kernels. This is model-conditional arithmetic, not an observed return-forecast error rate. |
| F: twins | 64 / 64 | Maximum dual/primal ridge discrepancy 1.35e-14; known-rival mixture reconstruction RMS at most 2.19e-15. Deliberate repackaging was detected. No representation was trained and no financial/OOS predictor was tested. |
| G: control | 64 / 64 | No positive worst-case-objective regret versus nominal/zero baselines within tolerance; maximum stationarity residual 1.14e-14. Robust control had **lower nominal objective in all 64 cases** than the nominal optimizer. Its protection is conditional on the supplied uncertainty set and is not free return improvement. |
| H: identification | 64 / 64 | Rectangular-support bounds matched all corner enumerations exactly. Missing short losses remained unbounded; an entirely missing population stayed unidentified above. A joint-constraint example makes clear why rectangular bounds need not be sharp for a coupled world. |
| I: prequential | 4,096 / 4,096 exact paths | Under the frozen fair-coin null, anytime threshold crossing was 0.78125%; repeated peeking at valid one-sided fixed-sample binomial tests crossed at 6.298828125%, versus nominal 5%. The anytime rule was conservative here; no power comparison or financial-return validity was established. |

These denominators have different units: scenarios, uncensored events and exhaustive
binary paths. Do not combine them into a single "accuracy" or effective financial
sample size. The binary calculation is exact enumeration under its toy null,
not a Monte Carlo confidence interval.

## Why these are not nine new findings

Several advantages are true by construction:

- The correct finite-state posterior minimizes expected Brier loss in its own model.
- A linear propagation solver should recover the same model's convergent series.
- A convex robust optimizer should optimize its chosen worst-case objective.
- An identified interval should contain all allowed vertices of its declared support.

The useful outcome is that the implementations preserved those properties, the
adverse controls exposed assumption dependence, and the code did not claim a new
financial signal from them. No real-data performance target, calibrated probability,
human gold, historic UTC authority or tradable edge was established.

Fixed-feature ridge identities and descriptive least-squares calculations used
invented arrays. No LLM/neural/learned feature-map training, financial training
pipeline, external model service or empirical backtest was run.

## Resources, provenance and boundaries

| Receipt | Observed |
|---|---:|
| Controller total wall time | 34.2091 s, below 300 s |
| Worker wall / CPU | 20.5796 s / 6.46875 s |
| Controller CPU | 1.09375 s |
| Worker peak RSS | 142,143,488 bytes |
| Controller peak RSS | 30,642,176 bytes |
| Sum of separate RSS peaks | 172,785,664 bytes, approximately 164.8 MiB |
| Compute affinity | One logical CPU, shared by owned controller and worker |
| Worker exit | 0 |
| Frozen source unchanged | True |

The hard worker Job Object limit was 896 MiB with one process and kill-on-close.
Controller RSS allowance was 128 MiB; combined RSS was monitored/verified separately.
Job private-commit and RSS are different measures, not a claimed single aggregate
working-set kernel limit. The strict launch was Windows-only.

Runtime versions observed immediately after freeze and before execution were CPython
3.12.10, NumPy 2.5.4 and SciPy 1.18.1. The frozen lineage includes the dependency lock;
this is not a new independent wheel-integrity attestation.

The ignored one-attempt receipt remains under
`data/quant_frontiers_validation_v1/attempt.json`; it is not removed or repurposed.
Only that new output and the public synthetic receipt were created by the run.
No existing data archive/parquet, source corpus, production trial-ledger content,
SEC source, price, real fundamental outcome or model artifact was read.
No production trial row, registered design, existing hold or historical result changed.
Access flags describe the reviewed scope; they are not an OS system-call trace or
an authenticated access permit. The resource Job Object is not a filesystem/network sandbox.

Pre-execution software verification passed **637 tests in 105.19 s**, with two existing
synthetic rank-deficiency warnings; repository Ruff passed. Controller fixtures did
not execute the benchmark generator before its freeze. No cloud run is claimed.

## What happens next

The [empirical pilot proposal](QUANT_EMPIRICAL_PILOT.md) is prepared, **not approved
or executed**. It starts with measurement feasibility and independent labels within
the 2012-2018 development-source envelope, not another return backtest.

Before any real inventory/read it needs a separate user decision, source rights,
an approved physically development-only curation/input boundary, eligible frozen
manifests, independent reviewers and a resource contract. Human review remains
unassigned. Oracle-input checks cannot be relabelled automatic extractor accuracy.

The H4/H6 holds, D6/D13 qualification, timestamp/identity/complete-return gaps and
small-sample inference limitations remain. These synthetic results neither release
those gates nor authorize a new benchmark run.
