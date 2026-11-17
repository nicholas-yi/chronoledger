# Literature-backed research upgrades

**Review date: 2026-11-17. Research recommendations, not new results or authorization.**

Repository evidence baseline: `6c280d470924938ad97ee2f3bd4a9aea1315ff22`.
Public literature was checked against primary abstract/publication records and, for the
central methods, relevant full-text sections. This is a targeted review, not an exhaustive
systematic review or a claim that one model is universally state of the art.

No SEC or market-data requests, project model inference, training, simulations, return
evaluations, source repairs, holdout access, purchases or human/vendor contact were performed.
Paper-level published aggregate results are literature, not results from this project.
Existing registrations, failed experiments and the sealed holdout remain unchanged.

## Executive recommendation

**Make the next contribution a trustworthy measurement system before trying to make it an
investment strategy.** The most promising upgrades are not another output grammar or a larger
collection of trading signals:

1. **Separate retrospective economic measurement from historically implementable prediction.**
   Current econometrics gives a constructive route to using imperfect modern LLM measurements
   with genuine validation labels. It does not certify historical trading performance.
2. **Measure evidence localization, claim alignment and computation separately.**
   Start with narrowly scoped real filing-pair labels and an oracle-evidence diagnostic.
   The project's observed source-selection failures make this more valuable than more
   format engineering.
3. **Use a prospectively frozen finite-population confidence sequence for future random
   audits, with explicit accounting for unread sampled cases.** This handles operational
   stopping without pretending unread cases are correct or that all planned-but-unvisited
   cases have already been sampled.
4. **Investigate validation-sample correction of AI measurement error.**
   MAR-S, PPI++ and active statistical inference are useful research directions, with different
   assumptions. None supplies free human gold or additional independent return months.
5. **Choose economic effect size and statistical geometry before choosing another return test.**
   More qualified history may help; changing the standard-error formula until it passes does not.

