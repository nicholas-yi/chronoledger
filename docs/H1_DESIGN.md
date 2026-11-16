# Claim-level change (H1): draft study card and annotation guide

**DRAFT, not registered.** The return test is not currently adequately calibrated
or powered. The measurement audit needs two human annotators, who have not been
recruited, and an adjudicator. AI pre-labels are suggestions only, never human
gold. No annotation, model run, data acquisition or return evaluation is authorized
by this document.

This integrates Research's **CL-R-H1-PRICE completion, 2026-11-16**, with the
Lead's verification of the calibration and power arithmetic at 14:05 ET.
It is a proposed design, not an observed result or a replacement for the
registrations. The July 2024-October 2026 return holdout remains sealed; the
existing stock-price cutoff remains 2024-07-31. The proposed annotation sample
ends with filings from June 2024.

## Study card: H1-CLAIM-INCREMENTAL-DRAFT-01

### Question and registered boundaries

Does a faithfully measured change in disclosed claims add return information
beyond the **same filing-pair word-level change signal**? The registered direction
remains high change followed by lower returns; the portfolio orientation is
low-change minus high-change. Disclosure change is not necessarily truth change,
business deterioration, surprise to all investors, fraud or causality.

Read this alongside [v1](PREREGISTRATION.md), [v2](PREREGISTRATION_V2.md),
[deviations](DEVIATIONS.md), the [research plan](RESEARCH_PLAN.md) and
[README](../README.md). Preserve original H1, its registered extraction
requirements, ChronoBERT-vintage requirement, development/holdout division,
monthly/event definitions, missing-return scenarios, costs, N and literal
v1-AND-v2/D3 success rules. H1n remains neutralized cosine, **not formal H1**.

The operationalization below proposes an explicit implementation/new-study
contract where the registration is underspecified. Material differences need a
versioned prospective registration/deviation, never a silent rewrite. This is
not yet ready to register: artifact pins, rights, human resources and a valid
inferential design remain unresolved, not parameters to guess.

### Claim and change unit

An atomic claim is one source-supported proposition with these fields:

```text
claim_id, entity_id_or_text, predicate, object_or_value, currency, unit, scale,
fiscal_period_start/end, period_role, segment/geography/scope, actual_vs_forecast,
modality, polarity, source_accession, section, text_offsets_or_table_cells,
evidence_spans, extraction_status
```

A sentence containing two independently assessable propositions produces two
claims. Table cells inherit their row/column headers and relevant footnotes.
Exact duplicate assertions across text and tables count once, retaining every
evidence location. Normalize quantities without inventing precision. Do not
conflate dollars and percentages, revenue and profit, consolidated and segment
figures, fiscal and calendar periods, or actuals and forecasts.

Match only compatible entities, predicates, scopes and period roles across
eligible reports. Retain actual period dates: rolling "current fiscal year" from
one annual report to the next is not itself a substantive change, but a change
in its reported value can be. Separately mark a correction to the same historical
period as a restatement. Do not force different metrics/entities into a modified
pair.

| Label | Operational definition |
|---|---|
| NEW | No compatible earlier claim within the completely observed, eligible comparison universe. Not necessarily newly true. |
| REMOVED | No compatible current claim, with complete comparable coverage. Not automatically retracted or false. |
| MODIFIED_NUMERIC | A matched claim changes normalized quantity, range, date or duration; exact unit conversion alone does not qualify. |
| MODIFIED_QUALITATIVE | A matched claim changes relationship, polarity, condition, modality, status or material scope. |
| UNCHANGED | Semantically equivalent after permitted formatting/unit normalization. |
| UNKNOWN/UNMATCHABLE | Evidence or correspondence is insufficient; not zero change. |

Use multiple flags for simultaneous numeric and qualitative modification, but
count the matched relation **once** in the signal. Explicit retraction and
supersession are separate evidence-backed flags, preserving the registration's
new/superseded/retracted vocabulary rather than equating deletion with retraction.
Boilerplate, formatting and out-of-scope content have separate exclusion reasons.

