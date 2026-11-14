# ChronoLedger

**A point-in-time research engine with an executable self-audit.** ChronoLedger turns SEC filings into a point-in-time,
provenance-tracked record of public companies, then tests whether filing-derived signals predict
returns, with explicit time-travel tests for look-ahead bias rather than an assumption of safety.

**Status: DEVELOPMENT ONLY (2026-11-13).** Public inputs were rebuilt and the development runs
completed. No supported hypothesis or tradable edge is claimed. All four monthly variants,
including three missing-return assumptions each, ran in **61.1 seconds wall-clock** with validated
prepared inputs; building that input snapshot separately took 155.0 seconds.
No holdout test has been executed. Historical H4 preprocessing
contaminated its isolation ([F4](docs/FINDINGS.md#f4-h4-winsorization-used-observations-outside-development));
the correction does not restore an untouched sample. Historical estimates are not fresh-data
results; [F2-F6](docs/FINDINGS.md) document survivorship and point-in-time defects, including
corrections [D6-D9](docs/DEVIATIONS.md). See [pre-registration](docs/PREREGISTRATION.md) and
[data audit / rebuild provenance](docs/DATA_AUDIT.md).

**Batch B update: release gates BLOCKED.** The one-time reruns did not match every
recorded summary exactly, and the metadata-only claims preflight found305CIK and
124acceptance disagreements. Claims selection stopped before drawing; DSR was not
computed. See [F7/F8](docs/FINDINGS.md#f7-h0-pair-metadata-disagrees-with-the-bulk-filing-identityacceptance-metadata)
and the [bounded Batch B evidence](docs/DATA_AUDIT.md#batch-b-completion-and-stopped-gates).
**Batch B's pinned full suite passed179tests**, but that does not resolve source
or numerical-reconciliation failures.
That full-suite result is pinned to Batch B's tested source. The later
[independent synthetic oracle cross-check](docs/DATA_AUDIT.md#independent-oracle-cross-check-r1-synthetic-only)
passed 56 focused tests after offline-helper fixes; no study/referee or stopped
step was repeated in that cross-check.

**P0 UPDATE — time-integrity BLOCKED.** The broad "JSON acceptance timestamps
verified UTC" claim is withdrawn: own filing headers/indexes reveal source-clock
inconsistencies even when both internal tables agree. A blind 4/5-hour shift is
unsafe. See [F9/P0 evidence](docs/FINDINGS.md#f9-p0-acceptance-time-authority-is-not-uniformly-certified-by-json-z-fields).
No production timestamp, CIK, snapshot or study was changed/rerun under Batch C;
Parts 2-3, including manifest refresh and new calibration, stopped behind P0.
The final P0 validation passed **18 focused tests and 213 full-suite tests**
(including post-`8642597` code), with two existing synthetic warnings; selected
Ruff passed. Passing tests do not clear the source-clock gate.

**Batch E prospective update:** user-approved established robust significance
tests replace the unexecuted c* proposal. [D12](docs/DEVIATIONS.md#d12-require-established-robust-significance-checks-for-future-acceptance)
and the [frozen seed/allocation](docs/DATA_AUDIT.md#batch-e-established-tests-and-frozen-verification-contract)
preserve all registered statistics/N/signs and add stricter future requirements.
EWC uses floor nu; NW uses ceil S with maxlags S-1 and KV table interpolation;
IM-by-month is non-deciding. **No robust procedure is applied to development data;
P0 and Batch C Part 2 remain blocked.** E3 size/power verification has not run yet.

The Python package is named `asof`, after the `as_of` queries everything is built on.

## Principles

- **Bitemporal research facts.** Temporal filing facts carry *valid time* (the period described) and *knowledge time* (EDGAR acceptance in UTC). Time-filtered queries protect these records; current-ticker and current-SIC proxies remain explicit limitations, not historical point-in-time guarantees.
- **Look-ahead is tested, not assumed away.** Time-travel checks compare full and as-of-truncated inputs, with canaries for known leaks. Passing checks are evidence for the tested paths, not a universal proof.
- **Pre-registered.** Hypotheses, thresholds, and sample splits are fixed and git-tagged before returns are examined. Deviations are logged with a timestamp and tag.
- **Every trial counts.** An append-only trial ledger feeds the Deflated Sharpe Ratio and probability-of-overfitting estimates, and the holdout can be opened only once.
- **As-traded prices.** Vendor prices adjusted for later splits are converted back to the prices that actually traded, so price filters and market caps don't leak future corporate actions.

## Verified so far

- A newly built five-issuer pilot has **132,527 facts**, all joined to stored acceptance timestamps.
  Ten fact and six revision as-of checks found zero violations; the planted period-end leak was caught.
  This is a new fixture, not a byte-for-byte restoration of the original pilot.
  Its source-clock accuracy was not re-certified by the P0 audit.
- The rebuild processed 32,508 H0 filing features and 12,184 H4 annual filings with zero feature
  errors. A 100-firm [pinned legacy comparison](results/h0_optimization_equivalence.json) passed
  across all four variants and 17 formation months, within its documented D7/D8 comparison scope.
- The local processed-price snapshot round-tripped **57,195 monthly rows and 14,433,060 daily
  returns** exactly. All 12 full-sample configurations then matched raw-preparation metrics exactly.
  The earlier 298.7-second timing miss remains in the [append-only ledger](results/trial_ledger.jsonl).
- There are 2,733 usable price histories among 2,753 **already current-ticker-selected** firms.
  That is not survivorship coverage. [F2](docs/FINDINGS.md#f2-distress-event-tests-are-invalid-under-a-current-ticker-universe)
  remains unresolved; [F3](docs/FINDINGS.md#f3-three-data-bugs-caught-by-an-implausible-backtest)
  records the original implausible-backtest failures.
- Latest P0 local regression tests: **213 passed**, with two existing synthetic
  rank-deficiency warnings. Selected changed-file Ruff `E4,E7,E9,F` checks pass.
  Full-repository default Ruff was not rerun here; its last recorded baseline
  had 62 inherited findings versus 63 at the handoff.
  See [validation and rebuild provenance](docs/DATA_AUDIT.md).

Historical header cross-checks matched the sampled JSON instants to header-derived UTC;
they did **not** establish a universal guarantee for all JSON paths/vintages.
The later P0 counterexamples supersede that broad interpretation. The section
parser's historical30/30 real10-K result was not repeated here.

### Development results, not confirmatory findings

H0 signals are accepted in **2023-01-01 through 2024-06-30 UTC**; returns end by **2024-07-31**.
The expected long-short sign is positive: long low-change firms, short high-change firms.
Primary results are value-weighted and net of estimated costs.

| Cosine variant | Return months | Mean net / month | FF5+UMD alpha t |
|---|---:|---:|---:|
| `v1_10K_raw` | 17 | -0.805% | -0.45 |
| `v2_latest_raw` | 18 | +0.291% | +1.46 |
| `v2_latest_neutral` | 18 | -0.294% | -2.33 |
| `v2_10K_neutral` | 17 | -1.689% | -2.36 |

No positive-direction support is established. The zero, -30%, and -100% missing-return assumptions
coincide here because no held long/short leg lacks its next-month return; that does **not** repair
firms missing from the universe. Raw change event panels are descriptive; neutralized event panels
are **not evaluated** under D8. These neutralized cosine variants, historically logged as `H1n`,
are **not the claim-level H1 signal**. See the [full H0 output](results/returns_h0_development.json)
and [execution source](scripts/h0_backtest.py).

| Test | Development result | Interpretation |
|---|---|---|
| H4: text change and next-year fundamentals, 2012-2018 | All six absolute t values <= 1.23; primary neutralized-score -> dROA t = -1.20 | No support at the 3.0 bar in these conditional diagnostics |
| H6(a): quiet revision and a formal outcome within 365 days, 2012-2018 | Adjusted association +4.20 percentage points, t = 1.74; 22,745 filings, 499 quiet, 1,103 firms | Exactly reproduces the earlier estimate; below the 3.0 bar |
| H6(b): subsequent CAR(+1..+60), 2023-Jun 2024 | Pipeline diagnostic +4.58%, t = 1.77, 316 events | **INVALID under F2**, not a return finding |
| H5(a), historical; not rerun here | Friday-evening difference +0.97 percentage points, t = 2.01 | Opposite the expected sign; not a replication |
| H5(b)/(c), historical; not rerun here | **INVALID under F2** | Current-ticker distress selection prevents interpretation |

H6(a)'s observed formal-outcome rates are 17.84% versus 13.72%; the 4.02-only descriptive rates are
4.81% versus 1.82%. The broad outcome includes 10-K/A filings that may be Part III-only amendments.
H4 retains its no-support conclusion, but D6 changes its winsorized dROA mean and coefficients.
H4 and neutralized H0 also use current SIC as a fixed proxy, not verified historical classifications.
See [H4 output](results/h4_development.json), [H6 output](results/h6_development.json),
and [historical-versus-rebuilt reconciliation](docs/FINDINGS.md#development-rerun-reconciliation-2026-11-13).

### Relationship extraction (local Qwen 3.5, synthetic benchmark on real 10-K text)

**Historical artifacts, not model runs repeated in this continuation.**

Ground truth comes from construction: fictitious companies are injected into real filing text, with no human labels.

| | Qwen 3.5 4B (300 cases) | Qwen 3.5 9B (80 cases) | Gate |
|---|---|---|---|
| Recall | 0.942 | 0.835 | ≥ 0.80 |
| Precision | 0.956 | 0.981 | ≥ 0.90 |
| Prior-knowledge hallucination | 0.5% | 0.0% | < 2% |
| All ungrounded raw outputs | 5.0% | 0.8% | reported |
| Entity-swap probe: famous real partner leaked | 0/159 | 0/40 | < 2% |

Every accepted link is verified by deterministic quote grounding.

### Change detection

**Historical calibration, not re-executed in this continuation.**

Centering ChronoBERT embeddings fixes their anisotropy. Similarity between unrelated risks drops from 0.971 to 0.045, and AUC on synthetic same-risk vs. different-risk pairs is 0.9999. See `results/change_calibration.json`.

### Executable referee: scoped checks are not release or scientific acceptance

The [executed report](results/REFEREE.md) records its actual source/input provenance.
[Batch B validation](results/batch_b_validation.json) compares its bounded rerun
with the prior defined-gate result. Historical gate PASS did not establish scientific
acceptance. The unused ChronoBERT-vintage and distress-coverage issues persist;
representation/extraction checks read recorded artifacts, not fresh model executions.
**F7 source disagreement and F8 exact-reconciliation failures are release blockers
not automatically covered by the existing referee checks.** No gate was retuned
to explain away those observed failures.

A pass covers the defined checks, not all possible biases, historical SIC availability, scientific
approval, or holdout authorization. Project-level DSR/PBO results, formal claim-level H1, and the
neutralized event co-primary are not established by these runs. The current session-clock helper
uses the fixed 16:00 ET convention and CAR windows index valid observations; early-close and
calendar-gap handling must be qualified before execution or confirmatory event-study claims.
H4's year-cohort neutralization is retrospective, not claimed observable at each filing time.

## Setup

Windows PowerShell:

```powershell
uv venv --python 3.12
uv pip install -e ".[dev]"
$env:ASOF_USER_AGENT = "Your Name your.email@example.com"
.\.venv\Scripts\python.exe -m pytest -q
```

Use the project interpreter for every command. The `embed` extra is needed only for ChronoBERT,
not these development runs. Raw vendor data and processed price datasets stay under ignored `data/`.
Follow the [rebuild runbook](docs/DATA_AUDIT.md#data-rebuild-runbook), including the pilot fixture
and safe Windows process-pool invocation, before running the backtests and referee.
The `prices` stage creates the validated processed snapshot; after a processing/runtime change,
rebuild it with `python scripts/h0_data.py price_snapshot`. Missing or stale snapshots fail explicitly.

## Proposed next gates: approval required, not executed

**Local continuation:** the [bounded gate packet](docs/DATA_AUDIT.md#bounded-gate-advancement-2026-11-13)
contains a proposed development-only source contract, exact method blockers and
reproducibility/holdout decisions. Two narrow implementation corrections have
synthetic-only validation (13 focused tests); they are uncommitted, and the earlier
CI/referee/empirical results above are evidence for their recorded revisions, not
reruns of these changes. No vendor pilot, new study, holdout opening, commit or
publication was authorized or performed by that bounded turn. Hourly automation
is unavailable; completion-triggered Lead handoff is not an always-on monitor.
The [six-package dependency queue](docs/DATA_AUDIT.md#six-package-dependency-queue)
now keeps stable CL-P1 through CL-P6 IDs, versioned designs and blocked operations
explicit. The completed **Research design cards v1** have full design review, not
source revalidation or wholesale scientific approval. Proposed resource/human
ceilings do not release rights or run permissions. Execution's
[P2 source/fixture map](docs/DATA_AUDIT.md#p2-source-to-contract-and-fixture-map)
retains unresolved choices. **Lead-D3a's explicitly approved separate synthetic
planner is now implemented and verified**:
[`asof.timing.plan_return_window`](src/asof/timing.py) uses supplied aware session
closes/readiness/deadlines, post-entry fixed-session intervals and explicit missing/
censored support. It is not wired into historical runners and claims no fill/borrow
feasibility. Queue/P2 v0.2, exact test results and the frozen-runner boundary are in
the [planner contract](docs/DATA_AUDIT.md#lead-d3a-opt-in-synthetic-planner-v02).
That D3a release did not authorize an empirical study, vendor access, simulation
budget, holdout opening or publication. Batch A's later prospective decisions
are recorded below; reserved operational permissions remain separate.

**Batch A v0.3:** prospective overlap/control/industry, decision, observation and
economic contracts are now recorded in the
[bounded offline release](docs/DATA_AUDIT.md#batch-a-prospective-decisions-and-bounded-release).
Supplementary manifest/decision gates, future evidence-label validation,
component-cost arithmetic and a data-free study registry passed **76 focused tests**.
The [supplementary manifest](results/trial_manifest.json) preserves all56attempts
and registered counts; project DSR/PBO remain unavailable.
The [fixed synthetic calibration](results/synthetic_inference_calibration.json)
completed **2,000 attempts in12.625CPU seconds /197.43MiB peak memory**, retaining
six nonfinite panel estimates. Null rejection substantially exceeded normal-reference
nominal rates in these designs: **execution complete is not calibration passed**.
See the [full bounded evidence](docs/DATA_AUDIT.md#batch-a-completion-evidence-offline-not-project-inference).
No additional inference method or empirical claim is validated by that result.
Frozen studies and their labels/costs remain unchanged. D10 discloses the
historical10-Q/A quiet-exclusion wording discrepancy after results, without a rerun.
Vendor contact/keys/spending, human annotation, publication, push/tags and holdout
access remain reserved; this release permits validated **local commits only**.

1. **Rights and historical-source feasibility first; no approved vendor pilot.**
   The earlier free-Tiingo suggestion is a historical premise, not a viable durable
   pilot authorization. [Posted Tiingo terms](https://www.tiingo.com/tos/) updated
   2026-11-05 prohibit Starter/trial durable storage of both data and derived products;
   Power predictive-model permission is internal-use-only, not established public-project
   permission. Sharadar also has disclosure and retention restrictions. See the
   [dated rights reconciliation](docs/DATA_AUDIT.md#current-source-rights-reconciliation-2026-11-13).
   No account-specific/supplemental rights, license, key use, purchase, or publication
   is approved. User approval cannot waive vendor rights. Only after rights are resolved
   could an explicitly approved development-only source pilot qualify dated identities,
   actions and terminal payoffs; F2 coverage >= 0.8 alone is insufficient.
2. **Holdout readiness.** Resolve F2 where applicable, the current-SIC proxy, early-close session
   timing/calendar-gap handling, the event-time neutralization contract, outstanding preregistered inference outputs,
   and F4's historical H4 contamination. Review the ledger, freeze/tag code/config/data/windows,
   and obtain explicit owner approval. Do not silently reseal or relabel contaminated data.
3. **Timing, not authorization.** The October 2026 monthly formation needs returns through
   **2026-11-30**. Under the [scheduled NYSE calendar](https://www.nyse.com/trade/hours-calendars),
   a final late-October event anchored on 2026-11-02 needs its +60th session through
   **2027-01-29**. Recheck actual closures and data finalization before an early-February-2027
   review; valid-observation windows with gaps may extend later until that contract is fixed.
   This is not an automatic opening date. H4/H6(a) require separate label-readiness and
   isolation decisions. Audit July 2024 event-label overlap with the permitted development tail.

Research priorities remain gated: **rights + historical identity/terminal payoffs**
before **calendar/dissemination/event-anchor/gaps + observable labels**, then
**power/dependence/trial families + co-primary inference**, then **blinded human
labels and cheap structural baselines**. Complex modeling comes only after
preregistered evidence gates. These are priorities, not activated studies.

## Data sources and licenses

- SEC EDGAR filings and XBRL APIs: public records.
- Prices: raw prices are not redistributed. **Derived does not automatically mean
  retainable or publishable**; each provider's applicable rights must cover the proposed
  storage, analysis, model use, validation and disclosure. The current terms review is
  not a retroactive rights clearance for historical artifacts or a vendor fitness test.
- Factors: Kenneth French Data Library, which is linked and cited but not re-hosted.

## Provenance of ideas and code

All code in this repository was written from scratch for this project. It contains no code, data, or
unpublished material from any employer. Methods are implemented from public sources and cited
where used: SEC EDGAR documentation, peer-reviewed finance and statistics papers, and public arXiv
preprints (for example, the episode-provenance reconciliation idea described in arXiv:2609.34242).

## License

MIT for code.