The strongest recent additions to the reading list are FinFIRST (September 2026),
FinMRAGBench (ACL Findings 2026), the 2026 publication of Ludwig, Mullainathan and Rambachan's
econometric framework, Carlson and Dell's February 2026 MAR-S revision, and the April 2026
revision of Active Statistical Inference. Publication and version status are distinguished
in the [source register](#source-register).

## 1. What the local evidence actually suggests

| Existing observation | Research implication | What it does not establish |
|---|---|---|
| [REAL2](../results/reader_real2_combined.json): 11/30 correct with the report | Real financial reading remains difficult | Paired-claim extraction accuracy or an economic signal |
| [REAL3 diagnosis](../results/reader_real3_diagnosis.json): five of nine strict-format misses primarily concerned selected cells/spans; two involved native conversion conventions | Separate retrieval/selection, reasoning, execution and evaluation contracts | A blinded causal estimate of which replacement will work; the diagnosis was post hoc |
| [Batch E](../results/robust_inference_calibration.json): none of NW6, EWC or NW fixed-b qualified at T=17/18/28 | Improve the design and information available, not just the named estimator | Mathematical impossibility of all small-sample inference; exact classical inference is possible under much stronger assumptions |
| [A2](../results/timestamp_full_a2_review.json): one discrepancy among 314 readable internally agreeing cases, conditional on Eastern | Stored-source agreement is not a sufficient validation rule | A verified UTC error rate or a sequentially valid cohort certificate |
| [Source panel](../results/price_source_test_panel.json): proposed cases, not observed vendor coverage; no dedicated CVR case | Economic terminal wealth and identity need direct qualification | That a current-price API, brand name or structurally valid intake packet supplies complete returns |

These are development observations and recorded methodological checks, not new findings.
The [draft H1 card](H1_DESIGN.md) remains the authority for its proposed claim tuple, comparison
universe, unweighted union denominator and incremental contrast. Its real-label thresholds
remain proposals; its registered prerequisites are not weakened here.

## 2. Two scientific tracks, not one ambiguous backtest

### Track A: retrospective, human-defined economic measurement

Define a source-grounded concept that humans can measure without knowing subsequent returns:
for example, whether a compatible assertion was introduced, removed or modified between two
specific versions of a filing. Use an imperfect model to scale that measurement, and use
a representative, independently labelled validation sample to correct the relevant statistical
moments.

[Ludwig, Mullainathan and Rambachan](#s11) distinguish this estimation problem from prediction.
[Carlson and Dell](#s12) make the measurement-error correction explicit, including aggregation
and transformation issues. This creates a potentially useful academic contribution even if
the current model did not exist when the documents were published.

**The claim would be about a defined historical economic concept, not about an algorithm
that was tradable then.** A modern model's raw proxy score is not automatically that concept.
Validation, source/version identity, an appropriate sampling design and valid downstream
inference are still necessary. Human labels must remain blind to returns.

### Track B: historically implementable or genuinely prospective prediction

This requires the historical information set, eligible model/tokenizer/artifact versions,
timing and execution feasibility. The registered ChronoBERT requirements and unresolved
artifact mapping remain in force. Alternatively, a separately approved future study can
freeze open weights before collecting genuinely new documents and outcomes.

[Chronologically Consistent Large Language Models](#s19) motivates dated vintages, but its
paper does not certify the particular artifacts used here. [Glasserman and Lin](#s20) show
why company knowledge can affect results. Masking names, asking a model to ignore the future,
retrieval, or fine-tuning on old text does not erase its pretraining.

The econometric framework's random-sampling examples concern explicitly defined target
populations; randomizing a set of old filings does **not** make a modern model historically
available or establish generalization to genuinely future markets.

**Decision:** keep Track A and Track B labels separate in all future study cards. A change of
scientific target needs a new prospective design; it cannot reclassify the original H1 or
turn already exposed development returns into a new clean test.

## 3. Upgrade the reader by diagnosing evidence, not adding syntax

### 3.1 What current financial NLP supports

| Method or benchmark | Useful idea | Transfer limitation |
|---|---|---|
| [FinFIRST](#s01), 2026 | Atomic criteria for raw information, authoritative/time-valid sourcing, and computation; entity, period, scope and unit alignment | An open-search financial research benchmark, not paired-claim change or historical tradability |
| [FinMRAGBench](#s02), 2026 | Test cross-page and cross-document evidence completeness | Its trained multimodal agent is not a demonstrated drop-in solution for a CPU-only 4B reader |
| [TAT-LLM](#s03) | Extractor -> reasoner -> external executor | A trained task-specific pipeline; stronger zero-shot formatting alone is not the intervention |
| [DocFinQA](#s04) | Compare retrieval with long-context reading and isolate evidence retrieval | Public QA, with reused FinQA questions; not fresh project gold or a chronological evaluation |
| [FinNLI](#s05) | Include a supervised encoder/NLI baseline instead of assuming bigger models dominate | Financial entailment is not cross-year claim alignment |
| [FinDVer](#s06), [ContractNLI](#s07), [REFinD](#s08) | Evidence spans, entailment/contradiction/not-mentioned distinctions, and directional relation errors | None supplies this project's paired-report change labels |

DocFinQA's average context is about **123,000 words**, not tokens, versus short supplied
contexts in the original tasks. A larger context window is therefore not a sufficient
engineering plan under the existing memory budget. Retrieval also needs to retain table
headers, footnotes and evidence spanning multiple chunks.

FinNLI reports best compared PLM/LLM macro-F1 values of 74.57%/78.62%. That is a reason to
include a compact task-trained baseline, not a predicted project score, a current universal
leaderboard or evidence that either model fits this machine.

### 3.2 Smallest useful new measurement study

Propose a **block-scoped calibration pilot**, not exhaustive whole-filing H1 certification:

1. Freeze a few financially meaningful metric families and a fixed set of eligible paired
   blocks, including ordinary unchanged cases, real numeric changes, paraphrases, negations,
   missing coverage, tables, segment scope and fiscal-period rollover.
2. Have two humans independently mark claims, evidence and cross-report correspondence;
   adjudicate disagreements. Time the first calibration work before projecting a large budget.
   AI suggestions are not either independent first pass.
3. Diagnose on calibration data using the **same reader with oracle evidence versus its own
   selected evidence**. The oracle arm is a diagnostic upper-bound condition, not an operational
   system or a fresh untouched-audit result.
4. Freeze at most a small set of realistic systems: the existing answer-first baseline,
   a structural/lexical retrieval baseline with deterministic calculation where applicable,
   and one evidence-localization/reranking/verifier candidate. Report every configuration.
5. Evaluate later on company-separated, time-separated, unexposed audit material. Do not
   recycle the exposed REAL2/REAL3 IDs as fresh tests.

For each system measure:

- Evidence/cell recall and precision, with exact entity, metric, period, scope and unit checks.
- Conditional answer correctness **given correct evidence**, plus end-to-end correctness.
- Claim unitization and alignment agreement, NEW/REMOVED/modified confusion and rare-class support.
- Coverage, abstention, unsupported assertions and failure reasons; not just accuracy among answers.
- Native benchmark scoring separately from economically meaningful evidence correctness.
- Runtime, peak owned memory and throughput; the cache-zero smoke did not validate long reports.

Use company/pair-aware uncertainty, not thousands of correlated claims counted as independent.
A small pilot can diagnose failure modes but cannot automatically support a precise lower
confidence bound or certify whole-filing recall.

### 3.3 Candidate architecture: source first, comparison second

This is a proposal for a separately frozen study, not an edit to the current H1 card's
no-retrieval extraction specification:

```text
pinned source version and layout
    -> evidence candidates with stable paragraph/table/cell IDs
    -> entity/metric/period-role/unit/scope compatibility
    -> independent claim extraction within each filing
    -> candidate matching between the extracted claim sets
    -> entailment/change verifier with explicit unmatched/unknown cases
    -> deterministic numeric normalization/execution
    -> source-linked measurement and coverage report
```

For cross-report alignment, investigate constrained bipartite matching with unmatched nodes,
rather than accepting every nearest embedding neighbor as equivalent. Do not force one-to-one
matching when the annotation guide identifies a legitimate split/merge: such cases need a
declared representation or an unknown outcome.

Embeddings can propose candidates; they cannot establish financial equivalence. Entailment
also needs correct period roles: different years' revenues are not logical contradictions
merely because their values differ. Preserve actual dates and distinguish current-year
rollover from a restatement of the same historical period. Extract filings independently;
do not let the earlier report cause the current extractor to invent an omitted assertion.

Add metamorphic checks for paragraph order, harmless formatting, duplicate assertions,
exact unit conversion and meaning-preserving paraphrase, with expected invariance. Deliberate
changes of entity, scope, polarity, forecast/actual status and quantity should produce the
declared non-invariant outcome. These are engineering checks, not substitutes for real labels.

Source-only financial extraction must not silently borrow current external knowledge from
knowledge-intensive benchmark tasks. In particular, FinDVer's external-knowledge tasks have
a different information-set contract.

## 4. A close 2026 disclosure paper: borrow the idea, not its alpha

[Choi et al., From Text to Alpha](#s10), v5 dated March 2026, is especially close to this project.
It extracts context-qualified performance metrics with an LLM, then compares their embeddings
to measure the disappearance of previously emphasized metrics. Its main empirical material
is **earnings calls**, not paired 10-K/10-Q claims.

Useful transfer: narrow the extraction target, preserve qualifiers such as business segment,
and compare semantic counterparts rather than surface words. A metric-omission pilot may be
much easier to label than unrestricted propositions across whole filings. It is nevertheless
a **different estimand** from H1's proposed union of new, removed and modified claims.

The full-text review also found reasons not to use its reported returns as a validation target:

- Section 5.1 selects similarity thresholds using **predictive performance** and
  interpretability. A clean separate tuning/test boundary is not established by that description.
- It applies Gemini-2.5-Pro and text-embedding-3-large to historical observations. This does
  not satisfy this project's historical model-vintage contract.
- Table 4 reports the LLM moving-target coefficient with **t=-0.95**; the conclusion claims
  significance at 10%. The displayed statistic does not support an ordinary two-sided
  10% significance claim.
- Its stated January 2010-December 2024 interval contains 60 calendar quarters, while Table 1
  reports 64. Extra comparator history might explain this, but that reconciliation is needed.
- The text does not establish the dated S&P 100 membership/complete economic-return contract
  required here. This is an unresolved replication question, not proof of what its code did.

**Adoption recommendation:** test the measurement architecture against genuine labels and cheap
baselines. Do not import its thresholds, significance claims or expected alpha.

A separate tempting search hit, [FinAgent-RAG](#s32), was withdrawn in July 2026 for fundamental
experimental-design errors. Its benchmark scores and cost-reduction claims are excluded.
Search snippets and old full-text mirrors still displaying those numbers are not valid evidence.

## 5. Correct the use of model measurements, not just their average accuracy

### 5.1 Why a 90% accurate extractor can still bias a regression

Let `C*` be the defined human claim-change measurement and `C_hat` the model's proxy.
If their errors differ by company size, distress, period, disclosure style or outcome-related
content, plugging `C_hat` into a return regression need not produce simple attenuation.
High aggregate accuracy does not determine the sign or size of the downstream bias.

This is the central lesson of [the applied econometric framework](#s11) and [MAR-S](#s12).
The measurement target must be explicit, not whatever score a convenient model happens to emit.

### 5.2 Which newer methods to investigate

| Method | Potential use here | Conditions and non-claims |
|---|---|---|
| [PPI](#s13) / [PPI++](#s14) | Estimate label-defined population quantities using a validation sample and many predictions; adapt the amount of reliance on the predictor | The basic setup uses labelled/unlabelled observations from the same distribution. PPI++ regression intervals use asymptotic normality; this is not a finite-sample T=17 guarantee |
| [MAR-S](#s12) | Correct relevant moments when the missing human-defined variable is a covariate, or labels are aggregated/transformed | Fixed annotation definition, representative/MAR validation, known positive annotation probabilities or additional estimation assumptions, sample splitting and appropriate inference |
| [Active Statistical Inference](#s15) | Allocate later annotation effort to informative examples while preserving a specified population estimand | Actual randomized query probabilities and weighted correction, not just selecting uncertain cases and treating them as a random audit |
| [Learn then Test](#s16) | Select among predeclared abstention/verifier policies with high-probability risk control | Independent calibration, valid per-policy tests and multiplicity control. It may return no acceptable policy |
| [Conformal Risk Control](#s17) | Calibrate an appropriate monotone expected loss | Exchangeability and monotonicity matter; an expected-risk guarantee is not a 95%-confidence conditional-precision guarantee under temporal shift |

For intuition, in the simple independently sampled mean problem with a fixed predictor, a
prediction-powered estimator has the form:

```text
estimated mean = mean(predictions on unlabelled sample)
                 + mean(human label - prediction on validation sample)
```

With known randomized annotation probability `pi_i > 0`, a related active-inference mean
estimator averages `f_i + A_i * (Y_i - f_i) / pi_i` over the sampled units. These are
illustrations of residual correction, not formulas to paste unchanged into H1.

Important project-specific limits:

1. **H1's missing human variable is a predictor.** Passing it to a PPI API intended for missing
   regression outcomes is not automatically correct. Derive the actual moments involving
   the true claim measurement, its square/cross-products where needed, returns and controls.
2. A corrected mean claim count does not automatically correct a ratio score, its ranks,
   portfolio membership or Sharpe ratio. MAR-S addresses some transformed/aggregated targets;
   non-smooth sorting and this project's dependence structure need separate justification.
3. Labels only on convenient years, surviving companies or keyword-positive claims do not
   establish the full population's error process. Preserve positive sampling probability
   across the declared population, and retain known probabilities.
4. Fine-tuning, tuning an abstention rule and final independent auditing need distinct roles
   for labels. Do not spend the untouched audit set twice.
5. The main baseline theories do not turn repeated company/date observations into iid units.
   Cluster/time extensions require verification. Bias correction can add variance.
6. Human agreement and adjudication quality still matter. Arbitrarily noisy labels cannot
   correct arbitrarily noisy model outputs without additional assumptions.

**Best next research experiment:** a separately approved invented-data study comparing oracle
measurement, naive proxy regression, validation-only regression and correctly specified
validation-corrected moments. Include errors related to observed covariates, biased annotation
selection, imperfect human labels and company/time dependence. Freeze the methods and pass/fail
criteria before running it. This would test applicability, not produce an economic finding.

## 6. A better future timestamp audit: random-prefix inference with missing labels

### 6.1 Preserve the stopped A2 result and distinguish the questions

The existing fixed-batch report remains unchanged:

- 3,270 selected random-rest accessions; 3,269 eligible internally agreeing cases.
- 320 visited; 314 readable comparisons and six visited unread cases.
- 2,949 eligible selected cases unvisited.
- The one observed discrepancy yields the recorded complete-case nominal CP upper bound
  of about 1.50%. The declared adverse completion of all 2,955 unread/unvisited cases yields
  the recorded upper bound of about 91.26%.

That adverse scenario is useful for the **fixed selected batch**. It is not the only possible
future scientific question. A finite-population random-sampling design instead asks:

> What fraction of a frozen eligible population has the defined discrepancy, using a
> random-order prefix, even if the audit stops early?

Unsampled members then contribute sampling uncertainty; sampled-but-unread members contribute
unresolved labels. These are different uncertainties. Neither can be silently discarded.

### 6.2 Applicable published method

[Waudby-Smith and Ramdas](#s18), Sections 1.1 and 2, construct confidence sequences for a fixed
finite population observed in uniformly random order without replacement. Their binary
construction uses a hypergeometric model and a full-support working prior:

```text
M_m(K) = prior(K) / posterior_m(K)
C_m   = {K in 0..N : M_m(K) < 1 / delta}
```

`K` is the population number of errors. The sets simultaneously cover the true `K` with
probability at least `1-delta`, under the sampling model. This supports optional stopping.
The Bayesian-looking working distribution is a device for a frequentist guarantee, not a
claim that the source-error rate has a scientifically established Bayesian prior.

**The theorem does not let us throw away unread cases or preferentially reorder difficult
filings.** Priority disagreement/CIK strata must stay distinct from the genuinely random
remainder; stratum-specific and simultaneous guarantees require their own frozen allocation
of error probability. Known eligibility can define a random subsequence only when it is
fixed independently of the audit outcomes.

### 6.3 Conservative construction worth implementing and checking offline

For the count-based, unintersected binary CS above, suppose `m` population members were drawn,
`k` readable cases are errors and `u` sampled cases have unresolved labels. A conservative
set is:

```text
C_missing,m = union over j=0..u of C_m(k+j)
```

Here `C_m(s)` means the published count-based CS evaluated with `s` errors in `m` draws,
using the same frozen `N`, prior and `delta`. This is a **union**, not an intersection.

Why the construction is conservative under those assumptions: the actual unresolved error
count is one of `0..u`, so the set for the fully observed latent sample is contained in the
union. Simultaneous coverage of that latent-sample CS implies simultaneous coverage of the
union. This does not require missingness to be random, but selective unread cases can make
the result uninformative.

This is a project-specific conservative adaptation, **not an implementation or calibrated
new project result**. Before use, verify:

- A fixed population and binary label definition, including how permanent source ambiguity
  enters a conservative certification target. A transient HTTP outcome cannot itself be
  mistaken for a fixed underlying timestamp-discrepancy label.
- Complete random-prefix accounting, including failures; no successful-response-only sample.
- Full support including `K=0` and `K=N`, impossible counts, numerical stability, and the
  difference between a count-based set and a path-dependent running intersection.
- Exact small-population enumeration and separately approved synthetic coverage checks,
  including outcome-dependent stopping and adversarial unread cases.
- Prospectively fixed inferential choices, strata, population estimand and error budget.
  Selecting this method after seeing A2 does not retroactively preregister it.

Do not assign a new numerical bound to the old A2 result in the meantime. A future study
would need an explicitly frozen new protocol and separate request authorization, not an
automatic continuation or a relabelled historical certificate.

For a simpler fixed-sample design, zero errors in **299 independent Bernoulli observations**
gives a one-sided 95% CP upper bound just below 1%:
`1 - 0.05**(1/299) = 0.009969...`; 298 is insufficient.
This is only a planning illustration. A finite-population audit uses its own sampling model,
claims within a company are not independent Bernoulli observations, and unread cases still
need explicit treatment.

All timestamp comparisons remain conditional on the labelled Eastern assumption.
Even an excellent bound on agreement with a header under that assumption does not establish
the historical field's UTC definition. Source error frequency also does not by itself bound
portfolio impact or validate calendar, identity and execution assignments.

## 7. Quant research: design for credible information and economic value

### 7.1 Do not shop for a small-sample standard-error cure

[HAR Inference](#s21) motivates EWC/fixed-b methods and size-power tradeoffs, not universal
validity at seventeen months. [The cluster guide](#s22), [CR2/BRL work](#s23),
[Ibragimov-Mueller](#s24) and [cluster leverage diagnostics](#s25) explain why the number,
independence and leverage of groups matter.

Ibragimov-Mueller relies on approximately independent, approximately Gaussian group estimates;
seven groups alone are not sufficient. CR2 corrects variance under a working model and uses
approximate degrees of freedom, not exact inference under arbitrary seven-cluster dependence.
The already observed project calibration failures take precedence over a generic paper's
favorable examples.

The actual [Batch E record](../results/robust_inference_calibration.json) has worst upper
bounds on nominal 5% null rejection of 39.06% (NW6), 13.40% (EWC) and 19.08% (NW fixed-b)
at T=17. All failed the frozen adoption tolerance. The separate [F10 record](FINDINGS.md#f10-synthetic-finite-sample-size-distortion-of-the-registered-tests)
also warns about the registered rare-tail screen; there is no new validation here.

With six factors plus an intercept, full-rank OLS leaves `T-7` residual degrees of freedom.
The incremental claim-versus-cosine regression adds another predictor, leaving `T-8`:
only nine at T=17. More firms can improve cross-sectional precision/diversification but
cannot be counted as additional independent market months. Fama-MacBeth coefficients are
still a time series; overlapping 60-session CARs do not become independent by being stored
on daily rows. Leverage or volatility rescaling alone does not improve the signal-to-noise ratio.

### 7.2 An optimistic planning scale, not a project MDE

For a simple iid Gaussian mean with **known** monthly standard deviation, no estimated
factors, no selection and no dependence, an approximate 80%-power scale is:

```text
T ~= ((c + normal_quantile(0.80)) * sigma / delta_effect)**2
```

The following are hypothetical monthly net effects/volatilities, not observations:

| Effect | Standard deviation | c=1.959964, conventional two-sided 5% planning | c=3.2, arithmetic illustration only |
|---|---:|---:|---:|
| 30 bp/month | 1%/month | 88 months | 182 months |
| 30 bp/month | 3%/month | 785 months | 1,634 months |

The numbers round the calculated sample-size scale upward, using exact standard-normal
quantiles. They are not calibrated factor-regression power, estimates of this project's
volatility, or validation of a normal interpretation of the registered t=3.2 screen.
They show why a meaningful effect size and realistic variability must precede another
backtest. The minimum meaningful incremental **net** effect remains an owner/scientific
decision, not 30 bp adopted by this report.

Before any future economic evaluation, freeze the exposure map, qualified data/universe,
time geometry, effect margin and a **single preselected calibration design**. Older data
are not automatically unseen: prior analyses and hypothesis-specific exposure must be
reconciled. Do not open the existing holdout to solve a power problem.

### 7.3 Use realistic opportunity sets and implementation costs

[Chen and Welch's July 2026 preprint](#s26) reports that the median return of roughly 200
published anomaly portfolios falls to about 7 bp/month when restricted jointly to post-2005
years and non-micro stocks. That is a **portfolio-return** result in their study, not a
factor alpha, the expected H1 effect or proof that no new anomaly exists.

Conversely, [Jensen, Kelly and Pedersen](#s27), published in the Journal of Finance in 2023,
find broad replication evidence using a Bayesian framework and 93-country data.
These studies have different universes, aggregation, estimands and implementation questions.
Do not cherry-pick either into a universal verdict.

For this project:

- Keep the original registered output separate from a new matched-sample incremental contrast
  against the same filing-pair cosine strategy. Standalone claim alpha does not prove
  incremental information.
- Report gross performance, observed versus assumed costs, turnover, capacity assumptions
  and break-even cost. Do not transfer a large institution's cost coefficients directly:
  [Frazzini, Israel and Moskowitz](#s29) study a particular real execution setting.
- Low-turnover bands or a long-only use case may be sensible **new** implementation studies.
  They change the portfolio/benchmark question and cannot rescue a failed registered spread.
- Separate acceptance, dissemination, observation on the chosen channel, completion of
  computation, order cutoff and fill. A correct timestamp does not make the closing print
  executable. Any alternative latency/execution convention requires a declared new design.
- Require dated share-class identity, all contractual payoff legs and the correct adjustment
  basis. [Shumway](#s28) demonstrates why delisting omissions matter; it does not prescribe
  today's missing payoffs. No last-bar liquidation, zero return or blanket -100% can be
  called a sourced recovery. Do not append a delisting leg already included in a return field.

### 7.4 Multiple testing comes after valid inputs

Keep the append-only return ledger and all failed/null configurations. Existing DSR and
[PBO/CSCV](#s30) are diagnostics, not repairs for time leakage, invalid null size,
survivorship, missing terminal wealth or unmodelled costs.

[e-BH](#s31) is a useful future method for a properly defined family with valid null
e-values, including dependence between tests. But a null e-value must satisfy
`E[E_value] <= 1`; converting an invalid NW p-value does not establish that property.
This is lower priority than source validity and test calibration, and not permission for
unbounded adaptive model/prompt/horizon search.

## 8. Proposed work sequence and adoption decisions

These are research recommendations to turn into separately scoped/frozen cards, **not**
approved jobs. No durations, annotation budget, source access or compute allocation are
implicitly granted.

| Order | Work package | Required inputs | Deliverable and decision |
|---|---|---|---|
| 1A | Offline finite-population CS and unread-label accounting | Published construction, mathematical review, explicitly approved synthetic validation budget; no network needed | Reproducible coverage/edge-case checks or documented failure; no A2 replacement bound |
| 1B, independent of 1A | Small real measurement pilot | Confirmed source identity/version, handling permission, two humans and adjudication; no price history needed just to study reading | Timed annotation, disagreement analysis and oracle-evidence diagnostic; decide whether the concept/reader is worth scaling |
| 2 | Evidence-localization and claim-alignment comparison | Frozen pilot definitions, company/time split, fresh audit inputs, pinned candidate artifacts and resource approval | Same-sample baseline comparison with evidence/semantic/coverage/runtime metrics; stop if baselines suffice or rare classes remain unsupported |
| 3 | Validation-corrected estimation feasibility | Explicit target moments and annotation probabilities; first an approved invented-data study | Compare oracle, naive proxy, validation-only and corrected estimators; retain failure if dependence/selection defeats the proposed method |
| 4A | Rights-first economic-return source qualification | Owner approval for terms/contact/access, fixed case/field contract and resolved authority gaps | Case-level identity/action/payoff reconciliation and independently reviewable rights; no vendor clearance from a schema pass |
| 4B, independent of 4A preparation | Economic effect/geometry decision | Defined scientific target, exposure map, meaningful net margin and qualified inference-design review | A defensible prospective calibration/power plan, or an honest decision not to run a return test |
| 5 | A bounded economic study, only if justified | Measurement, source, timing, inference/power, execution and authorization gates all met | Registered output and explicitly separate new contrasts, logged regardless of null/invalid/positive outcome |

The [existing intake tools](../scripts/check_research_intake.py) already prepare empty
human/source packets and structural checks. Another intake schema or readiness badge will
not produce the missing labels or legal/economic evidence.

### What not to prioritize

- More strict-output permutations on the exposed questions; that line is retired.
- Training a model before there is a stable target and genuine error-labelled data.
- Buying a bigger model or using multi-agent agreement as human gold.
- Reproducing a paper's largest reported alpha while overlooking its tuning or information set.
- Plugging a time-series foundation model, deep RL optimizer or larger factor zoo into
  incomplete data and treating complexity as validity.
- Calling public financial-QA performance fresh paired-claim validation.
- Weakening a scientific threshold, changing a horizon or releasing the holdout because
  the present study has little power.

### A useful outcome even with no trading edge

A reproducible source-grounded paired-filing measurement benchmark, a transparent negative
result about model generalization, and an audit procedure that handles operational stopping
honestly can each be substantive contributions. Publication readiness, privacy/rights and
scientific acceptance still require independent review. This review establishes neither
profitability nor acceptance of a particular proposed method.

## Source register

**Evidence depth:** `M` = relevant full-text methods/assumptions reviewed, not every proof
independently verified; `A` = primary abstract/publication or author-institution record;
`R` = current repository documentation, not a pinned dataset release; `X` = excluded.
Preprint-version dates come from bibliographic records, not converter-generated HTML date
headings. A version read on arXiv is not labelled unpublished merely because a venue was not
independently established.

<a id="s01"></a>
**S01. Wang et al. - FinFIRST (2026), M; preprint.**
[v1 record](https://arxiv.org/abs/2609.25192v1),
[methods](https://arxiv.org/html/2609.25192v1), Sections 1-2.
123 expert-authored tasks and atomic sourcing/acquisition/computation criteria.
Borrow the diagnostic rubric, not a claim that its leaderboard measures H1.

<a id="s02"></a>
**S02. Yang et al. - FinMRAGBench (2026), A; ACL Findings publication.**
[Primary publication](https://aclanthology.org/2026.findings-acl.187/),
DOI `10.18653/v1/2026.findings-acl.187`.
887 expert-verified QA pairs; cross-document/multi-page evidence. Full training/results
were not independently reproduced or used to select a project model.

<a id="s03"></a>
**S03. Zhu et al. - TAT-LLM (2024), M; v3 record reports ICAIF acceptance.**
[Record](https://arxiv.org/abs/2401.13223),
[v3 methods](https://arxiv.org/html/2401.13223v3), Introduction and pipeline.
Task-specific training plus external execution, not a grammar-only improvement.

<a id="s04"></a>
**S04. Reddy et al. - DocFinQA (2024; v3 October 2025), M; arXiv version read.**
[Record](https://arxiv.org/abs/2401.06915),
[v3 methods](https://arxiv.org/html/2401.06915v3), Sections 1-3.
7,437 questions, 801 source documents and about 123k-word average contexts.
Questions inherit FinQA provenance; public release does not establish fresh evaluation.

<a id="s05"></a>
**S05. Magomere et al. - FinNLI (2025), A; NAACL Findings publication.**
[Primary publication](https://aclanthology.org/2025.findings-naacl.257/),
DOI `10.18653/v1/2025.findings-naacl.257`.
21,304 NLI pairs, including 3,304 expert-annotated test instances. Domain shift and the
compared encoder/LLM results motivate a proper financial entailment baseline.

<a id="s06"></a>
**S06. Zhao et al. - FinDVer (2024), A/R; EMNLP publication.**
[Publication](https://aclanthology.org/2024.emnlp-main.818/),
[repository description](https://github.com/yilunzhao/FinDVer).
The published abstract describes four subsets; the current README describes three and
a July 2026 annotation release. Pin the actual release/schema before reuse; do not merge
the paper and live repository descriptions into a fabricated single frozen dataset.

<a id="s07"></a>
**S07. Koreeda and Manning - ContractNLI (2021), A; record reports EMNLP Findings acceptance.**
[Primary record](https://arxiv.org/abs/2110.01799).
607 contracts with evidence-linked entailment/contradiction/not-mentioned annotations.
Its negation/exception problems motivate diagnostics, not financial task equivalence.

<a id="s08"></a>
**S08. Kaur et al. - REFinD (2023), A; primary arXiv record with related ACM DOI.**
[Record](https://arxiv.org/abs/2305.18322),
related DOI `10.1145/3539618.3591911`.
Approximately 29k financial relation instances, 22 relations and eight entity-pair types.
Not a paired-filing change benchmark.

<a id="s09"></a>
**S09. Shah et al. - Numerical Claim Detection in Finance (2024), A; FEVER workshop publication.**
[Primary publication](https://aclanthology.org/2024.fever-1.21/),
DOI `10.18653/v1/2024.fever-1.21`.
Analyst-report/earnings-call claim detection and SME-informed weak supervision.
Useful label/task context; neither weak supervision nor a licence stated on this page
clears this project's whole information-set/data-use contract.

<a id="s10"></a>
**S10. Choi et al. - From Text to Alpha (2025; v5 March 2026), M; preprint.**
[Pinned record](https://arxiv.org/abs/2510.03195v5),
[full text](https://arxiv.org/html/2510.03195v5), Sections 3-5, Tables 1/4 and conclusion.
Relevant architecture, but the tuning/inference/version questions in Section 4 above
preclude adopting its economic claims as a validation target.

<a id="s11"></a>
**S11. Ludwig, Mullainathan and Rambachan - Large Language Models: An Applied Econometric Framework, M.**
[NBER record](https://www.nber.org/papers/w33344),
[methods read](https://arxiv.org/html/2412.07031v4), Sections 2-4.
NBER working paper 33344, 2025; the NBER record verifies a 2026 Annual Review of Economics
publication, DOI `10.1146/annurev-economics-120925-105620`. The journal full text was not
independently compared line by line with the working version.

<a id="s12"></a>
**S12. Carlson and Dell - A Unifying Framework for Robust and Efficient Inference with Unstructured Data, M; preprint.**
[v3 record](https://arxiv.org/abs/2505.00282v3),
[methods](https://arxiv.org/html/2505.00282v3), Introduction and Sections 2-3.
First 2025; v3 February 2026. MAR-S requires an explicit annotation target, MAR and
positive annotation support; generic iid/asymptotic theory is not small-T financial certification.

<a id="s13"></a>
**S13. Angelopoulos et al. - Prediction-Powered Inference (2023), A; arXiv version read.**
[Primary record](https://arxiv.org/abs/2301.09633).
Validation residuals plus many predictions. This review's detailed assumptions/computational
discussion relies on PPI++ and the later frameworks rather than claiming every original
PPI theorem was checked.

<a id="s14"></a>
**S14. Angelopoulos, Duchi and Zrnic - PPI++ (v2 March 2024), M; arXiv version read.**
[Record](https://arxiv.org/abs/2311.01453),
[methods](https://arxiv.org/html/2311.01453v2), Sections 1-2.
Same-distribution iid labelled/unlabelled setup, power tuning and asymptotically normal
M-estimation intervals. Do not turn its efficiency motivation into a finite-sample dominance promise.

<a id="s15"></a>
**S15. Zrnic and Candes - Active Statistical Inference (2024; v3 April 2026), M; arXiv version read.**
[Pinned record](https://arxiv.org/abs/2403.03208v3),
[methods](https://arxiv.org/html/2403.03208v3), Sections 2-4.
ML-guided randomized label collection with propensity correction; not unweighted
uncertainty sampling or synthetic human labels.

<a id="s16"></a>
**S16. Angelopoulos et al. - Learn then Test (2021; v5 September 2022), M; arXiv version read.**
[Record](https://arxiv.org/abs/2110.01052),
[methods](https://arxiv.org/html/2110.01052v5), Sections 1-2.
High-probability risk control via valid tests and family-wise error control over candidate
policies, using independent calibration data.

<a id="s17"></a>
**S17. Angelopoulos et al. - Conformal Risk Control (2022; v4 June 2025), M; arXiv version read.**
[Record](https://arxiv.org/abs/2208.02814),
[methods](https://arxiv.org/html/2208.02814v4), Sections 1-2/Theorem 1.
Exchangeable monotone bounded losses and expected-risk control. Not the same guarantee as LTT.

<a id="s18"></a>
**S18. Waudby-Smith and Ramdas - Confidence sequences for sampling without replacement (2020; v4 January 2021), M.**
[Record](https://arxiv.org/abs/2006.04347),
[methods](https://arxiv.org/html/2006.04347v4), Sections 1.1/2, Proposition 2.1 and Theorem 2.1.
Fixed finite population, uniform random order, time-uniform uncertainty. Venue status is
not needed for the specific pinned construction reviewed here.

<a id="s19"></a>
**S19. He, Lv, Manela and Wu - Chronologically Consistent Large Language Models (2025), A.**
[Primary record](https://arxiv.org/abs/2502.21206), v3 July 2025.
Use the pinned working version. A search-discovered 2026 publisher version could not be
read here and is not used to certify final-publication details or project artifacts.

<a id="s20"></a>
**S20. Glasserman and Lin - Assessing Look-Ahead Bias in Stock Return Predictions Generated By GPT Sentiment Analysis (2023), A.**
[Primary record](https://arxiv.org/abs/2309.17322).
Look-ahead and company-knowledge distraction are distinct; anonymization is diagnostic,
not universal decontamination.

<a id="s21"></a>
**S21. Lazarus, Lewis, Stock and Watson - HAR Inference: Recommendations for Practice (2018), A; JBES publication.**
[Author-institution record and abstract](https://discovery.ucl.ac.uk/id/eprint/10160486/),
DOI `10.1080/07350015.2018.1506926`.
Fixed-b/EWC size-power guidance, not validation of the project's exact small-sample geometry.

<a id="s22"></a>
**S22. MacKinnon, Nielsen and Webb - Cluster-Robust Inference: A Guide to Empirical Practice (2022 working version), A.**
[Primary record](https://arxiv.org/abs/2205.03285), which reports Journal of Econometrics acceptance.
The correct identifier is `2205.03285`; `2205.03288` is a different paper below.

<a id="s23"></a>
**S23. Pustejovsky and Tipton - Small sample methods for cluster-robust variance estimation and hypothesis testing in fixed effects models, A.**
[Corrected v2 record](https://arxiv.org/abs/1601.01981v2),
related journal DOI `10.1080/07350015.2016.1247004`.
The November 2022 revision corrects a theorem statement. BRL/CR2 and Satterthwaite-style
approximations are candidates under assumptions, not automatic exact seven-cluster inference.

<a id="s24"></a>
**S24. Ibragimov and Mueller - t-Statistic Based Correlation and Heterogeneity Robust Inference (2010), A; JBES publication.**
[Author-institution record](https://collaborate.princeton.edu/en/publications/t-statistic-based-correlation-and-heterogeneity-robust-inference/),
DOI `10.1198/jbes.2009.08046`.
The record explicitly states independence/Gaussianity of limiting group estimates.

<a id="s25"></a>
**S25. MacKinnon, Nielsen and Webb - Leverage, Influence, and the Jackknife in Clustered Regression Models: Reliable Inference Using summclust, A.**
[Primary record](https://arxiv.org/abs/2205.03288), v3 November 2023.
Use for cluster leverage/influence diagnostics, not as the source identifier for the guide.

<a id="s26"></a>
**S26. Chen and Welch - What Useful Alphas? (July 2026), A; preprint.**
[Pinned primary record](https://arxiv.org/abs/2607.06502v1).
The abstract's modern/non-micro result motivates realistic opportunity sets; its aggregate
claims have not been independently replicated here and do not define H1's expected alpha.

<a id="s27"></a>
**S27. Jensen, Kelly and Pedersen - Is There a Replication Crisis in Finance? (2023 publication), A.**
[NBER working-paper/publication record](https://www.nber.org/papers/w28432),
Journal of Finance DOI `10.1111/jofi.13249`.
Bayesian replication framework and 93-country evidence; no version-mixed replication percentage
is asserted in this review.

<a id="s28"></a>
**S28. Shumway - The Delisting Bias in CRSP Data (1997), A; Journal of Finance publication.**
[Author-institution record and abstract](https://scholarsarchive.byu.edu/facpub/9278/).
Foundational evidence on omitted terminal losses, not a current vendor field-format
qualification or a justification for a blanket imputation.

<a id="s29"></a>
**S29. Frazzini, Israel and Moskowitz - Trading Costs (2018), A; author-organization working-paper page.**
[Primary description](https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs).
Real execution data and cost heterogeneity; the institution's setting and execution process
do not identify this project's costs.

<a id="s30"></a>
**S30. Bailey, Borwein, Lopez de Prado and Zhu - The Probability of Backtest Overfitting (2017), A.**
[Author-institution record](https://scholarworks.wmich.edu/math_pubs/42/).
CSCV/PBO diagnoses strategy selection among configurations; not data-integrity certification.

<a id="s31"></a>
**S31. Wang and Ramdas - False discovery rate control with e-values, A; pinned arXiv version.**
[v5 record](https://arxiv.org/abs/2009.02824v5), December 2021.
Null expectation control is required before e-BH's dependence robustness is relevant.
The publisher page was inaccessible in this review; no publisher full-text verification is claimed.

<a id="s32"></a>
**S32. Shu, Liu and Xie - Agentic Retrieval-Augmented Generation for Financial Document Question Answering (2026), X; withdrawn.**
[Authoritative withdrawal record](https://arxiv.org/abs/2605.05409).
v2, July 5, 2026: methodological errors fundamentally invalidate the conclusions.
Not a supported source of SOTA scores or expected cost savings.

### Access and verification limits

Some publisher pages returned HTTP 403, including the searched 2026 overlapping-observation
regression article, the ChronoBERT journal-version lead, the open-source asset-pricing
publisher page and SSRN cost-paper pages. No access restriction was bypassed. Search-only
or inaccessible results are not treated as verified methods; accessible working versions
and explicitly labelled primary abstracts supply the claims actually used.

The [2026 NBER methods-lecture description](https://www.nber.org/research/videos/2026-methods-lecture-melissa-dell-and-ashesh-rambachan-estimation-and-inference-ai-generated-data)
independently identifies measurement with AI-generated data as a current econometric topic.
The lecture recording was not watched and is not cited as independent verification of proofs.

No benchmark data or weights were downloaded, no paper's strategy was rerun, and no dataset
licence was inferred from an article's open-access licence or a repository badge. The current
481-test software result belongs to the preceding implementation task and was not rerun
for this documentation-only review. Local link/anchor checks and the displayed analytic
planning arithmetic are documentation validation, not scientific acceptance.
