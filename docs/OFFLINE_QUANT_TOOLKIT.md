# Offline quant reference toolkit

**Status: implemented reference mathematics, not an empirical strategy or study release.**
The user approved `all_offline` on 2026-11-17: all nine directions from the
[frontiers review](QUANT_RESEARCH_FRONTIERS_2026_11.md), with invented-fixture tests,
no downloads, model calls/training, empirical backtests, sealed-data access,
production ledger rows or push.

The implementation is the pure in-memory [research package](../src/asof/research).
There are no dataset loaders, network clients, trained feature maps, broker adapters
or new registered-study runners. No dependency or lockfile change was required.

## What is actually implemented

| Review bet | Working reference algorithms | Not claimed or implemented |
|---|---|---|
| A: economic innovation | [Economic facts](../src/asof/research/economic.py): exact identity/period/definition state compilation, as-of revisions, prior-public-value novelty, compatible numeric updates; finite-state Bayes filtering with informative disclosure/silence | NLP extraction, semantic gold, learned reporting definitions, investor expectations or empirical managerial disclosure probabilities |
| B: observation/timing | [Arrivals](../src/asof/research/arrivals.py): frozen piecewise calendar baseline, bounded marked exponential Hawkes intensity, compensator, conditional no-event probability, likelihood and rescaled event gaps | Parameter estimation, causal managerial intent, financial direction from unsigned activity, stationary inference for a seasonal calendar |
| C: disclosure order | [Trajectories](../src/asof/research/trajectories.py): exact level-two piecewise-linear signatures, Chen concatenation, signed areas and timestamped prefix-only paths with a clock channel | Neural CDE/RDE training, future-knot interpolation, latent intradocument event ordering or validation of a signature-return effect |
| D: typed transmission | [Networks](../src/asof/research/networks.py): dated economic fractions, explicit unknown coverage, directed one-hop effects, stable Leontief propagation; separately, IDF-weighted counterparty similarity | Relationship extraction, inferred identities, economic shares from LLM confidence, a universal risk/similarity graph or a GNN |
| E: risk versus return news | [Pricing](../src/asof/research/pricing.py): supplied-VAR Campbell news identity, finite-state risk-neutral/physical measure conversion, sample SDF pricing moments | Fitting a VAR/SDF, cash-flow identification from text, options-data acquisition or inference on pricing errors |
| F: mechanism twins | [Mechanisms](../src/asof/research/mechanisms.py): fixed-feature dual ridge influence weights, descriptive least-squares reconstruction on supplied rival scores | Learned feature maps, out-of-sample predictive testing, causal attribution or a spanning-alpha test |
| G: decisions | [Control](../src/asof/research/control.py): exact convex open-loop finite-horizon quadratic plan with decay and joint ellipsoidal mean ambiguity | Empirically calibrated means/costs/uncertainty; leverage, cash, borrow, position, fill or trading constraints; stochastic closed-loop optimality |
| H: partial identification | [Identification](../src/asof/research/identification.py): sharp rectangular-support linear payoff bounds and finite-population mean support bounds, including infinite endpoints | Sampling confidence, estimated selection probabilities, joint source-world enumeration, dependent-support optimization or a replacement for invalid distress-return studies |
| I: prequential evidence | [Prequential](../src/asof/research/prequential.py): immutable in-memory forecast/settlement journal, canonical digest, chronological/target constraints, Brier/log scores and conditional-Bernoulli betting evidence | Real collection, authenticated timestamps, persistence, production ledger writes or financial-return anytime-valid inference |

These are complete algorithms for their **stated reference problems**. They are not
implementations of every model in every cited paper. In particular, the controller
uses an ellipsoid, not a Wasserstein distributional ball, and the observation model
is a finite-state assumed-probability model, not an estimated disclosure equilibrium.

Numerical outputs use finite float64 arithmetic. Symmetry/distribution checks use
`1e-12` tolerances, signature shuffle checks `1e-10`, and the controller checks
stationarity against `1e-8 * max(1, norm(linear_term))`. These are engineering
tolerances, not financial significance thresholds or statistical guarantees.