### Proposed extraction and reconciliation specification

1. Use only text/tables available by the accepted/disseminated availability clock.
   Preserve accession, version and amendment availability; never replace the
   original with an amendment before its actual availability. Use approved
   timing/calendar contracts, dated security identity and historical SIC.
   Unknown dated SIC means a neutralized-score abstention; a raw score may remain.
2. Select annual-to-annual and same-fiscal-quarter year-earlier comparisons as
   specified in v2. Adjacent mixed 10-K/10-Q filings are not interchangeable with
   that comparator. Reconcile a 10-K/A at its own availability, distinguishing
   administrative from substantive changes.
3. Extract each report independently, without retrieval, web access,
   company-memory completion, return information or importance inferred from
   later outcomes. Evidence offsets and typed fields are mandatory. Then align
   claims and classify changes using the fixed tuple rules. Content claims
   without supporting source spans fail validation.
4. Candidate extractor weights are the already-used local `qwen3.5:4b`, digest
   `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
   This is a proposal based on an existing artifact, not proof of adequacy. The
   previous QA prompt is not a claim extractor. Candidate settings are
   temperature 0, seed 2026111411, CPU-only four threads and context 16,384.
   An output allowance of 2,048 instead of the original reader's 512 tokens is
   an explicit new configuration. Before use, freeze tokenizer, model-file
   identity, full prompt/schema hashes, parser/sectioning/chunking code, runtime
   version and resource authorization. No execution is authorized here.
5. The proposed prompt enumerates only assertions explicitly supported by supplied
   spans; splits independent propositions; preserves entity, period, unit,
   modality and negation; and emits evidence-linked tuples plus
   `complete/overflow/unsupported` status. It returns unknown rather than filling
   from memory. Chunk deterministically on paragraph/table boundaries, targeting
   at most 2,000 input tokens with 200-token textual overlap. Do not sever table
   headers/footnotes. Deduplicate by source offsets and normalized tuple. A
   too-large table, truncation or invalid JSON is unresolved coverage, not an
   empty list. Allow at most two deterministic half-chunk retry levels;
   exhaustion means unavailable. Fix this bounded policy before scored labels.
6. Original registered ChronoBERT selection still needs its exact pre-filing
   eligible artifact/vintage mapping. Do not silently use today's checkpoint.
   Modern Qwen weights also create retrospective pretraining-contamination
   limitations; frozen weights alone do not establish point-in-time knowledge.
   Report source-grounded retrospective measurement separately from historical
   tradability.

### Measurement requirements come first

Registered synthetic prerequisites remain precision >= 0.90, recall >= 0.80 and
prior-knowledge hallucination < 2%. Failure means not testable, not permission
to weaken them.

The proposed additional human audit requires source-supported claim precision
>= 0.90 and exhaustive-in-scope claim recall >= 0.80 on untouched audit
companies/pairs; report change classification and alignment separately.
Research recommends that corresponding one-sided 95% cluster-aware lower bounds
reach those targets before promoting the extractor. These are **proposed**
real-label acceptance criteria, not an approved scientific threshold or a claim
that 60 pairs guarantee sufficient precision. Unsupported-claim rate must also
satisfy the original requirement. Zero observed errors is not a zero upper
confidence bound.

Report micro and pair-macro precision/recall/F1; NEW/REMOVED/numeric/qualitative
confusion and support; entity, unit/scale, period and evidence correctness;
coverage/abstention and failure reasons; and combined numeric/qualitative errors.
Resample whole companies/pairs, not individual claims as independent. Rare
classes without enough labels mean insufficient evidence, not success.
A block-scoped audit cannot certify whole-filing recall.

Why this is necessary: [REAL2](../results/reader_real2_combined.json) is financial
QA, not paired-claim extraction. Its 30-question report condition was 11 correct
and 19 wrong. The [REAL3 review](../results/reader_real3_review.json) records an
early memory stop, not a completed format-superiority result: ten completed
pairs, all 30 candidate IDs exposed, owned RSS over the 10 GiB ceiling and no
resume. Neither establishes these extraction requirements. Do not call
unattempted cases scored errors or recycle exposed IDs as fresh test data.

### Signal, baseline and incremental estimand

Proposed unweighted claim-change score:

```text
C = (n_new + n_removed + n_modified_union)
    / (n_unchanged + n_new + n_removed + n_modified_union)
