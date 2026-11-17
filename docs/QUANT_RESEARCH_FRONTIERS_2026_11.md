# Beyond text change: quant research frontiers for ChronoLedger

**2026-11-17. Research synthesis, not an experiment, registration or execution approval.**

Repository baseline: `42e27f02c0afe7c1c813baf143f3b5e2b277f074`.
This report develops the economics and computational-finance agenda beyond the
[earlier NLP/econometrics review](RESEARCH_REVIEW_2026_11.md). It examines 24 sources,
including selected full-text material for 11, and distinguishes published results,
working papers, source-access limits and our proposed recombinations.

Only public scholarly/industry research and project documentation were consulted.
No issuer-document cache, real archive/parquet, prices, fundamental observations,
models, simulations, studies or production ledger rows were accessed or run.
External papers' aggregate empirical claims are literature, not project results.
No purchases, keys, institutional entitlements or human/vendor contact were used.

**Subsequent implementation:** under a separate `all_offline` user approval,
the [offline quant toolkit](OFFLINE_QUANT_TOOLKIT.md) now implements bounded
in-memory reference algorithms for all nine directions with invented-fixture tests.
The proposals and authorization statements below retain their original review-time
meaning. That later approval did not authorize empirical studies, model training,
source collection, existing hold removal or a financial-performance claim.

## Executive thesis

**The ambitious project is an economic-information laboratory, not a filing chatbot
with a return predictor attached.**

The central question should become:

> What economically meaningful belief changed, when could an investor first know
> it, why might the market not already have incorporated it, and does any value
> survive measurement uncertainty, risk compensation and implementation costs?

That question connects four research traditions that are usually implemented apart:

1. Information economics: disclosure is a strategic, costly communication process.
2. Stochastic analysis: information arrives irregularly, with economically important order.
3. Asset pricing: cash-flow news, risk and discount-rate news are different objects.
4. Decision theory: uncertain forecasts are inputs to constrained dynamic decisions,
   not instructions to sort everything into a long-short portfolio.

The proposed differentiator is the connection among these traditions. **No claim of
first-in-literature novelty, state-of-the-art performance or tradable alpha is made.**
A credible novel contribution would require a narrower literature search, a frozen
estimand, appropriate data rights, validation labels and new evidence.

The highest-value initial research prototypes would be:

- an **economic-state and innovation representation**, instead of one text-distance score;
- **order-aware disclosure features**, beginning with very small path signatures;
- a **mechanism-twin comparison**, asking what simple economic strategy a complex model
  actually implements;
- an **uncertainty-aware, decay-aware decision layer**, rather than a more elaborate
  optimizer fed unqualified point estimates.

These are proposed new research profiles. None replaces the registered H0/H1/H4/H6
definitions, the [H1 draft](H1_DESIGN.md), stopped studies or original result vintages.

## 1. Schools of thought: ask the right kind of question

| School | Relevant question | Consequence for this project | Common category error |
|---|---|---|---|
| Costly information / noisy rational expectations [C01] | Why is useful public information not already fully in price? | A putative edge must pay for information acquisition, execution and competition | Treating public availability as either proof of no edge or proof of easy arbitrage |
| Rational inattention [C02] | Which information is worth processing under limited capacity? | Separate economic surprise from processing burden and availability | Calling token length, an LLM's entropy or GPU latency the market's Shannon capacity |
| Strategic disclosure / persuasion [C03]-[C04] | Why disclose this fact, in this form, at this time? | Model the observation policy, not only the observed text | Treating missing disclosure as random missing data or automatically as bad news |
| Asset pricing / no-arbitrage [C06]-[C07], [C17] | Is the price move cash-flow news, discount-rate news or compensation for risk? | Separate a better measurement, a risk forecast and an abnormal-return claim | Equating negative language with negative expected excess returns |
| Rough paths / stochastic processes [C08]-[C10] | Does sequence order or event arrival contain information lost by aggregation? | Preserve causal event order, elapsed time and observation masks | Assuming a sophisticated continuous-time model is automatically point-in-time safe |
| Statistical learning and identification [C12]-[C16], [C24] | What can the observations identify, and what is just an inductive bias? | Study both regularization benefits and economic rival explanations | Believing cross-fitting, more parameters or robustness jargon manufactures observations |
| Optimal control / professional portfolio construction [C11], [C23] | What position is worth holding given decay, costs, uncertainty and constraints? | Carry uncertainty and persistence into allocation | Optimizing noisy forecasts and reporting the optimizer's selected maximum as evidence |

These schools are complementary, not competing brands. A forecasting model can be
useful without being causal. A causal disclosure effect need not be tradable.
An informative document can already be priced. A risk forecast can be valuable
without providing a directional stock-selection signal.

## 2. Research bet A: reconstruct economic state, then measure innovation

### The idea

Replace the mental model "new filing minus old filing" with "new observation of an
evolving firm." A firm can change its wording without changing its economics, or
repeat the same sentence after the market has learned that its meaning changed.

A schematic continuous-state block is:

```text
latent economic state:      X_t = A X_(t-1) + u_t
disclosed measurement:      Y_t = H_t X_t + e_t, observed only when M_t = 1
disclosure policy:          P(M_t | X_t, observed public history)
```

