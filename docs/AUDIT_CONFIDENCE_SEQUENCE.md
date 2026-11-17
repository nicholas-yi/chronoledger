# Offline finite-population audit confidence sequence

This implements the count-based method proposed in the
[literature review](RESEARCH_REVIEW_2026_11.md#6-a-better-future-timestamp-audit-random-prefix-inference-with-missing-labels).
It does not resume collection, import real audit outcomes, change A2 bounds, qualify UTC or
grant permission to use a historical sample for new inference.

**Implemented and checked on invented data.** The
[executed validation receipt](../results/audit_cs_validation.json) records the single run
from freeze `84b79452fd6ac365781a69c07a35919630ccfef6`. This is implementation QA,
not independent scientific acceptance or a replacement for any stopped audit result.

## Contract and derivation

The unit is a **population member**, such as one accession with its required evidence,
not independent header/index HTTP requests. Freeze before observation: population, binary
error definition, eligibility, uniform without-replacement order, delta and inferential method.
Keep nonrandom priority strata separate. Code cannot verify these assumptions from counts.

Let N be population size, m drawn members, k observed errors and u unread **sampled** members.
Require `0 <= u <= m <= N` and `0 <= k <= m-u`. Unsampled members are `N-m`, not u.
Permanent undefined labels need an explicit conservative target; a transient HTTP status
must not define the supposedly fixed underlying error label. The implementation supports
`1 <= N <= 100000` as an explicit allocation/numerical engineering limit.

With the fixed full-support uniform prior on total errors K in `0..N`, the marginal
probability of s errors in m draws is `1/(m+1)`. Therefore the prior/posterior-ratio (PPR)
set accepts K when:

```text
HypergeometricPMF(s; N,K,m) > delta/(m+1)
```

The [published construction](https://arxiv.org/html/2006.04347v4), Sections 1.1/2,
is time-uniform under its random-prefix model. This implementation conservatively retains
equality and an additional `1e-7` outward log-probability margin. Computation uses SciPy's
double-precision log PMF, not a directed-rounding arithmetic proof.

Unread labels require a **union** over `s=k..k+u`. For each K the hypergeometric PMF is
unimodal in s, so its maximum over those completions is at its mode clamped to that interval.
The code evaluates this maximum rather than O(N*u) separate PMFs. Exact rational
small-state checks compare against the full explicit union independently of that shortcut.

The unknown true completion is included, so the unread union contains the latent
fully observed CS at every time. Thus the union inherits simultaneous coverage, without
a missing-at-random assumption. Unread cases can still leave it uninformative.

The result contains exact accepted integer **intervals**, inclusive, rather than silently
filling gaps in a noncontiguous set. The current snapshot is not intersected with previous
sets; endpoints need not tighten monotonically. Projecting the set to an upper endpoint
is valid under the same coverage event, but is not claimed to be an optimal one-sided CS.

## Offline usage

From the repository, using invented counts:

```powershell
python scripts\audit_confidence_sequence.py --population 80 --drawn 20 --errors 0 --unread 2
```

Stdout is JSON with count intervals, lower/upper fractions, inputs, assumptions and explicit
`sampling_verified=false`, `scientific_acceptance=false`, `qualifies_UTC=false`.
Success means only that the supplied counts were processed. No audit/data files are read or
written by the counts CLI. Invalid counts/levels or numeric failures produce an explicit stderr
error and nonzero exit; there is no success-shaped full-range fallback.

At an observed census with no unread labels, the set collapses to the observed total.
With unread census labels it is `k..k+u`; all-unread or unobserved populations remain `0..N`.
These endpoints include all-zero and all-one populations.

## Validation and run safety

The [frozen invented-data plan](../results/audit_cs_validation_plan.json) specifies 30 cells:
N=80, six error totals, five missingness rules and 1,000 random permutations per cell.
The whole path is checked, plus first-readable-error and precision-triggered stopping.
The QA screen uses simultaneous Bonferroni one-sided CP upper bounds on Monte Carlo
noncoverage. Passing this finite screen does not prove a universal floating-point guarantee
or establish historical sampling/source validity.

Before that run, exact tests enumerate all binary random-order paths for small populations,
compare every small count state against rational hypergeometric probabilities and check
that unread unions contain fully observed sets. The code, tests and plan must be committed
before the synthetic run:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
python -m pytest -q tests\test_audit_cs.py tests\test_audit_cs_validation.py
# Only for the separately approved single validation attempt, after its source freeze:
python scripts\validate_audit_cs.py
```

The validation supervisor is currently Windows-specific; the library/count CLI are not.
Only its owned worker enters a new Windows Job Object with a 1 GiB committed-memory
backstop, no child processes and kill-on-close. The worker is pinned to one allowed logical
processor with single-thread numerical-library settings. The standard-library spawn context
bypasses Windows' virtual-environment redirector; the worker waits on a pipe until its actual
process has joined the job. The idle controller is not a second compute worker.
The controller enforces a 300-second wall timeout, with a 270-second cooperative worker
wall/CPU stop; actual parent/worker RSS peaks are checked separately and summed against
1 GiB. A commit cap is not misrepresented as a hard aggregate RSS cap.

The ignored `data\audit_cs_validation\attempt.json` receipt prevents automatic retry or
resume, even after failure. The summary is written once to
`results\audit_cs_validation.json`; errors/stops cannot pass. On a hard worker failure,
unreported partial paths are unknown, not successful replicates. This harness has no network,
model, pricing or ledger-write code. It hashes the existing ledger, A2 reports and SEC counter
before/after to detect changes; it does not evaluate them.

Source matching permits only Git LF versus Windows CRLF line-ending equivalence; raw-byte
SHA256 values are retained and checked again after computation. The initial `1a0a9c5`
preflight rejected that line-ending difference before any marker, worker or synthetic path.
The [plan](../results/audit_cs_validation_plan.json) preserves that zero-draw failure.
Correcting preflight required a new source freeze, not deletion of an attempt receipt.

If a resource/worker/provenance check fails, keep the receipt, inspect the cause and obtain
a new decision before another attempt. Do not remove the marker to make a run look clean.
The historical A2 CP results and Eastern-clock qualification limits remain unchanged.

## Executed validation: 2026-11-17

The actual attempt began at `2026-11-17T17:36:18.627944+00:00`, from the retained
ignored attempt receipt. No new draws were made after completion.

| Check | Observed result |
|---|---|
| Full offline software suite on the final source | 510 passed, two existing sparse-control rank warnings |
| Ruff | Passed on the five new Python files; not a claim that the legacy repository is lint-free |
| Frozen synthetic allocation | All 30 cells and 30,000 paths completed, 1,000 per cell |
| Largest observed anytime noncoverage | 36/1,000 = 3.6%, N=80/K=40, fully observed |
| Largest simultaneous 95% Monte Carlo upper endpoint | 5.6791%, below the frozen 7.5% implementation-QA tolerance |
| Controller / worker wall time | 20.5285 / 17.9840 seconds |
| Worker process CPU time | 12.6406 seconds |
| Sum of separate controller/worker OS RSS peaks | 337.10 MiB, below 1 GiB |
| Worker affinity | Exactly one allowed logical processor |
| Protected metadata and frozen source | Before/after hashes unchanged |

Per-missingness maxima across the six invented error totals:

| Missingness rule | Maximum failures per 1,000 paths | Simultaneous MC upper endpoint |
|---|---:|---:|
| Fully observed | 36 | 5.6791% |
| Hide every error | 11 | 2.4551% |
| Hide every non-error | 21 | 3.7989% |
| All unread | 0 | 0.6377% |
| Unread positional bursts | 0 | 0.6377% |

**Interpretation:** the fixed QA screen passed. The worst Monte Carlo upper endpoint exceeds
5%, so the experiment alone does not establish a <=5% failure probability. Mathematical
coverage relies on the sampling assumptions and the published construction/conservative
union argument; floating-point behavior was checked only in the stated cases.
The all-unread case covers trivially because its set remains `0..80`, not because it learned
the true error rate. A passing coverage check is not sufficient evidence of informativeness.

The real CLI also processed an invented N=10 census with two observed errors and three
unread labels, returning exactly the inclusive set `2..5`, with all sampling/source
qualification flags false. No actual audit counts were submitted.

Runtime identification read **after** execution: Python 3.12.10 (64-bit), Windows 11
build 26300, NumPy 2.5.4 and SciPy 1.18.1. These are post-run environment observations,
not separately attested package versions captured inside the worker. No dependencies
were installed in this task. Pylance MCP requests timed out; no editor/type-check result
is claimed. Runtime tests, exact comparisons and Ruff provide the stated software evidence.

SHA-256 of the LF-encoded executed report:
`c762ed5e6c204239dfa3b50398a6372a746ed52d7f0e00bc2bc452a73033ad7c`.
The return ledger remains 74 rows and the SEC counter remains 3,254/34,402.
Measurement-error estimators, reader changes, source collection and real-data statistical
adoption were not part of this implementation.