## Execution and access boundary

Use the existing locked project environment:

```powershell
uv run --no-sync pytest -q tests\research
```

The fixtures contain invented issuers, values, probability models and timestamps.
They are software/math checks, not synthetic performance studies, empirical return
trials or calibration of statistical size/power.

All empirical access still requires the existing shared document/dataset contracts,
source rights, appropriate study approval and resource authorization. The current
H4/H6 holds remain unchanged. No function here grants permission to provide reserved
inputs that were read elsewhere. D6/D13 remains a permanent qualification.

The [integration fixture](../tests/research/test_no_io_integration.py) calls all nine
directions with Python-level tripwires for file opening, network connection and
production trial logging. This is a regression check after module imports, not an
OS filesystem/network sandbox. Source timestamps, hashes, node completeness and
economic measurement quality remain caller declarations.

## A. Economic facts and finite-state beliefs

`MetricKey` separates issuer, economic metric, canonical unit, reporting scope and
definition. `Observation` adds period end, declared aware knowledge time, source ID,
numeric value and explicit coverage. Dates are normalized using the shared
[`aware_utc`](../src/asof/timeutil.py) helper, which does not certify the source clock.

`state_as_of`:

- selects the latest eligible observation per exact metric-period;
- rejects duplicate source/metric/period identities and simultaneous conflicting values;
- uses a canonical source ID for identical concurrent observations;
- keeps a later unavailable measurement unavailable rather than replacing it with
  an older number;
- does not learn unit conversions or merge definitions/periods.

`public_innovation` compares against the **latest** prior state for the same key and
period. Repeating an earlier eligible disclosure is already public; reverting from
value A to B and back to A is a new revision relative to B, not an old-value cache hit.
An unavailable prior state produces explicit unavailable novelty.
This tests exact declared facts, not semantic novelty or actual market surprise.

`numeric_update` requires compatible observed keys and forward chronology, and
allows either an explicit same-period revision or a later period. It does not annualize,
seasonally adjust or call a repeated same value in a different period old news.

The finite-state filter uses a row-stochastic transition `T`, prior `p`, state-dependent
disclosure probabilities `d` and category emission probabilities `e`:

```text
predicted       = T' p
observed update = normalize(predicted * d * e)
silent update   = normalize(predicted * (1-d))
```

`silent` means an observable reporting opportunity with no disclosure.
`unavailable` and `no_opportunity` use prediction only and report no evidence probability.
They cannot consume emitted/disclosure evidence. Impossible observations raise;
there is no uniform-posterior fallback. No probabilities are estimated or calibrated.

## B/C. Arrival clock and path representation

The point-process clock is measured in UTC days. With frozen calendar rate `mu(t)`:

```text
lambda(t) = mu(t) + sum_(event s<t) a*b*mark_s*exp(-b*(t-s))
```

`0<=a<1`, `b>0`, and normalized excitation sizes in `[0,1]` provide an upper bound
on feedback strength. Marks are not signed return forecasts. Calendar segments are
ordered/nonoverlapping, frozen before their start, and must cover a requested interval.
No missing calendar rate is filled with zero. Instantaneous rates use half-open
calendar segments; evaluating an event at an uncovered final boundary fails explicitly.

The compensator integrates realized event history. Conditional survival instead
conditions on history through the forecast origin and assumes **no later event**:
it cannot use future realized arrivals or future baseline estimates unavailable at
that origin. The likelihood uses events in `(start,end]`; its rate excludes the event's
own excitation. Zero-intensity observed events raise. Exponential rescaling is a
model diagnostic only when the assumed complete conditional process is correct.

For piecewise-linear increments `dx`, the signature recursion is:

```text
second += outer(first, dx) + outer(dx, dx)/2
first  += dx
```

`Signature2` checks the shuffle identity `second+second' = outer(first,first)`.
Features include the level-zero constant; areas are `(second-second')/2`.
Initial economic levels are returned separately. `causal_trajectory` selects the
eligible prefix, adds elapsed UTC days, and does not interpolate toward future knots.
Ineligible future values do not change the prefix, even when those values are missing.
Tied timestamps are rejected: paragraph order is not asserted economic event order.
The dense implementation is capped at 64 channels as an engineering bound, not an
optimal scientific dimension.