This is a research representation, not a fitted model or a claim that corporate
economics is linear-Gaussian. Categorical assertions require categorical observation
models. The operator `H_t` can change when a firm changes definitions, reporting
scope or units. A missing measurement is not a zero state; carrying a stale number
forward does not make it fresh.

Useful state channels could include customer dependence, committed backlog,
capacity, pricing power, funding needs, contractual obligations and uncertainty.
Each needs an operational definition, units, entity/period/scope alignment and
source-grounded measurement. There is no validated model-generated state vector today.

### The genuinely important distinction: novelty relative to what?

Maintain separate concepts:

1. **Document novelty:** new relative to the preceding annual filing.
2. **Observed-public-history novelty:** new relative to eligible earlier filings,
   releases or other licensed sources in the researcher's observable information set.
3. **Market surprise:** new relative to investors' expectations.

The third is not observed simply by building the second. Investors may have private
information or different priors. An 8-K announcing a contract can make a later 10-K
description document-new but not publicly new. Conversely, an unchanged statement
can become economically important after a change elsewhere in the firm's state.

A possible operational innovation is:

```text
innovation_t = audited_state_update_t
               - prediction_of_that_update_from_prior_observed_history
```

For a well-defined probabilistic observation model, predictive surprise can instead
be scored by `-log p(Y_t | prior observed history)`. Raw token surprisal is not
automatically economic surprise, nor a calibrated probability that a claim is true.

Glasserman and Mamaysky [C05] provide a useful precedent: unusualness interacted
with sentiment forecasts volatility in their news setting. Their finding is not
proof that semantic novelty predicts abnormal returns from annual filings.

### The decisive contrasts

Use invented examples initially:

- paraphrase versus an actual change in a customer-concentration percentage;
- industry backlog versus the reporting issuer's contractual backlog;
- a new annual-report sentence repeating an earlier eligible disclosure;
- unchanged wording under a changed metric definition;
- an absent source section versus a deliberate, observable omission.

Then, only under a separately approved study, obtain blinded representative labels.
Modern models may support retrospective measurement under the earlier review's
validation/correction framework. That does not make them historically implementable.

**Falsifier:** apparent innovation is mostly rewording, old public information,
definition drift or extraction failures; a dated numeric/structural baseline explains
the same validated information.

**Why this matters:** this creates a scientifically useful economic measurement even
if return prediction ultimately fails. It is not permission to regrade the frozen KPI run.

## 3. Research bet B: absence and timing are an endogenous observation process

Acharya, DeMarzo and Kremer [C04] model strategic disclosure timing: external bad
news can trigger announcements, whereas good news can delay disclosure in their
setting. Kamenica and Gentzkow [C03] explain why the information structure itself
can be selected to influence a receiver. Neither paper proves that any observed
late filing or omitted metric is managerial deception.

This motivates a joint question:

> Was the economically meaningful event surprising, was its timing surprising,
> and was there a genuine opportunity to observe it?

A marked-event specification could use a predictable intensity:

```text
lambda_i(t) = calendar/deadline/firm baseline_i(t)
              + effects of eligible past events and their economic marks
```

If a complete observation process and a correctly specified intensity are available,
the probability of no event on an interval is `exp(-integral(lambda_i))`.
Silence is informative only relative to such an opportunity set. A parser failure,
uncached document or document excluded by a guard is not firm silence.

Bacry, Mastromatteo and Muzy [C10] provide the Hawkes-process foundation:
past events can affect future intensities, with stationarity conditions involving
the spectral radius of the integrated excitation kernel. The transfer to filings
is a proposal; most examples in that review concern high-frequency markets.

### Start simpler than Hawkes

Compare a calendar/deadline baseline, a renewal or discrete-time hazard model,
then a small marked point process. Annual and quarterly reporting are strongly
seasonal. A constant baseline can misread the reporting calendar or a common
macro shock as self-excitation or contagion.

Distinguish:

- unexpectedly frequent disclosure from unexpectedly negative economic marks;
- missing KPI measurement from evidence that the firm chose not to disclose;
- predictable activity from predictable signed price changes.

The 2026 path-portfolio preprint [C21] explicitly illustrates that excitation in
activity need not produce directional price information. That is a valuable
warning, not an empirical finding about this project.

**Falsifier:** event-timing effects disappear after calendar/common-shock controls,
or intensity predicts only activity rather than economically signed outcomes.

**Gate:** new source qualification, a separately frozen event population and an
observation/censoring contract. This is not a resumption or redesign of H6.

## 4. Research bet C: the algebra of disclosure order

This is the most distinctive computational direction worth examining first.

Two firms can have the same endpoints and the same bag of disclosures but different
trajectories:

```text
Path 1: customer concentration rises -> margins deteriorate
Path 2: margins deteriorate -> customer concentration rises
```

An annual text-distance aggregate discards the ordering. An economic model might
interpret these trajectories differently. That is a hypothesis, not a known effect.

### Small path signatures, not a huge neural model

For a bounded-variation path of predeclared economic channels:

```text
S_i       = integral dX_i
S_ij      = integral_(s < u) dX_i(s) dX_j(u)
Area_ij   = (S_ij - S_ji) / 2
```