```

The denominator is the union of eligible matched relations/unmatched claims,
not summed report lengths. A matched change counts once even when both flags
change. Missing sections, failed extraction, unresolved identity/coverage or a
zero eligible denominator mean **unavailable, not zero**. Do not sweep
result-based salience weights, numeric materiality cutoffs, class weights or
alternative denominators.

Primary scope is the registered risk-factor, MD&A and customer-disclosure
universe, with stable text/table deduplication. Predefine section identification
and missing-section policy. For monthly formation retain the latest genuinely
available filing, registered industry/size/acquisition neutralization and
portfolio filters, weights and costs. Do not fit cohorts retrospectively. For
event-time neutralization, fit other firms' latest eligible signals strictly
before the focal time and score the focal firm out of fit; do not invent a
support default.

Evaluate the registered H1 output unchanged if it becomes evaluable. Separately
preregister this incremental contrast on an identical valid company/calendar
sample, keeping preparation and costs fixed:

```text
R_claim,t(net) = alpha_incremental + beta * R_cosine,t(net)
                 + gamma' * (FF5 + UMD)_t + error_t
```

Claim and cosine spreads have the same low-minus-high orientation. This is an
economic spanning/intercept test, not standalone claim alpha relabelled as
incremental information, and not a causal test. Report marginal registered alpha
and incremental alpha distinctly. Include cheap structural/numeric-diff and
dated TF-IDF baselines; preserve D3's registered TF-IDF sign/threshold requirement
where required. Matched-sample results are supplementary unless the registration
says otherwise. Publish exclusion/coverage reconciliation so sample reduction
cannot masquerade as incremental value. The minimum economically meaningful
incremental net alpha must be chosen before return evaluation; it is unset.

### Return test, calibration and power: not currently defensible

[Batch E calibration](../results/robust_inference_calibration.json) is
synthetic-geometry evidence, not project-return inference. Adoption required
the upper 95% binomial bound on nominal 5% null rejection to be <= 7.5% for every
fixed data-generating process. The worst upper bounds were:

| Months | Registered NW6 | EWC | NW fixed-b |
|---|---:|---:|---:|
| 17 | 39.06% | 13.40% | 19.08% |
| 18 | 38.00% | 12.51% | 19.55% |
| 28 | 24.91% | 9.65% | 13.09% |

All are `unreliable_at_this_geometry`. For independent identically distributed
returns at T=17, NW rejected 30.5% at nominal 5%. EWC improved matters but was not
a validated cure. The G=7 Ibragimov-Mueller result passed only its specific
synthetic year-group geometry; it cannot be transferred to H1's overlapping
60-session cumulative abnormal returns (CARs) and month clusters. Wild cluster
restricted bootstrap (WCR) did not pass that G=7 calibration either. No rare-tail
calibration establishes the registered 3/3.2 screen here.

This card therefore cannot honestly specify a currently successful confirmatory
return test. Registered NW outputs may be reproduced as registered, with a
warning about invalid test size, but cannot yield a newly validated H1 support
claim. A new inference method/design needs prospective registration and
calibration at the actual factor/overlap/dependence geometry **before** its return
result is inspected. Event co-primary inference needs its own calibration and
timing/identity qualification. Thousands of filings do not create thousands of
independent months.

An optimistic scale calculation, **not a calibrated project minimum detectable
effect (MDE)**: with independent Gaussian returns, known sigma and no estimated
regressors, 80% power for a positive effect using a two-sided 5% screen is
approximately `(1.96 + 0.842) * sigma / sqrt(T)`.

| Months | Approximate effect / monthly residual SD | With 3.2 as a fixed normal screen | Hypothetical 3% monthly SD, 3.2 screen |
|---|---:|---:|---:|
| 17 | 0.680 | 0.980 | 2.94% monthly |
| 18 | 0.660 | 0.953 | 2.86% monthly |
| 28 | 0.530 | 0.764 | 2.29% monthly |

These are not observed project volatilities, an exact noncentral-t/regression
calculation or validation of a 3.2 cutoff. Six factors plus the cosine control,
serial dependence, noisy measurement and multiple-testing restrictions make the
actual incremental design harder. At present no reliable finite-sample project
MDE can be quoted from a size-valid monthly procedure.

| Verdict | Meaning under a future approved design |
|---|---|
| SUPPORTED | Measurement, point-in-time sources and inference are adequate; a prospectively specified incremental economic margin and the literal registered v1-AND-v2/D3/co-primary rules all succeed. Positive standalone alpha is insufficient. |
| UNSUPPORTED | A valid, adequately powered design fails its preregistered economic/directional rule. Claiming no material increment also requires an interval excluding the chosen meaningful effect. |
| INCONCLUSIVE | Intervals are too wide, power/cluster support is inadequate or clock/source availability is unsettled. A p-value above 0.05 is not equivalence. |
| NOT TESTABLE/INVALID | Extraction requirements fail, sources/identity/returns are invalid or inference fails calibration. These are not scientific nulls. |

Falsifiers include source-evidence or entity/period/unit mistakes; changes
explained mostly by formatting/boilerplate; no improvement over the
numeric/structural baseline; no incremental relation after cosine; sign
instability across registered missing-return scenarios; and missing required
TF-IDF robustness. Report all, including failures, without trying different
prompts/weights on the audit set.

The smallest credible alternative is a measurement-only evaluation on
development filing pairs, with no return outcomes. A longer older panel,
including separately authorized 2011-2022 return periods, needs a qualified
source and a new approved design. Neither older-data eligibility nor opening the
28-month holdout is granted here. Opening it does not solve the demonstrated
calibration problem.

## Annotation guide: H1-CLAIM-GUIDE-DRAFT-01

### Sampling and what a consecutive pair means

Target 60 real pairs whose **current** filing is in 2023-01-01 through
2024-06-30; the earlier comparator must already have been public. Use the
registered annual/annual or same-quarter year-earlier comparison. Consecutive
annual 10-Ks qualify; consecutive quarterly filings in calendar order do not
implement the year-earlier 10-Q comparator. Do not substitute mixed forms.

Proposed quota: six predeclared broad industry strata, two forms and five pairs
per cell, for 60 pairs. Within each industry/form cell choose two low-, one
middle- and two high-word-change candidates using prespecified development-only
bins, randomized with frozen seed 20261116. Derive bins and sample only from
availability, industry and text-change metadata, never later returns, endpoints,
model correctness or attractive stories. Unknown dated industry needs an
explicit unresolved stratum/mapping, not today's SIC presented as historical
truth. Publish quota weights and weighted/unweighted audit metrics; this enriched
sample is not a population prevalence estimate.

Use distinct companies for every pair where feasible and no company overlap
across splits. Proposed split: 12 earlier guide-calibration pairs, 18 later
development pairs and 30 latest untouched audit pairs. Solve chronology,
company and quota constraints before annotation. If the eligible universe cannot
meet them, stop for a documented amendment rather than move dates, reuse companies
or borrow holdout filings. Freeze all 60 IDs and splits before model inspection.
Years before 2023 may appear only as known predecessor text; this does not
authorize returns outside existing scope.

### Annotation universe and budget

Preferred gold is exhaustive within the actual scored sections: risk factors,
MD&A, customer disclosures and relevant tables/notes, not just model-found
sentences. If unaffordable, a separately declared **block-scoped measurement
pilot** is acceptable. Select matched blocks without model outputs, preserve
headings/table/footnote context, and claim recall only inside those blocks.
A block pass does not validate whole-filing H1 return measurement.

These estimates are not approvals:

| Scope | Per pair, per annotator | Adjudication per pair | Total for 60 pairs |
|---|---:|---:|---:|
| Full target sections | 4-8 hours | 1-2 hours | 540-1,080 person-hours |
| Bounded blocks | 1-3 hours | 0.5-1 hour | 150-420 person-hours |

Totals assume two annotators and exclude training/administration. Time a few
calibration pairs before committing budget. Preserve overruns and missing
coverage rather than rushing labels. No humans have been recruited, permissions
obtained or hours authorized by this draft.

### Annotator view and segmentation

Show earlier/current eligible text, report/fiscal dates, headings, tables, units,
footnotes and enough nearby context to resolve referents. Pseudonymize issuer
names consistently where meaning survives; log inevitable identity leakage.
Hide returns, company news, future filings, registered score/rank, system
predictions and the other annotator's work. Never search later documents to
decide what an earlier disclosure meant.

First enumerate claims independently on each side, with exact evidence. Split
"revenue rose and costs fell" into two claims; keep condition and negation attached
to their proposition. Resolve pronouns only with supplied context. A comparative
sentence can support separate period facts and an explicit comparison, but do
not double count repeated table/text assertions. A missing current section or
truncated table means UNKNOWN, not REMOVED. REMOVED requires review of the
defined counterpart universe.

### Synthetic label examples

These are invented, not filing excerpts.

| Label | Earlier to current: example 1 | Earlier to current: example 2 |
|---|---|---|
| NEW | No corresponding assertion to "Distributor Delta supplies 40% of our inputs." | No corresponding assertion to "A licensing agreement expires in 2025." |
| REMOVED | "One factory is subject to a remediation order." disappears from a fully reviewed comparable section. | A named customer's concentration claim disappears after complete comparable coverage; this does not assert that the customer disappeared. |
| MODIFIED_NUMERIC | "FY2022 revenue was $200 million." becomes "$220 million for FY2022" (restatement flag). | "Customer Beta represents 30% of sales." becomes "20%" for the aligned disclosure role; preserve actual periods. |
| MODIFIED_QUALITATIVE | "We may need external financing." becomes "We will require external financing." | "We have not breached the covenant." becomes "We breached the covenant." |
| UNCHANGED | "Debt is $1 billion." becomes "$1,000 million." | "Two facilities operate in Ohio." moves from text to a table. |
| EXCLUDED_BOILERPLATE/FORMAT | Unchanged generic safe-harbor language has different line wrapping. | A new page heading or generic "results may vary" sentence has no company-specific proposition. |
| UNKNOWN/UNMATCHABLE | "Operating margin is 12%." becomes "Margin is 10%" without a basis/scope definition. | Earlier customer concentration is visible, but the current customer table/footnote is missing. |

Numeric and qualitative example: "At least $20 million may be required" becomes
"Exactly $30 million is committed." This is one modified relation with numeric
and modality/status flags. Do not infer beneficial/adverse sentiment merely from
an increase/decrease.

### Edge rules

- **Restatement:** retain the original and correcting assertions with distinct
  availability. Flag the same-period correction; give a reason only if stated.
  Never backfill the corrected figure into the original report's knowledge set.
- **Boilerplate:** unchanged generic language is not NEW because it moved. A
  company-specific changed risk condition within a template remains eligible.
  Preserve the exclusion rationale.
- **Tables/text:** require exact unit, period and scope agreement; footnotes can
  reverse apparent meaning. Count repeated facts once. Totals and components
  are different predicates, not duplicates. Mark derived arithmetic separately;
  it is not an explicit claim unless stated.
- **Forward-looking:** retain horizon and modality. Forecast versus realized
  actual is not an ordinary matched-value substitution. Withdrawal of guidance
  is an explicit qualitative/retraction event only if stated. Disappearance alone
  is REMOVED.
- **Amendments:** separate administrative exhibit/signature changes from
  substantive financial/disclosure changes. Reconcile only amendments already
  available at the focal time. Preserve original H4/H6 definitions; this guide
  does not repair them retroactively.
- **Entity changes, acquisitions, reporting currency and scope:** label
  scope/matching uncertainty. Do not convert incompatible pre/post entities into
  a simple numeric change.

### Two annotators, adjudication and agreement

Both trained annotators independently enumerate, align and classify claims,
blind to each other's work. Use the 12 calibration pairs to revise the guide,
preserving versions. Freeze guide and extractor before untouched audit labels.
A third adjudicator resolves disagreement by source evidence after independent
passes. Retain both original labels, rationale and final decision. Unresolvable
cases remain unknown.

For fixed matched units report raw agreement, confusion matrix, class prevalence
and Cohen's kappa; use nominal Krippendorff alpha with missing judgments or more
than two coders. Agreement on automatically matched model units alone is biased.
Report segmentation/span F1 and independent claim-set/matching agreement
separately: ordinary kappa does not solve unitization disagreement. Proposed
target: kappa/alpha >= 0.80 on audit-classification units. Below that, reliability
is not established until prospectively addressed. Undefined agreement from an
absent class or all-one-class sample is not a pass. This is a proposed practical
target, not a universal methodological law. Report cluster-aware uncertainty and
per-class support, not only an aggregate coefficient.

Spreadsheet columns:

```text
pair_id, split, pseudonym, form, earlier/current_accession, accepted_at,
fiscal_period, section/block_id, source_hash, old_claim_id/span/cells,
new_claim_id/span/cells, entity, predicate, normalized_value/unit,
period/scope/modality/polarity, matching_status, primary_change, secondary_flags,
completeness, exclusion_reason, annotator_id, guide_version, confidence, rationale,
adjudicator/final_label, AI_suggestion_seen
```

Freeze source manifest, guide, raw independent labels, adjudication log and final
gold under checksums. Do not fit/tune on the 30 audit companies. Restrict audit
labels until the model/prompt/parser specification is fixed; inspected cases
cannot remain untouched tests. Repeated vintages stay in the trial/history
manifest; engineering entries are not silently erased.

AI pre-labels are allowed only after a saved blind first pass, clearly flagged
as suggestions. Never show them to establish initial gold or substitute model
consensus for human adjudication. Retain original human decisions. Report
AI-human precision, recall, agreement and acceptance/correction rates separately
from human-human agreement. Source-grounded suggestions do not remove
pretraining contamination.

### Methodological grounding and limits

- [FEVER](https://aclanthology.org/N18-1074/) separates supported, refuted and
  not-enough-information labels from evidence retrieval; it does not validate
  these change labels.
- [TAT-QA](https://aclanthology.org/2021.acl-long.254/) and
  [paper sections 2.2-2.4](https://arxiv.org/html/2105.07624v1) motivate preserving
  table/text evidence, scale, derivation and independent verification. Its
  original split is by hybrid context, not proof of company/time independence.
- [FinQA](https://aclanthology.org/2021.emnlp-main.300/) separates answer execution
  from reasoning-program correctness, analogous to value versus evidence/period
  correctness here.
- [Artstein-Poesio](https://aclanthology.org/J08-4004/), pp. 555-596, explains
  agreement-measure and unitization limitations.

These sources motivate the protocol; none supplies empirical gold for H1.
The [source comparison](RESEARCH_PLAN.md#historical-equity-source-comparison-draft)
and [proposed action panel](../results/price_source_test_panel.json) address
separate historical-data needs. No source has been qualified. Exact ChronoBERT
artifacts, extractor/parser/tokenizer pins, a meaningful economic margin, valid
monthly/event inference and human annotation/adjudication resources remain
unresolved. Existing failures, survivorship findings and the July boundary
overlap are unchanged; no profitability, tradability or clean-holdout result has
been established.