```powershell
uv run --no-sync python -c "from asof.research.trajectories import signature2; print(signature2([[0,0],[1,0],[1,-1]]).area()[0,1])"
```

Expected output: `-0.5`, an exact invented path illustration, not an estimated effect.

## D. Economic exposure is not a similarity matrix

Exposure is indexed by a fixed node universe, economic denominator/type, period end
and aware knowledge cutoff. `A[i,j]` is the supplied fraction of affected entity `i`
exposed to counterparty `j`. Types are customer revenue, supplier cost and creditor
assets. Shares sharing a denominator cannot sum above one. Newer eligible edges
supersede earlier values; conflicting simultaneous edges and inferred identities fail.

Missing pairs are unknown unless the caller explicitly declares the affected row
complete. An unknown fraction remains unknown even in a declared-complete row.
Propagation refuses any unknown pair. Completeness is not verified by this module.

`one_hop` computes `A z`. `leontief_total` computes `(I-A)^(-1)z`, including the
direct shock, only for spectral radius below one. This is a stipulated linear
propagation model, not an estimated causal stock-return relationship.

`shared_counterparty_similarity` separately computes IDF-weighted cosine on a complete
binary incidence matrix. Empty rows fail because cosine is undefined. It neither
alters the exposure operator nor converts confidence into economic magnitude.

## E/F. Pricing identities and model archaeology

For a supplied linear VAR, innovation `epsilon`, return selector `e`, and discount
parameter `rho`:

```text
discount-rate news = e' rho*A (I-rho*A)^(-1) epsilon
unexpected return = e' epsilon
cash-flow news    = unexpected return + discount-rate news
```

The discounted forecast sum must converge. The decomposition needs the underlying
log-linear present-value conditions; it is not identification from a language label.
`physical_probabilities` implements `p proportional to q/m` for a **supplied**
positive finite-state pricing kernel, using log-space normalization. It does not
estimate that kernel or equate risk-neutral with physical probabilities.
`pricing_moments` returns sample `mean(m*excess_payoff)` without inference or SDF fitting.

For a fixed feature map, `kernel_weights` returns:

```text
a = (Phi Phi' + penalty*I)^(-1) Phi*query
prediction = a' supplied_targets
```

The positive ridge penalty is explicit. Influences may be negative and need not
sum to one; they are not probabilities or independent-bet counts.
`project_on_twins` provides an in-sample descriptive reconstruction, residuals,
RMS and an explained fraction. It requires residual degrees of freedom/full rank;
constant candidate scores have an undefined explained fraction, not a default 100%.
No OOS performance, statistical significance, causal explanation or cheap-rival
dominance can be established from the descriptive projection alone.

## G. Exact reference controller and its limits

The controller forecasts `mu_t = persistence**t * initial_mean`, with a supplied
operator whose spectral radius does not exceed one. It maximizes:

```text
sum_t beta**t * (w_t' mu_t - gamma/2*w_t' Sigma*w_t
                - 1/2*(w_t-w_(t-1))' Lambda*(w_t-w_(t-1)))
minus rho * sqrt(w' D*V*D*w)
```

`D` stacks discount factors, `V` is the SPD geometry of the **joint stacked mean
forecast error**, and `w` stacks the open-loop position path. This is one ellipsoid
across the entire horizon, not independent per-period robust optimization.
Return covariance is SPD, cost geometry PSD, `gamma>0`, and `0<beta<=1`.
Risk, cost and uncertainty inputs are supplied; no statistical confidence coverage is
asserted for an arbitrary `V` or radius.

The minimization form is:

```text
1/2*w'Hw - b'w + rho*sqrt(w' V_effective w)
```

If `sqrt(b' V_effective^(-1)b)<=rho`, zero is optimal. Otherwise the implementation
solves `w=(H+eta*V_effective)^(-1)b` with
`eta*sqrt(w' V_effective w)=rho`. A bounded scalar root parameterization avoids an
unbounded search near the zero-position threshold, and the output must pass a
stationarity check. No generic optimizer success flag substitutes for that check.