Chevyrev and Kormilitzin [C08] explain these iterated integrals, their algebra and
limitations. The antisymmetric level-two term records order-sensitive signed area.

A hand-worked invented example makes the distinction precise. Starting from zero,
take increments `(1,0)` and then `(0,-1)` along axis-aligned segments. The endpoint
is `(1,-1)`, and `Area_12=-1/2`. Reverse the increments: the endpoint is unchanged,
but `Area_12=+1/2`. These are algebraic illustrations, not simulated or financial results.

Important details:

- A signature is translation-invariant: preserve the initial state separately when
  its level matters.
- Reparameterization invariance can discard duration: include a clock channel if
  the elapsed time between disclosures is economically relevant.
- With `d=5` channels **including time**, levels zero through two contain
  `1+5+25=31` coordinates. Starting-state fields are additional.
- The identity `S_ij + S_ji = S_i S_j` means some coordinates are redundant with
  endpoint products. Compare against endpoint changes/products, lags and time gaps.
- Do not feed a 1,000-dimensional embedding into unrestricted second-order features
  and call the resulting million-dimensional expansion new economic information.

### The less obvious leak: interpolation

Morrill, Kidger, Yang and Lyons [C09] show why continuous-time models need adapted
interpolation, not merely dated raw observations. A full-path natural cubic spline
can use future observations. Linear interpolation toward a not-yet-observed knot
also cannot be queried as if that endpoint were already known.

For disclosures, an annual fact learned in March must not be smoothly inserted
into the investor's December state. Use an explicitly causal embedding and check
that appending future events cannot change any earlier feature. A causal transform
still does not certify the underlying SEC clock. Here "causal" means time-adapted,
not identification of a causal economic effect.

Their benchmarks concern medical monitoring, not securities. Neural CDEs are a
later candidate, not the starting implementation. A deterministic low-order
signature plus a regularized linear model would provide a much clearer first test.

### What the 2026 frontier actually adds

Noguer i Alonso [C21] connects signatures, portfolio risk and execution conventions.
The paper explicitly uses **no market data**. Its numerical advantages are from
invented, model-consistent settings; some apparent level-two gains come from
terminal convexity rather than genuine order dependence. Its reported sample-size
ratios are not universal thresholds and are not counts of independent project months.

Borrow the decomposition and estimation-risk questions, not its performance numbers.

**Falsifier:** order-sensitive features add nothing after matched endpoint, lag,
timing and nonlinear-interaction baselines; gains arise only from the symmetric block.

**Initial artifact:** a tiny, interpretable trajectory representation and analytic
counterexamples. No signature library, training run or empirical evaluation is authorized here.

## 5. Research bet D: economic networks need different operators for different jobs

