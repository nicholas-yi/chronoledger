# Focused reader

The focused reader answers one narrow question:

> Extract one reporting issuer's metric value, stated unit and reporting year with
> source evidence, or explicitly abstain.

This page is the condensed reference. The run-by-run notebook (frozen plans, commit freezes,
resource receipts, approval history and superseded designs) is preserved unchanged in the
[archived FOCUSED_READER.md](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md).
Links labelled "notes" below point to the matching archived section.

**Current status.** The deterministic source path (guarded parser, exact-offset evidence and
source-proved claim checks) is the current candidate and passes all nine regression cohorts. No
model arm, critic or AI reviewer has been promoted; the AI reviewers and the rules-first pipeline
are advisory only. Real-filing accuracy has not been measured: independent human labels remain
zero, and the [source review runbook](#human-actions-still-required-source-review-runbook) is the
outstanding step. The answer-first model reader remains the application default; prefer the
deterministic path when its explicit input contract applies.

## Terms

| Term | Meaning here |
|---|---|
| Invented / authored cohort | Cases written for this project, with expected labels visible to the authors. Not independent gold. |
| Exposed | Already seen during development. Re-scoring it is a regression check, not a fresh measurement. |
| Fresh / one-shot | Frozen in Git before the cases were opened, then recorded once. Still author-visible unless stated. |
| Review / deferral | The system declines to decide and sends the item to review. Counted against coverage, never as a correct financial verdict or as proof of absence. |
| Advisory | Output may inform a human; it cannot change candidates, source guards, human-review counts or gold. |

## Design

### Components

| Stage | Module | What it does |
|---|---|---|
| Field reading | [`reader_fields.py`](../src/asof/reader_fields.py) | Guarded source parser and the `field-record-v1` scorer. Binds issuer, metric, value, sign, currency, scale, measure and reporting year, plus scope, accounting basis, period kind and revision status when the source states them. Hosts the shared admission guard. |
| Evidence linking | [`linked_reader.py`](../src/asof/linked_reader.py) | `linked-evidence-v1`: source SHA-256 plus exact character offsets for value, metric, entity, unit and reporting year, and for scope, sign convention, footnote and correction spans where applicable. |
| Answer verification | [`verified_reader.py`](../src/asof/verified_reader.py) | Checks a model answer against a unique bound fact inside its cited quote. May fill **only a blank unit**; never rewrites values, years or explicit units. |
| Source-cell selection | [`reader_cells.py`](../src/asof/reader_cells.py) | The model picks a `cell_id` from parser-qualified cells; code derives the answer from that cell's proof. Numbers are never generated. |
| Claim checks | [`claim_verifier.py`](../src/asof/claim_verifier.py) | `source-claim-v2`: compares a claim with a unique exact-offset source fact and returns `supported`, `contradicted` or `review`. |
| Notation | [`financial_notation.py`](../src/asof/financial_notation.py) | `financial-notation-v2`: bounded compact notation (`GBP26m`, `EUR 4.5bn`), spelled cardinals and declared revenue aliases. Used only when the guarded reader finds nothing, never after it refuses. |
| Ingestion normalization | [`text_normalization.py`](../src/asof/text_normalization.py) | Repairs C1 bytes to their cp1252 characters and removes invisible formatting in real filing text, as a declared, counted step. |
| Review pipeline | [`review_pipeline_v2.py`](../src/asof/review_pipeline_v2.py) | REVIEW-PIPELINE-02: frozen rules first; AI-REVIEWER-04 only where rules defer. Advisory. |
| Regression replay | [`reader_regression.py`](../src/asof/reader_regression.py), [`check_reader_regressions.py`](../scripts/check_reader_regressions.py) | Replays the current candidate over nine exposed invented cohorts; exits nonzero on any newly missed case. |
| Private review preparation | [`reader_review.py`](../src/asof/reader_review.py), [`prepare_reader_review.py`](../scripts/prepare_reader_review.py), [`reader_review_context.py`](../src/asof/reader_review_context.py), [`prepare_reader_context_forms.py`](../scripts/prepare_reader_context_forms.py) | Builds the private twelve-window packet and blank reviewer forms, and checks returned forms mechanically. |

The original answer-first model reader is [`focused_reader.py`](../src/asof/focused_reader.py).
Other reader modules still in `src/asof` (stress, reliability, AI reviewers v1/v2 and pipeline v1)
back the regression replay and the review pipeline. The invented challenge corpora and their
scoring now live in [`tests/support`](../tests/support); the HHEM wrapper and the non-adopted
AI-REVIEWER-03 are [archived](ARCHIVE.md).

To decide one claim against one source file with the deterministic rules (no model call):

```powershell
uv run --no-sync asof check-claim source.txt "Contoso reported revenue of 18 USD million for 2017."
```

It prints `supported`, `contradicted` or `review` with the bound source span, after the declared
filing-text normalization.

### How a claim is decided

1. **Normalize** real filing text ([`text_normalization.py`](../src/asof/text_normalization.py)).
   Bidirectional controls and undefined C1 bytes are kept, so the verifier still defers them.
2. **Admission guard.** Dispute, denial, retraction, misstatement/restatement, estimate,
   preliminary/provisional/unaudited/draft and hypothetical-framing vocabulary anywhere in the
   source defers to review. So do clause-local negation or forecast wording, source-wide
   illustrative or quarterly/forecast qualifications, invisible format/control characters,
   non-ASCII digits and non-Latin letters. Claims must be printable ASCII.
3. **Prove a source fact** with the guarded reader (table columns, applicable footnotes,
   correction priority, full metric identity). If the reader refuses (`context_rejected`), the
   claim stays in review; the notation path runs only when the reader finds nothing.
4. **Compare.** Exact match gives `supported`; a qualified same issuer/metric/year fact with a
   different value, currency, scale or measure gives `contradicted`; anything unproved gives
   `review`. Same-currency denominations are compared exactly (18 USD million equals 18,000 USD
   thousand); there is no FX conversion, rounding, fuzzy metric matching or alias substitution
   beyond the declared notation policy.
5. **Advisory fallback** (REVIEW-PIPELINE-02). For items the rules defer, an answered candidate
   counts as supported only if the unchanged AI-REVIEWER-02 value check says `supported` **and** a
   separate disclosure question answers `stated`. Abstentions get the disclosure question only, and
   fixed code (not the model) maps its answer to a verdict.

### Design rules

- **Fail closed.** Unsupported grammar or context goes to review or abstention and counts against
  coverage. Missing proof is not contradiction or successful nondisclosure.
- **Never regenerate source facts.** Values, years, currencies and scales come from bound source
  spans; changing a value, year, unit, entity, role, offset or link path cannot produce an accepted proof.
- **Bounded grammar.** A finite prose/Markdown grammar over at most 8,192 source characters; not
  arbitrary financial entailment, an HTML/layout parser or XBRL conformance.
- **Shared rules, not independent judgment.** Proof construction and validation use the same
  deterministic rules; agreement between them is not semantic adjudication.
- **Separate states.** `unknown`, `not_applicable` and `unanswered` are distinct; a dash/nil is
  never coerced to zero. Issuer and metric are supplied queries, so binding is tested, not discovery.
- **One-attempt model runs.** Every model run was frozen in Git before inference and allowed one
  attempt: cached local `qwen3.5:4b`, one CPU, no GPU/cloud/downloads, 6-GiB owned-process cap,
  20-minute wall cap, 90-second call cap (the real-report runs differed; see
  [below](#real-reports-tat-qa--finqa)). Stopped runs are kept, not retried.

### Rejected alternatives

| Alternative | Why rejected | Evidence |
|---|---|---|
| Critic/revision loop | v1 truncated with no usable critique; v2 corrected zero outcomes and regressed one | [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-v2-result-completed-critic-not-beneficial) |
| General entailment model as a gate | Raw HHEM approved seven false claims at threshold 0.5 | [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#hhem-result-1724-at-the-predeclared-threshold) |
| Blind-extraction reviewer (AI-REVIEWER-03) | 17/24, below the unchanged control's 20/24 | [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#fresh-ai-review-comparison-on-24-separately-authored-probes) |
| "Cited line must contain value and currency" rule | Tuned to one miss; would also downgrade two correct table verdicts | [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#decomposed-ai-reviewer-ai-reviewer-02) |
| Unicode normalization of look-alikes; non-ASCII digits as numbers | Hides evidence; ambiguous provenance | [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#guards-added-a2e57c4) |
| Blocking bare forecast words on every path | Breaks a deliberate control ("Its customer may forecast lower costs.") | same |
| `$`/`£` as one currency; net sales as revenue; open-ended spelled numbers | Ambiguous. "Turnover" and "top line" as revenue are declared policy choices, not universal truths | [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#notation-policy-financial-notation-v1) |
| Strict answer formats on real reports | Did not carry over to real reports; answer-first remains the reader | [archived plan](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/RESEARCH_PLAN.md#toward-a-stricter-answer-format) |

## Results

One row per experiment or round, in run order. Scores are copied from the receipts; the scoring
contract changed between some rows (single-quote, linked, `field-record-v1`, claim decisions), so
scores in different rows are not like-for-like. "In main tree" means the code is part of the current
design (its challenge corpus may live in `tests/support`); it does not mean production promotion.

### Real reports (TAT-QA / FinQA)

Local Qwen 3.5 4B on CPU. Questions were drawn at random, and questions, prompt and scoring were
committed before any answer. Format controls used newly written invented questions: 21 answerable
and 3 unanswerable each. Detail: [archived plan](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/RESEARCH_PLAN.md#what-has-been-run).

REAL2 by question type (report supplied): 7 of 10 single-value lookups, 4 of 15 calculations and
none of the 4 questions needing several values; the single counting question was wrong. It first
stopped after 10 question pairs when memory passed a 6 GiB limit; the limit was raised to 10 GiB
with nothing else changed and only the unfinished questions were run. The TAT-QA paper's
human-expert 84.1% exact match is on its own test set and is not a matched comparison.

| Experiment | Headline | Status | Evidence |
|---|---|---|---|
| Rule baseline | 30 TAT-QA: 5 right, 4 wrong, 21 declined; 10 FinQA: all declined | Reference only | [receipt](../results/benchmark_diagnostic_status.json), [follow-up](../results/benchmark_followup_status.json) |
| First model run | 10 TAT-QA: all 8 finished requests declined; stopped on a timeout | Diagnosed as deliberate refusals | [receipt](../results/reader_diagnostic_status.json), [diagnosis](../results/reader_pc1_diagnosis.json) |
| Positive control | 12 invented: 9 of 10 answerable right, both unanswerable declined (old prompt: 1 of 10) | Answer-first prompt adopted | [receipt](../results/reader_pc1_status.json) |
| REAL1 | 30 TAT-QA: stopped by an over-sensitive CPU safeguard before any answer | No result | [receipt](../results/reader_real1_status.json) |
| REAL2 | 30 TAT-QA: **11/30** exact with the report (36.7%, 95% range 21.9-54.5%; F1 42.6%; units 73.3%); 0/30 without | Reference result for the answer-first reader | [combined](../results/reader_real2_combined.json), [as stopped](../results/reader_real2_status.json), [completion](../results/reader_real2_completion_status.json) |
| REAL2 error review | 19 misses: 6 wrong numbers, 4 joined values, 4 operator/denominator conventions, 2 wrong units, 3 other | AI-assisted, post hoc; no score changed | [review](../results/reader_error_audit.json) |
| Contract format | 0 of 21 answerable (outputs broke the format); 1 of 3 unanswerable declined | Not adopted | [review](../results/reader_contract_review.json) |
| Modes format | 18 of 21; 0 of 3 | Not adopted | [review](../results/reader_modes_review.json) |
| Presence format | 19 of 21; 2 of 3 | Not adopted | [review](../results/reader_presence_review.json) |
| Roles format | 19 of 21; 3 of 3 | Not adopted | [review](../results/reader_roles_review.json) |
| Columns format | 18 of 21; 2 of 3 | Not adopted | [review](../results/reader_columns_review.json) |
| REAL3 | Stopped early at a memory limit. On ten completed pairs, strict format 1 exactly right vs 6 for the simple prompt; five of its nine misses were source-cell or span selection | Format line stopped | [diagnosis](../results/reader_real3_diagnosis.json), [review](../results/reader_real3_review.json) |

### Focused reader, invented cohorts

| Experiment | Headline | Status | Evidence |
|---|---|---|---|
| Critic v1 (CL-FOCUS-LAAJ-01) | Stopped: 2 of at most 36 calls; first critic hit its 256-token cap; 0 of 6 evaluation cases reached | Not promoted | [receipt](../results/focused_reader.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-local-result-stopped-no-improvement-established) |
| Critic v2 (compact JSON) | Judge-assisted **4/6** vs single pass 5/6 and parser 5/6; zero corrections, one regression; about 2.55x latency | Not promoted | [receipt](../results/focused_reader_v2.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-v2-result-completed-critic-not-beneficial) |
| Grammar robustness | 24 cases: binding parser **24/24**, LLM + verification 24/24, raw LLM 21/24, old parser 21/24 | Verification in main tree; no LLM increment | [receipt](../results/verified_reader.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-verifier-only-result-and-private-review-preparation) |
| Harder formats | 288 deterministic cases: binding parser 144/144 controls, 36/144 stress. 12 model stress cases: single pass 5/12 full contract (12/12 tuple only), verified 3/12 | Exposed format limits | [receipt](../results/reader_stress.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-harder-audit-the-old-perfect-score-was-format-specific) |
| Linked challenge | Linked parser **24/24**; same LLM output + evidence completion 23/24 (old scorer on those answers: 15/24) | In main tree | [receipt](../results/linked_reader.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-linked-challenge-2324-completed-2424-deterministic-control) |
| Field records | Guarded parser **24/24**; parser-first + model fallback 23/24; old linked parser 21/24; old completion 20/24; 156/156 field checks on positives | Guarded parser in main tree | [receipt](../results/reader_fields.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-field-comparison-complete-positive-records-fallback-still-adds-a-failure) |
| Reliability | Same 12 inputs: schema conformance 10/12 free vs 12/12 constrained; best model arm 11/12; source-gated **12/12** (24/24 on the full cohort) | No model arm promoted | [receipt](../results/reader_reliability.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-reliability-audit-valid-shapes-improve-wrong-year-reasoning-remains) |
| Cells + context coverage | Deterministic **192/192**; model comparison stopped on its first call (timeout after 90.016 s) | No model result | [receipt](../results/reader_cell_selection.json), [accounting](../results/reader_cell_selection_accounting.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-cell-audit-coverage-completed-model-comparison-stopped-on-first-timeout) |
| Compact cells + AI-REVIEWER-01 | Cell selection 12/12 (source-only control also 12/12); reviewer **5/12**, four invalid outputs | Cells in main tree; reviewer not promoted | [receipt](../results/reader_ai_review.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-ai-reviewer-and-cell-run-cells-pass-judge-does-not-earn-trust) |
| Regression consolidation | All nine current cohorts pass (12/12, 24/24, 24/24, 288/288, 24/24, 24/24, 24/24, 192/192, 12/12) | In main tree | [receipt](../results/hhem_benchmark.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#current-source-candidate-complete-declared-regression-matrix) |
| HHEM-2.1-Open | **17/24** at fixed threshold 0.5; false support 7/12 unsupported claims; false rejection zero | Not promoted; not a gate | [receipt](../results/hhem_benchmark.json), [assets](../results/hhem_assets.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#hhem-result-1724-at-the-predeclared-threshold) |
| Source-rule claims | **24/24** vs raw HHEM 17/24 on the same fresh inputs; six format controls deferred, so 24/30 (80%) coverage | In main tree | [receipt](../results/hhem_structured.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-source-rule-comparison-2424-resolved-claims-six-visible-deferrals) |
| Claim assurance (`source-claim-v2`) | 37/37 policy controls (28 resolved verdicts, nine expected reviews); 40 property examples pass; original set **26/30** resolved (86.7% coverage) | In main tree | [receipt](../results/claim_assurance.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-broader-assurance-real-decision-defects-fixed-coverage-rises-to2630) |
| Notation (`financial-notation-v1`) | Fresh challenge 12/24 → **24/24**; grid 540/780 → 780/780; original 30/30 (exposed); separately authored adversarial one-shot **71/72**, one false support fixed post hoc | In main tree | [baseline](../results/notation_baseline.json), [adversarial](../results/notation_adversarial.json), [final](../results/notation_final.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#notation-protocol-and-results) |
| AI-REVIEWER-02 | First attempt stopped with zero calls; rerun **17/18** (fresh 6/6, exposed 11/12; v1 on the same 12: 5/12), one false support | Advisory, not promoted | [stopped](../results/reader_ai_review_v2.json), [rerun](../results/reader_ai_review_v2b.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#decomposed-ai-reviewer-ai-reviewer-02) |
| Integrity guards | 221-case challenge: 83/221 with 134 false supports → **221/221** with 0 | In main tree | [baseline](../results/integrity_baseline.json), [final](../results/integrity_final.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#guards-added-a2e57c4) |
| Adversarial round 2 (`financial-notation-v2`) | **96/96** one-shot; zero false supports, false contradictions or missed resolutions | In main tree | [receipt](../results/notation_adversarial_r2.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#second-adversarial-round-financial-notation-v2) |
| AI review round 3 (24 fresh probes) | AI-REVIEWER-03 17/24; AI-REVIEWER-02 control **20/24**; rules 10/10 decided, 14 deferred | AI-REVIEWER-03 not adopted | [v3](../results/reader_ai_review_v3.json), [control](../results/reader_ai_review_v3_control.json), [rules](../results/reader_ai_review_v3_rules.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#fresh-ai-review-comparison-on-24-separately-authored-probes) |
| REVIEW-PIPELINE-01 (round 4) | **23/24**, one conflict false support; AI alone 20/24; rules 9/9 decided | Not promoted | [AI](../results/reader_ai_review_v4.json), [pipeline](../results/review_pipeline_v4.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#declared-rules-first-pipeline-on-a-further-fresh-round) |
| REVIEW-PIPELINE-02 (round 5 stress) | **30/30**, zero false supports; unchanged value check alone 10/16 with 6 false supports | In main tree; advisory, not promoted | [combined](../results/review_pipeline_v5_combined.json), [half A](../results/review_pipeline_v5a.json), [half B](../results/review_pipeline_v5b.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-rules-first-pipeline-v2-agreement-closes-conflict-and-forecast-false-supports) |
| Guard coverage, real 10-K MD&A | Raw 8.9% sentence deferral → **2.1% / 4.7% / 9.8%** (sentence / ±1 / ±3 neighbours) on fresh issuers after normalization and two stem fixes | Normalization in main tree; deferral, not accuracy | [round 1](../results/guard_coverage_real.json), [round 2](../results/guard_coverage_real_v2.json), [round 3](../results/guard_coverage_real_v3.json) · [notes](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/docs/FOCUSED_READER.md#observed-guard-coverage-cost-on-real-10-k-mda-text-aggregate-only) |

### Notes on selected rows

- **Field records.** Of the 156 field checks, 112 had known-valued targets and 44 were unknown or
  not applicable. Known-context denominators were tiny (scope 2/2, basis 2/2, period kind 3/3,
  revision status 1/1); the 192-case context cohort later supplied 24/24 known positives for each of
  those four dimensions, from author-visible templates.
- **Harder formats.** The raw model's ten stress answers matched the authored tuples, but seven
  failed the single-quote evidence contract (table headers, footnotes, parenthesized negatives,
  pronoun or fiscal-year context). Those are citation failures, not seven wrong financial tuples.
- **Reliability.** The constrained response obeyed the schema but still picked the wrong-year
  (2017) fact for U02-0: **schema validity is not semantic correctness.** Both completion gains
  were the same per-share case, not a unit-word-order repair.
- **AI-REVIEWER-01.** Three valid false rejections were justified abstentions; the four invalid
  outputs said `supported` while listing error codes. An always-reject reference would match 6 of
  12, more than its 5.
- **HHEM.** Wrong claims got high scores (up to 0.8859, for an accepted superseded original);
  a raw score is not a calibrated correctness probability. HHEM was not tested on abstention.
- **Source rules vs HHEM.** The source-only control (same decisions without model probabilities)
  also scored 24/24, so **there is no demonstrated incremental HHEM benefit.**
- **Notation adversarial set.** Written by a separate AI agent instance from the written policy
  only (95% Wilson interval 0.925-0.998). ADV-71 exposed a real sibling-sentence defect, fixed in
  `b97dcf6`; the 71/72 receipt stays authoritative and the later 72/72 is an exposed regression.
- **REVIEW-PIPELINE-01.** The rules corrected three of the AI's four errors; the remaining miss,
  RV4-15, was a source with two equally authoritative amounts that the AI accepted.
- **REVIEW-PIPELINE-02.** The agreement step caught all six value-check false supports: three
  conflicts and three forecast-type amounts. Round 5 deliberately over-represents known
  weaknesses, so it is a stress test, not a representative error rate (95% Wilson 0.886-1.000).
- **Guard coverage.** Round 1 showed the integrity guard firing on benign encoding artifacts
  (zero-width spaces and mis-decoded Windows-1252 punctuation), which led to the declared
  normalization. Stems `alleg*` ("Allegro") and `imagin*` ("imaging") were narrowed. Remaining
  deferrals come from intended vocabulary such as "estimated", "restated", "unaudited" and
  "provisional". The pre-existing admission checks almost never fire on real MD&A (0-0.2%).

| Guard coverage round (freeze) | Sample | Integrity deferral | Shared-guard deferral: sentence / ±1 / ±3 |
|---|---|---|---|
| 1 raw text (`c8475f5`) | issuers 1-150, 1,814 sentences | 5.95% | 8.9% (7.7-10.3) / 14.7% / 24.3% |
| 2 normalized (`45910e5`) | same 150 (exposed) | 0% | 3.3% / 6.2% / 12.0% |
| 2 normalized | fresh issuers 151-300, 2,167 sentences | 0% | 2.8% (2.2-3.6) / 6.1% / 11.8% |
| 3 normalized, `imagin*` narrowed (`a0ec24b`) | fresh issuers 301-450, 1,741 sentences | 0% | **2.1% (1.5-2.9)** / 4.7% / 9.8% |

The coverage measurement read only cached development-window (2012-2018) 10-K primary documents,
excluded all 12 review filings and their 12 issuers, and stored aggregate counts only; no passage
was stored or shown. Its runner is archived:
[`measure_guard_coverage_real.py`](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/measure_guard_coverage_real.py).

## What is established and what is not

**Established, within the stated scope:**

- In every paired invented comparison except the harder-format audit, the deterministic source
  path matched or beat the model-assisted arm (grammar 24/24 vs 24/24, linked 24/24 vs 23/24,
  fields 24/24 vs 23/24, reliability 12/12 vs 11/12, cells 12/12 vs 12/12). The exception, under
  the old single-quote contract (stress cases: raw single pass 5/12, binding parser 3/12), led to
  the linked-evidence contract. **No incremental LLM advantage is established.**
- The current candidate passes all nine regression cohorts with zero wrong admissions.
- On two fresh 24-probe rounds the deterministic rules made 19/19 correct decisions with zero
  errors, but decided only 40% of probes.
- A general entailment model (raw HHEM) approves wrong financial associations: year column, entity,
  definition, scope, denominator, footnote and correction errors. It is not used as a gate.
- On fresh real 10-K MD&A revenue sentences, the conservative guards defer 2.1% of single
  sentences, 4.7% with one neighbour each side and 9.8% with three.
- With the report supplied, the answer-first model got 11/30 TAT-QA questions exactly right and
  declined all 30 without it.

**Not established:**

- **Independent accuracy.** Invented and author-visible cohorts are not independent gold. Cohorts
  overlap and are development-exposed; never pool them into one sample size.
- **AI review as gold.** AI review is advisory, never human gold. Probes for later rounds were
  written by separate AI agent instances, not independent humans; one shared small local model is
  not model diversity or authenticated independence. A one-human-plus-AI workflow must be labelled
  AI-assisted, not two independent human passes.
- **Real-filing accuracy.** Human labels remain zero. A deferral rate is not an error rate.
- **Generalization.** Unlisted wording, arbitrary financial formats, real-filing notation
  coverage and AI conflict detection beyond one stress round.
- **Economic value.** None of this measures disclosure change over time, historical usability or
  returns.

## Human actions still required: source review runbook

The [public preparation receipt](../results/reader_review_packet.json) identifies the existing
private twelve-window packet (issuer-disjoint excerpts from an already exposed 2012-2018
development cohort) and its pin:
`3b2cf99bbb7b4e163f0b420a6bdd1f42a13b63b2d24b209ef61cb1b25fefb2a9`.
The packet and blank forms already exist under ignored `data/`; nothing below requires model or
SEC credentials, network access, a push or opening a holdout.

1. **Assign two independent reviewers** with authorized access. Each does a blind first pass
   without AI answers or the other reviewer's labels and uses one consistent reviewer ID. Anyone
   who has seen model suggestions must not declare a blind pass; use another reviewer or disclose
   the exposure and keep the pass exploratory. This repository cannot contact people or
   authenticate identity.
2. **Distribute the base forms.** Check the SHA-256 of `data/reader_review_v1/packet.json` against
   the pin above, then give each reviewer the packet and one of `reviewer_a.csv` /
   `reviewer_b.csv` from the same folder. Status per item: supported, unsupported within the
   excerpt, or `insufficient_context`. Supported tuples need finite values, the requested year and
   verbatim evidence. Do not copy excerpts or identities into Git. The packet was created once by
   `python scripts/prepare_reader_review.py --execute`; do not rerun it as part of review.
3. **Distribute the context forms.** Give each reviewer the matching
   `data/reader_review_context_v1/context_reviewer_a.csv` or `context_reviewer_b.csv` (72 blank
   rows each: six dimensions x twelve items; both files had SHA-256
   `c7bbbeeb5d6187be4e80b49063bdbd40b1ab1a9eca20f668e872bd7108d6f38d` when generated). If they are
   missing, `python scripts/prepare_reader_context_forms.py --prepare-blank` recreates them from
   the public receipt only, without reading excerpts; it refuses to overwrite.
4. **Annotate context.** For every item, label issuer binding, metric binding, scope, accounting
   basis, period kind and revision status as `supported`, `unknown` or `not_applicable`. Supported
   rows need zero-based character offsets `[evidence_start, evidence_end)` into the exact packet
   excerpt plus a rationale. Use `unknown` when the context is outside the window; do not browse the
   full filing or use background knowledge. Unknown and not-applicable rows have no value or span
   but still need a rationale. Do not invent fiscal endpoints.
5. **Return and check.** Return all four forms privately. Check base forms with
   `asof.reader_review.check_reviews` and context forms with
   `asof.reader_review_context.check_context_reviews` (matching reviewer identities, packet pins,
   full item/dimension coverage, blind declarations, offset bounds, state/value consistency; lists
   disagreements). These are mechanical checks, not semantic gold.
6. **Adjudicate.** Keep both original passes; record an adjudicator and a source-linked rationale
   for each disagreement. Equal labels or valid offsets alone do not certify entailment.
   Unresolved items stay out of accepted gold and remain visible in coverage counts.
7. **Approve any expansion separately.** If excerpts lack necessary context, approve a bounded
   eligible development-context expansion before any new reads. Source holds and holdouts stay
   closed. Twelve selected windows cannot establish representative accuracy; a real-world claim or
   production promotion needs a separate independent evaluation design.

## Limitations

- **Grammar coverage.** Only the declared prose/Markdown constructions, table/footnote bindings and
  notation policy are supported. Anything else defers. Real-text coverage was measured only for
  revenue sentences in development-window US 10-K MD&A, with window sizes as proxies.
- **Finite admission patterns.** The guards do not understand every negation, disclaimer or
  forecast paraphrase, and conservative source-wide holds reduce coverage in mixed documents.
- **Notation scope.** `$`, `£`, bare dollars/pounds and `M`/`MM`/`K` are refused by design, so the
  notation path neither adds nor removes US MD&A coverage. Turnover synonyms beyond the declared
  aliases stay unresolved.
- **Exact arithmetic only.** Equivalence is exact and same-currency; there is no FX conversion.
- **Small, authored samples.** Field-context known targets came from four template families;
  AI-reviewer rounds used small sets of author-written probes, so intervals are wide (for example
  0.80-0.99 for the 23/24 pipeline).
- **Costs are single runs.** Latency and memory figures come from one run each on a shared
  worker; they are not robust estimates. Model calls took tens of seconds each, while parser
  computation over a whole challenge took fractions of a second.
- **Public benchmark exposure.** The model may have seen TAT-QA during training; declining without
  the report does not rule that out.
- **Software checks.** The full suite runs in CI on Ubuntu and Windows for every push. Earlier
  runs recorded intermittent Windows Job readiness and SEC request-rate timing failures that later
  passed; no permanent environmental cure is claimed.

## Reproducing

```powershell
python scripts/check_reader_regressions.py
python -m pytest -q tests/test_reader_fields.py tests/test_linked_reader.py tests/test_verified_reader.py tests/test_claim_verifier.py tests/test_financial_notation.py tests/test_text_normalization.py tests/test_review_pipeline_v2.py tests/test_reader_regression.py tests/test_reader_review.py tests/test_reader_review_context.py
```

The regression check reads only the invented fixtures in [`tests/fixtures`](../tests/fixtures),
makes no model calls and exits nonzero on any newly missed case. Model runs need the cached local
model and their archived runners, for example
[`run_focused_reader.py`](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/run_focused_reader.py),
[`run_hhem_benchmark.py`](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/run_hhem_benchmark.py),
[`validate_claim_assurance.py`](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/scripts/validate_claim_assurance.py)
and [`integrity_challenge.py`](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/src/asof/integrity_challenge.py),
or the archived [`hhem_verifier.py`](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/src/asof/hhem_verifier.py)
and [`reader_ai_review_v3.py`](https://github.com/nicholas-yi/chronoledger/blob/archive-2026-11/src/asof/reader_ai_review_v3.py).
Each receipt records the commit it was frozen at; check out that commit to rerun it (see
[ARCHIVE](ARCHIVE.md)). Each one-shot run keeps an exclusive attempt marker, so rerunning one is a
new, separately frozen experiment, not a retry.