The result includes nominal and worst-case objective values, positions, forecast
means and a stationarity residual. These are mathematical objective values, not
observed investment returns. The cap is 256 total position coordinates.

**Important limitations:** open-loop finite horizon, no terminal liquidation charge
unless represented in a different explicit problem, no stochastic policy feedback,
no budget/leverage/borrow/fill constraints, no bid-ask or financing model, no deployable
portfolio. Huge leverage is not prevented by this unconstrained reference problem.
No trading adapter consumes its output.

## H/I. Identification and prequential accounting

`payoff_bounds` is exact for a linear payoff over a rectangular product of supplied
outcome intervals. Negative weights reverse endpoints. Unknown simple-long equity
support `[-1,+infinity)` therefore gives an unbounded lower payoff for a short.
A zero-weight unknown still appears in coverage counts. No arbitrary upper return
cap is inserted. `mean_bounds` also handles entirely missing populations; an empty
population is an error. Observed outcomes must be exact finite points and cannot
contradict the declared support.

These are identified sets under support assumptions, not confidence intervals.
Dependencies, common-clock constraints and mutually exclusive identity mappings
require a joint feasible set not represented by these rectangular bounds.

The in-memory journal records declared source/artifact readiness, model/input/target
SHA-256 identifiers, created time and a strictly future binary target. Appends return
new immutable journals; duplicate forecasts/targets, backdating, early labels and
duplicate settlements fail. The digest is canonical for the recorded declarations,
not an external timestamp, signature, authenticated approval or persistent audit trail.

As-of scores exclude future settlements and retain abstentions and unresolved mature
targets in separate counts. Proper Brier/log scores are computed only where an emitted
probability has a revealed label; impossible predictions have infinite log loss
without probability clipping.

For the explicitly stated conditional null
`P(Y=1 | all previously revealed information)<=p0`, a previously committed
`lambda in [0,1/p0]` gives factor `1+lambda*(Y-p0)`. The journal reports log wealth.
Zero wealth is `-infinity`, not an exception or a fabricated positive value.
Abstentions require a reason and zero stake.

The conditional-null requirement is substantive: a correlated batch of labels,
post-hoc targets, unqualified sources or arbitrary financial returns do not inherit
this guarantee. This is distinct from the existing finite-population audit CS,
registered NW inference and the production trial ledger. Nothing is written to any
of those systems.

## Verification provenance

Focused [fixtures](../tests/research) use independently worked scalar/geometric-series,
signature-order, conjugate-probability, matrix-normal-equation, convex stationarity,
missing-support and conditional-null expectations, plus rejection cases and the
all-nine no-I/O integration check. They do not establish economic truth, realistic
model probabilities, estimator efficiency or predictive performance.

Pylance's workspace-symbol request timed out in this session. Runtime fixture checks,
the existing regression suite and Ruff are the available verification evidence;
no successful editor type-check is claimed.

Initial toolkit validation on 2026-11-17, with numerical library thread counts set to one:

| Command | Observed result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | 629 passed in 70.78 s; two existing synthetic rank-deficiency warnings |
| `.venv\Scripts\python.exe -m ruff check .` | Passed with the repository's existing documented legacy baseline |

The full suite includes 32 new reference-toolkit tests and the prior 597 regressions.
No scientific power/coverage study, empirical return trial or cloud validation was
performed. No real data, production ledger rows, registered designs, dependency pins,
study holds or frozen historical outputs were changed. These local changes are not pushed.

Under a later `synthetic_and_plan` approval, a [separately frozen known-truth stress run](QUANT_SYNTHETIC_RESULTS.md)
completed all nine areas within 34.21 s and approximately 164.8 MiB combined peak RSS.
Its pre-execution controller/software suite passed 637 tests. The results preserve
the important negative/adverse controls and are not empirical performance evidence.
The accompanying [empirical pilot](QUANT_EMPIRICAL_PILOT.md) remains blocked.