The [existing research plan](RESEARCH_PLAN.md#customer-shocks-travelling-to-suppliers)
already proposes customer-to-supplier effects. The new contribution would not be
"use a graph." It would be a **typed economic transmission model with uncertainty**.

Acemoglu and coauthors [C18] explain how production-network structure can amplify
idiosyncratic shocks into aggregate variation. Cohen and Frazzini [C19] study return
predictability across economically linked firms. Their results do not identify
today's executable opportunity or this project's graph.

For customer-revenue exposure, one could define a dated coefficient `A_ij` as the
share of supplier `i`'s revenue exposed to customer `j`, and begin with a one-hop
shock `A z`. An input-output model may motivate higher-order propagation, such as
an appropriate Leontief inverse under its own accounting and stability assumptions.
An arbitrary LLM relationship score is **not** an input-output coefficient.

Direction, type and units matter:

- customer distress can reduce a supplier's sales;
- a competitor's supply disruption can benefit another producer;
- a creditor exposure is not a product-market similarity edge;
- unknown customer identity is not a license to fill the gap with a modern model's memory.

### A close 2026 paper exposes a useful design choice

Yang and Zhang [C20] extract relationships for 42 selected Nasdaq-100 firms using
recent annual reports. The paper combines filing agents with document-free
background-knowledge agents, and uses IDF-like filtering and relative thresholds.
It is a contemporary network-measurement study, not validation of a historical
all-issuer return strategy.

Useful ideas: explicit versus inferred edges, provenance, dependency direction and
matrix-level measurement audits. Important reasons **not** to copy it wholesale:

1. Parametric prior knowledge can infer historically unnamed counterparties from
   later information. This conflicts with historical implementation unless cleared.
2. Different prompts using the same model are not independent statistical witnesses.
3. A plausible-but-weakly-documented relationship is not an evidence-confirmed edge.
4. A symmetrized community/similarity layer is not the directed transmission operator.
5. **IDF can be appropriate for similarity and inappropriate for systemic risk.**
   A ubiquitous foundry or cloud dependency may be exactly the concentrated exposure
   a risk model should preserve, rather than an "economic stop-word" to downweight.
6. Self-reported confidence, economic exposure size and probability of edge existence
   are different quantities.

This suggests keeping separate similarity, exposure and transmission operators,
rather than one universal knowledge graph. Start with one-hop, directly documented
economic exposure before a GNN. Near-unstable propagation magnifies parameter error;
forcing a convenient spectral radius does not validate the economics.

**Falsifier:** the result is industry/common-factor exposure, future edges, model
prior knowledge, coverage selection or an unsigned activity effect.

**Gate:** dated entity/edge qualification, complete opportunity-set accounting and
a new study approval. No real network construction or graph model was run.

## 6. Research bet E: separate cash-flow information, risk information and alpha

Campbell [C06] supplies the fundamental conceptual split. Under the log-linear
present-value framework and its conditions:

```text
unexpected return = cash-flow news - discount-rate news
```

The empirical decomposition needs a forecasting system; the cash-flow component
can be recovered as a residual. An LLM saying "cash-flow news" is not that identification.

Practical implications:

- better operating news need not produce a positive price surprise if it was expected;
- higher uncertainty can affect discount rates, option prices and risk exposure;
- a correctly measured risk signal need not forecast the same object as mean returns;
- factor-adjusted abnormal returns and improved risk forecasts require different claims.

The no-arbitrage school reinforces this distinction. Chen, Pelger and Zhu [C17]
use pricing restrictions and adversarial test assets rather than treating prediction
error alone as the objective. Their work is motivation to ask what is being priced,
not a reason to fit a neural stochastic discount factor to this project's short panel.

### A serious later extension: cross-market disagreement

After measurement and licensing are qualified, compare a disclosure's economic
implications with contemporaneous options-implied risk, credit or analyst expectations.
Martin and Wagner [C07] connect expected stock returns to option-implied quantities
under their framework. This offers a different lens on required returns.

But risk-neutral quantities are not physical probabilities by default. Options
include risk premia, liquidity effects and maturity structure. Equity/credit/option
disagreement is not automatically an arbitrage or evidence of investor inattention.

This extension requires substantially more qualified data and is **not** a
cheap/free next experiment. No options, credit, analyst or return data was requested.

**Falsifier:** the purported text alpha is compensation for risk or already reflected
in public expectations; it does not survive the predeclared economic rival.

## 7. Research bet F: every complex model gets a mechanism twin

This is the most important lesson from the current complexity debate.

Kelly, Malamud and Zhou [C14], published in the Journal of Finance in 2024, provide
theory and evidence for highly parameterized return models. The right conclusion
is not that simple models always win or that overparameterization is necessarily wrong.

Nagel's 2025 working paper [C15] challenges an important short-window RFF
implementation: similarity between persistent predictors can mostly encode temporal
proximity, making the method resemble volatility-timed momentum rather than learning
the economic predictor relationship. His counterexample uses reversal dynamics.

Kelly and Malamud's response [C16] disputes the implications of recent critiques and
emphasizes effective complexity, implicit regularization, ensembles and limits to learning.
Only its author-page summary was verified here; the site's PDF button returned a
two-page disclaimer rather than the substantive paper. This review does not
independently settle the disagreement.

### The computational insight

For a fixed feature map with training matrix `Phi` and ridge penalty `lambda>0`:

```text
prediction(x) = k(x)' (Phi Phi' + lambda I)^(-1) y
             = a(x)' y
```

The prediction is a weighted combination of training targets. Inspecting the
weights can reveal recency, volatility or cluster effects. This identity does not
say that every learned neural model has fixed target-independent weights.

For each sophisticated candidate, define an economic rival with comparable
exposure, turnover, volatility and costs:

| Candidate | Mechanism twin to beat |
|---|---|
| High-dimensional return model | Recency-weighted/volatility-scaled momentum and ordinary regularized baselines |
| Semantic novelty score | Numeric/structural diff, filing length, section coverage and earlier-public-information controls |
| Signature features | Endpoints/products, lags, gaps and event-count effects |
| Network predictor | Sector/common-shock exposure and dated one-hop links |
| "Uncertainty alpha" | Risk/volatility exposure rather than directional informational advantage |

Use prespecified dependence-respecting null worlds when testing mechanisms. A
naive shuffle can destroy time dependence and produce an unfairly easy null.
An equal-Sharpe rival is not the only failure mode: identical exposures can reveal
that a model is repackaging an already-known strategy.

**Falsifier:** the complex model's output and economics are substantially mimicked
by its twin, with no validated incremental information at comparable implementation cost.

This is model archaeology, not another leaderboard. It directly answers what the
computation bought, and remains useful even when the outcome is "nothing new."

## 8. Research bet G: make the portfolio controller understand uncertainty and decay

Garleanu and Pedersen [C11] connect predictable returns, different decay speeds
and transaction costs. Their linear-quadratic setting produces partial adjustment
toward an aim portfolio reflecting current and expected future opportunities.
It is not generally optimal to rebalance instantly to the current frictionless target.

For this project, the research question is not "which optimizer has the best backtest?"
It is:

> How much of a measured disclosure signal's value remains after delayed availability,
> estimation error, alpha decay, borrowing constraints and trading costs?

A proposed economic objective could be:

```text
maximize expected discounted [
    position * future return
    - risk penalty
    - cost of changing position
]
subject to financing, leverage, liquidity and genuine availability constraints
```

All loss terms must use compatible return/wealth units and the declared horizon.
The original paper's convenient scalar adjustment rule uses additional structure,
including trading costs proportional to the covariance matrix. Linear predictive
dynamics and quadratic costs are not a model of halts, unavailable borrow, gap risk
or arbitrary market impact.

### Put measurement uncertainty into decisions

An illustrative robust mean-variance problem is:

```text
max_w min_(mu in M) [
    w' mu - gamma/2 * w' Sigma w - costs(w - w_previous)
]
```

If, as a mathematical example, `M` is
`{mu_hat + delta: delta' V^(-1) delta <= rho^2}` with `V` positive definite, then:

```text
min_(mu in M) w' mu = w' mu_hat - rho * sqrt(w' V w)
```

This support-function identity is not a claim that we have estimated a valid
confidence ellipsoid. `V` must describe justified mean uncertainty, not arbitrary
LLM confidence scores or the asset-return covariance substituted without explanation.

Esfahani and Kuhn [C12] offer a broader Wasserstein DRO framework with tractable
reformulations. Their statistical guarantees have sampling/tail assumptions;
the iid training setup cannot be silently transplanted to overlapping financial
events and 17-28 dependent months.

Pedersen, Babu and Levine [C23] also emphasize the optimizer's sensitivity to
unreliable portfolios and the role of shrinkage. More accurate covariance estimates
or an elegant optimizer do not validate the expected-return input.

**A useful economic consequence:** a small, slow, well-measured update can be more
valuable than a large, fast-decaying, uncertain update. Whether it actually is so
requires evidence. Neither a hard-coded confidence multiplier nor a tuned uncertainty
radius would establish it.

**Falsifier:** controller gains depend on oracle forecasts, omitted financing costs,
impossible fills or a favorable ex-post uncertainty radius.

## 9. Research bet H: report an identification frontier, not a preferred imputation

The current survivorship limitation should inspire a more rigorous financial
question than "which missing-return default looks reasonable?"

Define a set of admissible worlds: source-clock assignments, dated entity links,
measurement states and economic terminal outcomes consistent with justified evidence.
Ask whether a proposed conclusion survives all those worlds, while respecting their
joint constraints. A source-wide clock offset cannot be independently chosen for
each filing to favor a result.

For a bounded scalar outcome, elementary missing-data bounds can be written:

```text
population mean = observed_fraction * observed_mean
                  + missing_fraction * missing_mean
```

An interval for the missing mean induces an interval for the population mean.
However, **equity returns are not naturally bounded above**. Limited liability
gives a lower bound of -100% for a simple fully paid long equity position, not a
finite upper bound. A missing return on a short position can make a worst-case
long-short lower bound unbounded. Financing/distribution conventions add further issues.

Consequently, a distribution-free finite certificate may be impossible without
additional assumptions. The honest output is `NOT IDENTIFIED`, not a convenient
maximum return chosen after examining strategy performance.

Aronow and Lee [C13] provide related selection-probability sensitivity ideas, but
their bounded-probability framework is not a ready-made cure for a whole distress
stratum with zero coverage. The elementary support argument above is not a claimed
implementation of their estimator.

Useful future outputs would be an **assumption frontier**:

- which conclusion holds under which explicit support/selection assumptions;
- how much source ambiguity changes eligibility versus only a timestamp label;
- where no finite economically interpretable bound can be justified;
- which single piece of evidence would most reduce the identified set.

Distinguish set identification from a sampling confidence interval and from scenario
stress tests. Optimizing over several convenient imputations does not make the set exhaustive.

**Falsifier:** support exists only under one favored completion, or the uncertainty
set excludes plausible failures without evidence.

## 10. Research bet I: eventually make the experiment genuinely prequential

A prospective, separately approved economic-information challenge could be more
credible than repeatedly renovating historical backtests:

1. Freeze model/tokenizer/artifact versions, feature definitions and cheap rivals.
2. Record eligible new information and predictions before future evaluation outcomes.
3. Keep missing predictions and abstentions in coverage accounting.
4. Evaluate measurement, economic prediction and implementation separately.
5. Make version changes prospective rather than rewriting the prediction history.

This is not approval for live collection, paper trading, trading or opening existing
sealed data. Future observations after an approved freeze would define a new study;
the old exposed H4/H6 windows do not become untouched again.

Ramdas and coauthors [C22] explain why valid e-processes support continuous monitoring.
The key is a valid null-specific construction, often using conditional moment or
likelihood restrictions. Relabeling an LLM likelihood or a sequence of positive
backtest returns as betting evidence is not such a construction.

Anytime validity addresses stopping, not model misspecification, source failure,
overlapping-return dependence or the absence of independent market history.
The existing finite-population audit CS solves a different sampling problem.

Similarly, DML [C24] can address nuisance-estimation bias under an identified setup;
it does not make the endogenous decision to disclose a randomized treatment.

## 11. What to prioritize, and what not to build yet

### The best near-term intellectual sequence

| Rank | Proposed work package | Smallest informative artifact | What must be demonstrated before empirical expansion |
|---|---|---|---|
| 1 | Economic state and public-history innovation | A narrow state/observation contract with invented economic contrasts and coverage states | State changes are distinguishable from wording, units, prior public disclosure and missing sources |
| 2 | Disclosure-order algebra plus mechanism twin | A few predeclared low-order signature coordinates, with endpoint/lag/timing rivals | The representation contains the intended order information without future interpolation |
| 3 | Uncertainty- and decay-aware control | Analytic limiting cases and a separately proposed synthetic validation design | No oracle inputs; zero-signal/cost/risk limits behave correctly; assumptions and constraints are explicit |
| 4 | Strategic observation process | Calendar baseline and a specified mark/observation opportunity contract | Absence is observable, not a cache/parser artifact; seasonality is not mislabelled excitation |
| 5 | Typed economic transmission | A directed one-hop exposure contract, distinct from similarity graphs | Economic direction/size and uncertainty are measured, not inferred from present-day memory |
| 6 | Identification/assumption frontier | A mathematical missing-outcome and joint-source-ambiguity specification | Unbounded/unsupported cases remain unbounded or unidentified |
| 7 | Cross-market and prospective studies | New study cards with source rights, estimands, horizon and independent validation | Data, timing, measurement, inference, resource and user-decision gates all pass |

The first three are the strongest proposed research spine, not a request to implement
all seven at once. The ranking is a judgment about scientific value and current
feasibility, not a numeric expected-alpha or project-performance estimate.

### Explicitly reject these shortcuts

- More agents, prompts or a bigger model without a better economic estimand.
- Using a model's own confidence as an independently calibrated measurement variance.
- Treating IDF, graph centrality, token entropy or Hawkes excitation as an alpha theorem.
- Claiming rough-path universality or no-arbitrage training eliminates estimation error.
- Substituting options-implied probabilities for physical probabilities without a model.
- Choosing a new standard error, ridge parameter, uncertainty radius or return support
  after seeing which produces a favorable conclusion.
- Calling thousands of related filings thousands of independent return observations.
- Counting an improved risk forecast, extraction benchmark or hypothetical controller
  utility as a supported registered stock-return hypothesis.

The current [H1 inference and power limitations](H1_DESIGN.md#return-test-calibration-and-power-not-currently-defensible)
remain. Better mathematics must answer a new, explicit question; it cannot erase
the failed small-sample calibration or source qualifications.

### What would make this an exceptional project?

Not a spectacular reported Sharpe ratio. A compelling deliverable would distinguish,
with reproducible evidence, between:

1. the reader could not recover the economics;
2. it recovered the economics but not genuinely new public information;
3. the information was new but already priced or compensated risk;
4. it predicted something, but costs/uncertainty eliminated its decision value;
5. a prespecified, independently validated economic increment survived.

The architecture should make all five outcomes publishable and interpretable.
That is a much stronger contribution than a system engineered to report only the fifth.

## 12. Source register and evidence depth

`M` means relevant full-text definitions/methods or argument sections were read,
**not** that every proof was independently checked or empirical results replicated.
`A` means an author/institution/publisher abstract or publication record was read.
`B` means bibliographic/search-depth verification only. A 2026 HTML conversion date
is not treated as the paper's publication or revision date. These are selected
sources, not an exhaustive systematic review or evidence of first-in-literature novelty.

<a id="c01"></a>
**C01. Grossman and Stiglitz (1980), M.** *On the Impossibility of Informationally
Efficient Markets*, AER 70(3), 393-408.
[Publisher PDF](https://www.aeaweb.org/aer/top20/70.3.393-408.pdf).
Read opening/model discussion, including its distinction between general conjectures
and the solved CARA/normal example. Costly-information equilibrium is not a proof of
this project's informational advantage.

<a id="c02"></a>
**C02. Sims (2003), A.** *Implications of rational inattention*, JME 50(3), 665-690.
[Princeton record](https://collaborate.princeton.edu/en/publications/implications-of-rational-inattention/),
DOI `10.1016/S0304-3932(03)00029-1`. Publisher fetch returned 403; no full-text proof
review claimed. Finite communication capacity is not measured by an arbitrary NLP score.

<a id="c03"></a>
**C03. Kamenica and Gentzkow (2011), A.** *Bayesian Persuasion*, AER 101(6), 2590-2615.
[Publisher abstract](https://www.aeaweb.org/articles?id=10.1257/aer.101.6.2590).
Sender-chosen information structures; not a calibrated model of issuer deception.

<a id="c04"></a>
**C04. Acharya, DeMarzo and Kremer (2011 publication; 2010 WP), A.**
*Endogenous Information Flows and the Clustering of Announcements*.
[NBER record](https://www.nber.org/papers/w16485), AER 101(7), 2955-2979.
Strategic timing under the model's information structure; not a causal late-filing estimate.

<a id="c05"></a>
**C05. Glasserman and Mamaysky (2019), A.** *Does Unusual News Forecast Market Stress?*
[Publisher abstract](https://doi.org/10.1017/S0022109019000127), JFQA 54(5), 1937-1974.
News unusualness/sentiment and volatility. This is JFQA, not JFE, and not a filing-alpha result.

<a id="c06"></a>
**C06. Campbell (1991 publication; 1990 working text read), M.**
*A Variance Decomposition for Stock Returns*.
[NBER record](https://www.nber.org/papers/w3246),
[Harvard PDF](https://dash.harvard.edu/server/api/core/bitstreams/7312037c-6bdc-6bd4-e053-0100007fdf3b/content).
The retrieved PDF identifies itself as January 1990 NBER 3246. Read introduction and
decomposition argument; do not claim line-by-line verification of the final 1991
Economic Journal article. No historical variance-share estimate is transferred here.

<a id="c07"></a>
**C07. Martin and Wagner (2019), A.** *What Is the Expected Return on a Stock?*
[LSE publication/abstract](https://researchonline.lse.ac.uk/id/eprint/90158/),
JF 74(4), 1887-1929, DOI `10.1111/jofi.12778`. Option-implied quantities under an
economic model; not an assumption-free equality between risk-neutral and physical measures.

<a id="c08"></a>
**C08. Chevyrev and Kormilitzin (first 2016; v2 January 17, 2025), M.**
*A Primer on the Signature Method in Machine Learning*.
[Pinned record](https://arxiv.org/abs/1603.03788v2),
[text](https://arxiv.org/html/1603.03788v2), Sections 1.1-1.3.
Definitions, translation/reparameterization properties, order and dimensionality.
The expanded 2025 text is not described as an unchanged 2016 manuscript.

<a id="c09"></a>
**C09. Morrill, Kidger, Yang and Lyons (2021 v1), M.**
*Neural Controlled Differential Equations for Online Prediction Tasks*.
[Record](https://arxiv.org/abs/2106.11028v1),
[text](https://ar5iv.labs.arxiv.org/html/2106.11028), Sections 1-2.
Adapted measurability and interpolation; empirical medical tasks do not validate finance.

<a id="c10"></a>
**C10. Bacry, Mastromatteo and Muzy (2015), M; arXiv v2 text read.**
*Hawkes processes in finance*.
[Text](https://arxiv.org/html/1502.04592v2), Sections 1-2.
Point-process definitions, marks and stability; transfer from microstructure to
scheduled issuer disclosures needs a different observation/calendar model.

<a id="c11"></a>
**C11. Garleanu and Pedersen (2013), M; accepted manuscript read.**
*Dynamic Trading with Predictable Returns and Transaction Costs*.
[Institutional PDF](https://research-api.cbs.dk/ws/files/60191441/lasse_heje_pedersen_et_al_dynamic_trading_acceptedmanuscript.pdf),
DOI `10.1111/jofi.12080`. Read Model and Solution and Propositions 1-4,
PDF pages 9-15. Linear predictor dynamics, quadratic costs and the special
`Lambda=lambda*Sigma` assumption matter; the scalar rule is not universal.

<a id="c12"></a>
**C12. Mohajerin Esfahani and Kuhn (v3 June 13, 2017; 2018 journal publication), M.**
*Data-driven Distributionally Robust Optimization Using the Wasserstein Metric:
Performance Guarantees and Tractable Reformulations*.
[Pinned record](https://arxiv.org/abs/1505.05116v3),
[text](https://ar5iv.labs.arxiv.org/html/1505.05116), introduction/setup and iid assumptions.
The converter's 2026 header is not a new paper version. No dependence-robust
financial calibration of a Wasserstein radius was performed.

<a id="c13"></a>
**C13. Aronow and Lee (2013 issue; online December 2012), B.**
*Interval estimation of population means under unknown but bounded probabilities
of sample selection*, Biometrika 100(1), 235-240.
[DOI](https://doi.org/10.1093/biomet/ass064),
[publisher-deposited metadata](https://api.crossref.org/works/10.1093/biomet/ass064).
Title, authors and dates verified; bounded-selection framing checked in indexed
text, not full methods. Publisher returned 403. No theorem-transfer or implementation claimed.

<a id="c14"></a>
**C14. Kelly, Malamud and Zhou (2024 publication; 2022 WP), A.**
*The Virtue of Complexity in Return Prediction*.
[NBER/publication record](https://www.nber.org/papers/w30217),
JF DOI `10.1111/jofi.13298`. Complexity benefits under a theoretical/empirical setup,
not blanket permission for unconstrained model search in a tiny financial panel.

<a id="c15"></a>
**C15. Nagel (August 2025), M; working paper.**
*Seemingly Virtuous Complexity in Return Prediction*.
[Record](https://www.nber.org/papers/w34104),
[PDF](https://www.nber.org/system/files/working_papers/w34104/w34104.pdf).
Read abstract/introduction and short-window RFF mechanism argument. Its claim
concerns a specific model/regime, not a universal refutation of complex learning.

<a id="c16"></a>
**C16. Kelly and Malamud, A; author-organization response page dated July 10, 2025.**
*Understanding The Virtue of Complexity*.
[AQR page](https://www.aqr.com/Insights/Research/Working-Paper/Understanding-The-Virtue-of-Complexity),
which links SSRN 5346842. The page's date is not asserted to identify the latest
SSRN revision. The PDF button returned only a two-page disclaimer: the substantive
response methods were **not read**. Present both positions without declaring a winner.

<a id="c17"></a>
**C17. Chen, Pelger and Zhu (v6 August 2021), A; working version used.**
*Deep Learning in Asset Pricing*.
[Pinned record](https://arxiv.org/abs/1904.00745v6).
No-arbitrage criterion, adversarial test assets and state extraction. Final journal
version/results were not independently checked here; no neural SDF adoption recommended now.

<a id="c18"></a>
**C18. Acemoglu, Carvalho, Ozdaglar and Tahbaz-Salehi (2012), A.**
*The Network Origins of Aggregate Fluctuations*, Econometrica 80(5), 1977-2016.
[Publisher abstract](https://jstor.econometricsociety.org/publications/econometrica/2012/09/01/network-origins-aggregate-fluctuations),
DOI `10.3982/ECTA9623`. Production networks and aggregate shocks, not a stock-return GNN theorem.

<a id="c19"></a>
**C19. Cohen and Frazzini (2008), A; publisher-deposited abstract.**
*Economic Links and Predictable Returns*, JF 63(4), 1977-2011.
[DOI](https://doi.org/10.1111/j.1540-6261.2008.01379.x),
[Crossref record](https://api.crossref.org/works/10.1111/j.1540-6261.2008.01379.x).
Historical customer-supplier evidence is not an assumed current effect size, executable
cost estimate or qualification of contemporary model-inferred links.

<a id="c20"></a>
**C20. Yang and Zhang (July 17, 2026 v1), M; preprint.**
*LLM Latent Edge Measurement: Point-in-Time Economic Graphs for Quantitative
Investing from Corporate Disclosures*.
[Record](https://arxiv.org/abs/2607.15640v1),
[text](https://arxiv.org/html/2607.15640v1), Sections 1-4.1.
Contemporary selected-42-firm graph; its priors, inferred names and audit labels are
not historical-vintage qualification or independent gold. No published venue or
replicated performance is asserted.

<a id="c21"></a>
**C21. Noguer i Alonso (August 3, 2026 v1), M; preprint.**
*Path Portfolio Optimization: Defect, Lift, and the Price of Path Complexity*.
[Record](https://arxiv.org/abs/2608.02355v1),
[text](https://arxiv.org/html/2608.02355v1), introduction/definitions and explicitly
stated simulation scope. The HTML date header is not used as the submission date.
No market data; no independent proof or reproduction of its numerical comparisons.
Its own attribution says the signature-linear optimizer is prior work, not new here.

<a id="c22"></a>
**C22. Ramdas, Grunwald, Vovk and Shafer (2023 publication; arXiv v2 read), M.**
*Game-Theoretic Statistics and Safe Anytime-Valid Inference*.
[Text](https://arxiv.org/html/2210.01948v2),
DOI `10.1214/23-STS894`, Statistical Science 38(4), 576-597.
Read Sections 1-1.2 on filtrations, predictability and null-valid betting evidence.
Publisher full-text page was blocked; arXiv text used. No financial e-process constructed.

<a id="c23"></a>
**C23. Pedersen, Babu and Levine (2021), A.** *Enhanced Portfolio Optimization*.
[Author-organization publication record](https://www.aqr.com/Insights/Research/White-Papers/Enhanced-Portfolio-Optimization),
which identifies Financial Analysts Journal publication.
Useful professional portfolio-construction perspective; no proprietary implementation,
paper alpha or project covariance improvement is claimed.

<a id="c24"></a>
**C24. Chernozhukov and coauthors (2018 publication; 2017 WP), A.**
*Double/Debiased Machine Learning for Treatment and Structural Parameters*.
[NBER/publication record](https://www.nber.org/papers/w23564),
DOI `10.1111/ectj.12097`. Orthogonal scores/cross-fitting address nuisance estimation
within identified models; they do not supply exogenous disclosure or valid small-T inference.

### Review limits and next decisions

This review did not reproduce a paper, prove all cited results, inspect licensed
replication data or establish a universally best architecture. Public accessibility
of a paper is not permission to reuse its underlying dataset, code or modern models.
Retrieved PDFs remain outside Git; only this synthesis and its links are deliverables.

For retrieval reproducibility, the public PDFs actually inspected have these byte hashes.
They pin those copies, not every published or subsequently revised version:

| Source copy | SHA-256 |
|---|---|
| C01 AEA PDF | `d348bec3517acefec693a57504596a6f5e8fd90be0bfcad09379dde347b32a31` |
| C06 Harvard-hosted 1990 working paper | `52fad21405bb0f70ac2ea37133b62d792c1895c2ba6546134f1877a65bac4165` |
| C11 CBS-hosted accepted manuscript | `8bec9f75161d969089bdab4195b9f31ad8db969723b025e07d36916d913937e9` |
| C15 NBER working paper | `0254d3ca96b0083f1dede3723f614af28685c9b9ee08c307f4fc3c9d102bd4b2` |

The existing two-track distinction still governs: retrospective economic measurement
with proper labels is not historically implementable prediction. Any empirical
extension must respect every reserved source/outcome calendar, D6/D13, source rights,
and current H4/H6 holds. Physical development-only extraction remains a separate,
previously unapproved operation; this report does not implement or authorize it.

**Next decision:** choose a narrow economic-state/trajectory question and its
mechanism twin, then separately approve its specification and any fixture/compute
budget. Do not equate this research agenda with permission to run all candidates.

[C01]: #c01
[C02]: #c02
[C03]: #c03
[C04]: #c04
[C05]: #c05
[C06]: #c06
[C07]: #c07
[C08]: #c08
[C09]: #c09
[C10]: #c10
[C11]: #c11
[C12]: #c12
[C13]: #c13
[C14]: #c14
[C15]: #c15
[C16]: #c16
[C17]: #c17
[C18]: #c18
[C19]: #c19
[C20]: #c20
[C21]: #c21
[C22]: #c22
[C23]: #c23
[C24]: #c24
