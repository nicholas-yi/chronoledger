# CL-QF-SYN-01: frozen synthetic stress benchmark

**Pre-execution design, 2026-11-17.** User selected `synthetic_and_plan`.
This is a new bounded known-truth check, not an empirical financial study.
The [allocation](../results/quant_frontiers_validation_plan.json), controller,
cases and reference source must be committed before any benchmark random draw.

## Contract

- One attempt; PCG64 seed `202611171803`, independent area stream `seed+area_index`.
- 64 generated scenarios in each algebraic area A/C/D/E/F/G/H.
- B: 256 uncensored marked-Hawkes events, at most 100,000 thinning proposals.
- I: all 4,096 length-12 fair-coin paths, not a Monte Carlo estimate.
- Numerical oracle absolute tolerance `1e-8`, fixed before execution.
- B's one stochastic QA screen uses DKW delta `0.01`: with the true parameters,
  transformed interarrival uniforms must have empirical CDF distance at most
  `sqrt(log(2/0.01)/(2*256))`. This can fail by chance; a failure stays a failure.
- No automatic repeats, seed changes, parameter sweeps, retuning or resume.
- One compute CPU: both owned controller and owned worker use the same affinity bit.
- Total wall budget 300 seconds; controller stops at 290 with cleanup reserve;
  worker soft wall/CPU caps 270 seconds.
- Total RSS budget 1 GiB. Owned worker has an OS Job Object private-commit limit
  of 896 MiB and a peak-RSS check; controller peak-RSS allowance is 128 MiB.
  Their sum of separate observed RSS peaks must be below 1 GiB.
  The worker Job Object also enforces one process and kill-on-close.
  These commit/RSS measures differ; combined RSS is monitored/verified, not claimed
  to be a single process-tree OS working-set limit.
- No real-data/financial archive reads, SEC, models/training runs, empirical backtests,
  production trial-ledger operations, purchases or push.

Numerical-library thread variables must all equal one. Worker imports/draws are
gated until the controller attaches the Job Object and CPU affinity.
The default 1-GiB limit of the previously tested `WorkerJob` is preserved; the new
optional lower memory limit lets this run reserve RAM for its controller.

## Cells and interpretation

| Area | Ground truth/oracle | Baseline or adverse control | What success does not prove |
|---|---|---|---|
| A | Exact declared state revisions; enumerate the joint state/disclosure/emission distribution and expected Brier risk | Ignore evidence; reverse the supplied disclosure probabilities | Semantic extraction accuracy, correct real managerial probabilities or market surprise |
| B | Generate a bounded marked exponential Hawkes process by valid thinning with a known alternating 1/4-per-day calendar, excitation 0.3, decay 0.5/day, uniform marks | Constant 2.5/day calendar with no excitation; its DKW statistic is diagnostic, not required rejection | That Hawkes fits real filings or implies signed return predictability |
| C | Analytic two-increment cross-area, reversal and future-prefix invariance | Endpoint representation; full lag twin also recovers the area exactly | An advantage over all cheap lag features or a financial effect |
| D | Six-node nonnegative matrix with row sums 0.4; 60-term Neumann-series oracle | Reverse the transmission direction | A correct real graph, causal spillover or alpha |
| E | Three-state discounted VAR sum through 180 terms; exact finite-state pricing measure conversion | Equate risk-neutral and physical measures without the supplied kernel | Identified real cash-flow news or assumption-free option forecasts |
| F | Dual/primal fixed-map ridge identity; deliberately constructed rival-score mixture | Known rival reconstruction | Learned financial information or out-of-sample predictive performance |
| G | Convex stationarity plus worst-case objective comparison | Zero position and nominal optimizer; report nominal utility sacrificed by robustness | Real return dominance, calibrated uncertainty, financing or execution feasibility |
| H | Enumerate all 16 vertices of each four-outcome rectangular support; include unbounded missing short and entirely missing population | Zero imputation; explicit joint-constraint example where rectangular bounds are loose | A confidence interval or sharpness with unrepresented joint constraints |
| I | Exact fair-coin path probabilities, conditional binary betting-product identity and anytime crossing probability at threshold 20 | Peek repeatedly at exact fixed-sample binomial tails | Valid financial-return inference or all forms of dependence |

These are intentionally small, interpretable model worlds. Some conclusions hold by
construction: the true Bayes posterior minimizes expected Brier loss, a correctly
specified propagation equation recovers its own oracle, and a robust optimizer
maximizes its specified worst-case objective. Those comparisons check software and
assumption sensitivity; they are not independent economic discoveries.

Wrong-model controls may perform poorly or sometimes look adequate. Their outcomes
are reported without requiring a favorable ranking. No effect size or benchmark score
will be used to select a real-data detector, trading threshold or registered design.

## Receipts and stops

`data/quant_frontiers_validation_v1/attempt.json` is created exclusively after source
preflight and before launch. Its presence or an existing public report blocks rerun.
Only that newly owned output path is used; existing data files are not inspected.
The public report is `results/quant_frontiers_validation.json`.

The controller requires a clean committed source tree, checks frozen files against
HEAD with LF/CRLF equivalence, and records raw-worktree SHA-256 values before/after.
Only code/configuration/docs/dependency files are fingerprinted; no real ledger or
data payload is read to create a protection receipt.

Workers checkpoint cell state every eight started scenarios/events/paths and on cell
completion. `attempted` includes a started case; `completed` counts finished cases
through the last checkpoint. A stopped run reports the last receipts and treats
unreported work as unknown, not as passed or as additional sampled evidence.

Completion and QA are separate. A complete run with any failed oracle/DKW check is
not a passed QA run. Source/resource violations also block QA. No empirical claim,
UTC qualification, measurement gold or registered-hypothesis support can result.

## Launch after the freeze commit

Pre-execution software verification: the full suite passed 637 tests in 105.19 s
with two existing synthetic rank-deficiency warnings; repository Ruff passed.
The controller tests cover changed allocations, prior attempts, source matching,
handshake refusal and recorded guard failure. They do not execute the benchmark
generator. This is not a benchmark outcome or a financial/statistical qualification.

```powershell
$env:OPENBLAS_NUM_THREADS="1"
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
uv run --no-sync python scripts/validate_quant_frontiers.py --execute
```

The strict controller currently requires Windows. Unit tests use invented plan/guard
fixtures and do not call the benchmark generator before its committed freeze.
