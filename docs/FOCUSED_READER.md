# Active focus: one evidence-linked reader, not nine trading models

**2026-11-19.** Broader stochastic-process/network/pricing/portfolio modules are
parked research references. Their code, frozen runs, nulls and failures are preserved.
The active research question is now:

> Extract one reporting issuer's metric value, stated unit and reporting year with
> a verbatim supporting sentence, or explicitly abstain.

The [implementation](../src/asof/focused_reader.py) reuses the existing evidence
normalization helper. There is no new framework, graph engine or training stack.

## What improvement means here

1. A narrow parser supplies an auditable cheap baseline.
2. One fixed answer-first local model supplies a single-pass baseline.
3. A critic sees the same source, question and actual draft. It checks entity,
   metric definition, period, number/unit, ambiguity and supporting quote.
4. On evaluation cases, a nonaccept verdict permits **one** revision. The critic
   can be wrong: the revision must recheck the original source.
5. A revision failing necessary deterministic checks is rejected; a valid initial
   answer is retained. If neither output passes, return a documented abstention.

The selection policy never consults expected/gold answers. A semantically wrong
revision that passes token/quote checks can therefore regress a correct initial
answer. The benchmark must count that regression, not secretly roll it back with gold.
Malformed model JSON is an invalid response, not a correct abstention.

Necessary checks are verbatim evidence, issuer token, requested year, stated unit
and numeric occurrence. An industry metric can pass all five when its sentence
mentions the issuer. **Grounding is not semantic entailment, independent gold or truth.**
The deterministic accounting oracle remains a separate optional diagnostic; this
single-value task does not invent an accounting equation to certify every answer.

## A bounded across-version improvement mechanism

Only mistakes verified against authored **development** fixture answers enter the
private error bank. Model approval alone cannot produce a labelled example.

A frozen adaptation rule maps observed error categories to six fixed critic reminders:
period binding, signs, issuer-versus-industry, definition mismatch, percent/currency
units and unresolved conflicts. Before any evaluation model call, the runner writes
the selected reminders and candidate digest to an exclusive receipt.
The initial evaluation generator remains identical across the two model arms.
Only the critic/revision can see these development reminders.

No errors means no lessons; that is not described as learned improvement.
There is no prompt search, repeated evaluation, automatic code editing, DPO,
reinforcement learning or model-weight update. The error bank/proposal is a
reviewable input to a future version, not an unsupervised reward-maximizing loop.

The promotion gate reports paired corrections/regressions and **always refuses
production promotion from this invented-case harness**, including if a caller sets
an `independent_audit` boolean. That flag cannot authenticate real independent evidence.
Any future external audit/promotion mechanism needs its own genuine evidence and
approval; it is not implemented by relabelling these fixtures.

## Frozen local-model comparison: CL-FOCUS-LAAJ-01

The user explicitly approved one local run: twelve invented cases, at most 36 calls,
20 minutes, one CPU, no GPU/cloud/downloads, 6 GiB owned-process memory cap, no retry.
The [plan](../results/focused_reader_plan.json), prompts, fixtures, runner, package
pins and this contract must be committed before inference.

Inputs are only the fixed [invented fixture](../tests/fixtures/focused_reader.json),
not filing caches, public financial benchmarks, reserved data, prices or outcomes.
Every issuer/value is invented. This is a task-level diagnostic, not validation of
financial extraction in the wild or a historical trading model.

### Allocation and split

- Six development cases: generate once, critique the actual draft, and critique
  one deliberately wrong authored probe per case: **18 calls**.
- Freeze candidate development reminders/digest before evaluation model calls.
- Six evaluation cases: generate once, critique once, optionally revise once:
  **at most 18 more calls**.
- No development revisions; its judge-assisted summary remains explicitly not
  attempted. Development is for error collection and critic calibration only.
- Single-pass and judge-assisted evaluation arms share the same initial generation,
  isolating the downstream critic intervention. They are not independent samples.
- Judge-assisted per-case latency/tokens include that shared initial generation;
  summing arm costs would double-count it. Total actual calls are recorded separately.

The parser grammar handles only "`ISSUER reported METRIC of VALUE UNIT for YEAR.`"
and rejects unresolved conflicts. One evaluation wording intentionally lies outside
that grammar; it tests baseline coverage, not an industry-wide parser performance claim.
Other cases cover periods, signed values, issuer/industry confusion, currencies,
definition mismatch, missing facts and contradictory evidence.

Expected tuples are not sent to either model stage. Critic calibration compares
accept/reject decisions against known authored fixture correctness, including wrong
probes; it is not judge-to-judge agreement. Invalid critiques count explicitly.

The whole fixture was authored and is visible in Git. "Evaluation" means held
away from the frozen development-reminder selection rule/model requests, **not an
independently authored secret test set or human gold**. Six evaluation cases cannot
establish high accuracy, statistical superiority, generalization or economic value.

### Local runtime and stops

Only the already cached `qwen3.5:4b` digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`
is allowed. Verify the previously pinned executable/native backend before launch.
The runner refuses an occupied `127.0.0.1:11435` port and never alters the existing
shared `11434` server. There are no model pulls or cloud endpoints.

The owned Python worker is gated until attached to the packaged
[`WorkerJob`](../src/asof/runtime.py), then launches its own server. A new optional
process-count limit allows up to four owned members (default remains one).
Descendants inherit one CPU; sampled Job membership/affinity is checked.
Numerical thread counts and model thread count are one, `num_gpu=0`, and the
owned server's `/api/ps` must report zero VRAM after every completed request.
Here completion means a response accepted as complete by the runner; a truncated
response stops before that post-call model-state check.

Owned-server environment disables cloud and declares native prompt cache zero,
with the previously verified shipped support. This is not a new experiment proving
which memory component that setting controls. Context is 2,048 tokens; generation/
revision output cap 384, critic cap 256; temperature zero and seed 202611190611.
No complex output grammar is imposed; JSON schema validation happens after generation.

One request at a time, no automatic generation retries, per-call timeout 90 seconds,
startup cap 60 seconds. Input-fit/truncation checks fail closed. The controller stops
at 1,180 seconds to reserve cleanup/report time inside 1,200 seconds.
The Job private-commit limit reserves 128 MiB of the 6-GiB budget for the controller;
combined observed working set is sampled separately. Commit and RSS differ.
Neither is an OS filesystem/network sandbox. Unexpected membership/resource/
transport/truncation errors stop and preserve the attempt.

Raw responses, server logs, error bank, candidate snapshot and per-process resource
receipts stay in ignored `data/focused_reader_v1`. An exclusive attempt marker blocks
rerun. Every send is recorded before transport; interrupted calls remain attempts.
Only invented-case answers and aggregate comparisons go in the public report.
The controller closes its Job and terminates only explicitly owned process handles.

## Evaluation and honest release

Report all-planned correctness, answered coverage, wrong/unsupported answers, malformed/
unattempted cases, critic false acceptance/rejection, corrected/regressed answers,
latency, tokens and actual resource use. Abstention is not an answered correct value;
correct rejection of an unanswerable item is reported distinctly.

No judge "pass" is used as the extraction-accuracy denominator. No successful
synthetic comparison establishes real economic labels, market novelty or alpha.
Without an independent labelled audit, the default answer-first reader remains
unchanged and no production challenger is promoted.

Relevant precedents and caveats:
[LLM-as-a-judge biases](https://arxiv.org/abs/2306.05685),
[Self-Refine](https://arxiv.org/abs/2303.17651),
[limits of intrinsic self-correction](https://arxiv.org/abs/2310.01798),
[self-rewarding weight training](https://arxiv.org/abs/2401.10020).
These support testing a bounded workflow, not assuming improvement.

No real-data study, H4/H6 hold release, source repair, return ledger row, new
model download, API expenditure, weight training, external publication or push.

Pre-inference software verification: **668 tests passed in 51.83 s**, with two
existing synthetic rank-deficiency warnings; repository Ruff and local documentation
target checks passed. New tests include a semantically wrong industry answer that
passes necessary token checks, wrong-revision rollback without using gold,
development-only lessons, failed-attempt accounting and owned Job telemetry.
No model generation occurred during those checks. This is not the local-model result.

Preflight correction, before inference: the initial freeze `8686abb` used an HTTP
request to test whether port 11435 was occupied. That GET raised ConnectTimeout
before the attempt marker, owned server or model generation. Both marker/report
were confirmed absent, and exclusive OS binding confirmed the port unoccupied.
The corrected preflight uses exclusive OS binding; startup health polling tolerates
connection errors/timeouts within its existing 60-second readiness cap.
No generation retry, budget, prompt, fixture, seed or evaluation rule changed.
This fix is committed in a new freeze before the single actual model attempt.

## Observed local result: STOPPED, no improvement established

The corrected freeze was `987f956127c23656dd5a521da9a3e7db23b8506a`.
The [actual receipt](../results/focused_reader.json) is a stopped run, not a passed
reader comparison:

| Observation | Actual result |
|---|---|
| Started model calls | 2 of at most 36 |
| First development extractor response | Correct invented value `17`, unit `USD million`, period `2016`, supported quote |
| Extractor cost | 58.422 s wall, 60 generated tokens; includes its first-call/load overhead |
| First critic response | Hit the frozen 256-token limit, `done_reason=length`; no complete accepted critique |
| Critic cost | Additional 84.453 s wall, 256 generated tokens |
| Revisions / completed critic calibration records | 0 / 0 |
| Evaluation cases reached | 0 of 6 |
| Verified error-bank/candidate adaptation phase reached | No |
| Production promotion / weight updates | No / no |
| Total controller wall | 144.562 s |
| Observed combined peak working set | 3,776,741,376 bytes, about 3.52 GiB |
| Resource/source checks | Passed; one inherited CPU and unchanged frozen source during the run |

The incomplete critic output began questioning the correct year/value association,
then reconsidered itself before truncation. This is a qualitative observation about
an unfinished response, **not a scored final false rejection**, a completed
calibration exercise or proof that all judges are unreliable.
No judge opinion became a training label. One correct development answer is not
100% extraction accuracy, and the six unattempted evaluation cases are not a measured
0%-accuracy model. Planned/attempted/invalid counts remain separate in the receipt.

The owned server verified zero VRAM after the first valid call; the second response
stopped at truncation before post-call state inspection. Every request declared
`num_gpu=0` and inherited the CPU-only server environment. The owned Job's four
observed member PIDs exited/are absent; the preexisting shared Ollama PID remained
untouched and port 11435 no longer had a listener. No persistent server was left.

**Decision:** keep the existing answer-first default. This judge configuration did
not earn a default role, and its extra latency produced no usable critique or
observed correction. Do not silently increase tokens, switch models, rerun with
another seed or call this "self-improvement." A future critic design would be a
new version and separately approved experiment; the attempt marker is retained.

The full post-preflight software suite passed **669 tests in 40.18 s**, with two
existing synthetic rank-deficiency warnings; Ruff passed. Those software checks do
not reverse the stopped model result. Historical quant experiments and source holds
are preserved; no real corpus, prices, fundamental outcomes, production ledger,
weight training, model download, cloud inference or push was involved.

## V2: separately authorized compact-critic redo

The user explicitly requested "fix and redo" after seeing the stopped v1 result.
This is a new post-development-failure design, not an automatic resume or a hidden
replacement of the old evidence. V1's raw result/attempt marker remain intact.

The change targets the observed failure mechanism: v1 asked for free-form feedback,
which rambled/reconsidered itself and hit the output cap. V2 uses:

```json
{"verdict":"accept","issues":[]}
```

The `format` field constrains the critic to a two-field JSON object: verdict is one
of `accept/revise/abstain`; at most three issue codes from a fixed nine-code enum.
No generated feedback or reasoning field exists. The critic output cap is **128**,
down from 256, not an increased budget to accommodate rambling.
Pydantic still rejects inconsistent verdict/code combinations, repeats or unsupported
codes. A bounded grammar is not a semantic correctness guarantee.

On revision, code expands the critic codes into fixed source-checking reminders.
That feedback contains no authored expected answer and no free-form model rationale.
The model must re-read the source; the deterministic rollback policy is unchanged.

All twelve fixtures, model/digest, generator/revision prompts, seed, split, development
lesson rule, six wrong probes, 36-call ceiling, 20-minute wall cap, per-call timeout,
one CPU, no GPU/cloud/pulls and 6-GiB resource contract remain the same.
No evaluation outputs were observed in v1, but these still are visible, agent-authored
invented fixtures, not independent gold or a secretly held-out test.

The [v2 plan](../results/focused_reader_v2_plan.json), schema/prompt and tests are
committed before v2 inference. Explicit launch:

```powershell
uv run --no-sync python scripts/run_focused_reader.py --version v2 --execute
```

V2 uses new `data/focused_reader_v2` and `results/focused_reader_v2.json` paths;
default `v1` still refuses its existing attempt. The v1 public result is included in
v2's frozen file hashes so accidental alteration is visible. There is no third
automatic attempt, no promotion of a schema-only success, and no new training.

V2 pre-inference verification: **671 tests passed in 64.51 s**, with two existing
synthetic rank-deficiency warnings; Ruff and documentation/index checks passed.
New tests reject generated free-form feedback, unknown/repeated/excess codes and
inconsistent verdicts, and verify unchanged generator/revision messages and isolated
v1/v2 output selection. No v2 model call occurred during those checks.

## Observed v2 result: completed, critic not beneficial

The [v2 actual receipt](../results/focused_reader_v2.json) records the single run
frozen at `0a3882f431da216e75128bbf966e106eac1aadc6`. All twelve fixtures were
processed in **1,038.781 seconds (17.31 minutes)**, with 33 calls of the maximum 36:
12 initial generations, 18 critiques and 3 evaluation revisions.
All responses ended normally without token truncation. Format/semantic validation
still rejected four critiques and one initial answer; completion is not a QA pass.

### Evaluation, six authored invented cases

| Arm | Correct outcomes / 6 | Answered values | Correct abstentions | Other outcomes |
|---|---:|---:|---:|---|
| Narrow parser | 5 | 3 | 2 | One missed answer outside its grammar |
| Single pass | 5 | 3 | 2 | One invalid response: correct number/quote but missing unit |
| Judge-assisted | 4 | 2 | 2 | Two missed answers; one was a regression from a correct draft |

No wrong numeric answer was emitted in the completed evaluation arms. That is not
100% accuracy: invalid responses and missed supported answers remain failures.
The same initial generations were shared between model arms, not independently
sampled. The critic corrected **zero** outcomes and regressed **one**.

The regression was E04, an invented EUR revenue disclosure. The initial answer
quoted the exact source correctly. The critic requested revision; the revised model
abstained, claiming the sentence was absent even though it was present verbatim.
Abstention passes the necessary output/grounding contract but does not establish
that evidence is actually missing. The selector did not secretly consult gold to
undo the regression.

E01's initial response contained the right authored value and source sentence but
left `unit=""`, so strict parsing rejected it. The critic accepted that raw draft
instead of requesting a unit repair. This is a task-contract failure, not proof the
model failed to locate the number. We did not regrade or normalize it post hoc.

### Development critic calibration, not independent gold

All six initial development outputs matched their authored fixture answers, so the
verified-development error bank was empty. The frozen adaptation rule executed and
saved an empty-reminder candidate **before** evaluation; no lessons or model weights
were learned. This is not evidence of iterative improvement.

| Draft type | Accept | Nonaccept | Invalid critique |
|---|---:|---:|---:|
| Six correct actual development drafts | 3 | 2 (false rejections) | 1 |
| Six deliberately wrong authored probes | 1 (false acceptance) | 2 (correct rejections) | 3 |

"False rejection" here follows the frozen wire contract: `accept` must include a
justified abstention. The two nonaccepts of correct drafts were `abstain` verdicts,
which can echo the original correct abstention rather than contradict its facts.
They still violate the routing contract and request unnecessary revision.
Likewise, two of the three evaluation revisions only regenerated already-correct
abstentions; the third caused the E04 regression.

The four invalid critiques repeated the same `missing` issue code twice. The bounded
JSON grammar solved the token-exhaustion problem but did not enforce every semantic
validator rule. They remain invalid; we did not silently deduplicate/regrade them.
No error-code/schema repair changes the observed E04 semantic regression.

### Cost, resource and decision

- Evaluation single-pass latency: **186.375 s**; judge-assisted latency including its
  shared initial generations: **474.999 s**, about **2.55x**.
- Evaluation output tokens: single pass **350** versus judge-assisted **647**.
  Summing both arms would double-count the shared initial generation.
- Total unique generated tokens across the run: **1,224**.
- Observed combined peak working set: **3,832,442,880 bytes (3.57 GiB)**.
- One-CPU affinity, source immutability and resource checks passed; worker exited 0.
  All four observed owned PIDs were confirmed absent after cleanup, port 11435
  closed, and the original shared Ollama PID remained untouched.
- V1's public result was included in the frozen hashes and remained unchanged.
  Neither its result nor either attempt marker was overwritten.

**Decision: the technical truncation fix worked; the critic still did not earn its
complexity. Keep the existing answer-first default and do not automatically revise
answers with this judge.** No production promotion, weight update, third automatic
attempt, real-data study, ledger row, model pull, cloud/API expenditure or push.

The score difference is descriptive for six visible, agent-authored invented
evaluation cases, not statistical evidence that every judge is harmful or proof
that a future independently calibrated approach cannot help. This result is an
honest rejection of this particular configuration under this budget.

## Next frozen test: verifier only, with fair deterministic controls

The user requested the next steps on 2026-11-19: deterministic output repair,
fresh robustness pairs, an independently reviewable development sample, and no
return to broad model expansion. The judge remains disabled.

[`asof.verified_reader`](../src/asof/verified_reader.py) may repair **only a blank
unit**. It first validates every other answer field without coercion, requires a
verbatim normalized quote and the requested year, then requires a uniquely matching
issuer/metric/value/year/unit binding in a finite sentence grammar. The binding
must occur inside the cited quote. Multiple compatible values/units, another year,
a fabricated quote or a wrong explicit unit are rejected; values/years/explicit
units are never rewritten to match gold. Unrelated JSON errors remain invalid.
Existing justified abstentions are preserved; their factual correctness is not certified.

Supported units are USD/EUR million/thousand, `%` and `subscribers`.
Supported forms are the original explicit reported-metric sentence and two finite
subscriber wordings. This is **not general financial entailment**: unsupported
language stays unavailable, and a relation parser cannot establish truth from an
arbitrarily negated/qualified real-world paragraph.
Only necessary source checks and this declared grammar are enforced.

### Fresh paired fixture and allocation

The [new authored fixture](../tests/fixtures/verified_reader.json) has 24 cases in
12 pairs: sentence order, changed issuer/year/sign/currency/scale, conflicting values,
industry distraction, metric definitions, subscriber wording, ambiguous currency,
and whitespace/case. It uses new names/numbers, not regraded old cases.
The [plan](../results/verified_reader_plan.json) is committed before inference:

- At most **24** local generation calls; no critic, revision, retry or prompt search.
- Existing model/digest, unchanged generator prompt, fixed seed 202611190752.
- Same 20-minute / one-CPU / no-GPU/cloud/pulls / 6-GiB resource contract.
- New output `results/verified_reader.json` and private `data/verified_reader_v1`.
- Preserve/hash both old judge results; do not regrade their missing-unit failures.

Arms: the old narrow parser, a **stronger binding parser**, fixed single-pass LLM,
and that exact same raw LLM output plus deterministic verification.
Verification latency is recorded separately as well as added to the shared model
call. There is no second generation for the verified arm.
The stronger parser exposes how much apparent improvement is already encoded by
the binding rules: do not credit the LLM for a capability the deterministic parser has.

Report all-planned correctness/coverage, invalid/wrong answers, corrections/regressions,
both-correct pairs and transformation violations. A pair of consistently wrong
answers can satisfy an invariant, so invariant agreement alone is not success.
Invalid/unattempted pairs remain separate. The authored fixture deliberately uses
the supported grammar and exercises a known weakness; this is engineering robustness,
not independent test authorship, unbiased real-data performance or economic value.

### Real-source packet, not invented independent labels

The separate [packet plan](../results/reader_review_plan.json) permits only the
previously date-cleared, content-pinned `data/kpi_omission_dev_v1` derivative.
No new raw-cache body, mixed ZIP/parquet, quarantined source, SEC request or outcome
dataset may be opened. Every annual/context metadata reference is guarded before
the text-containing derived JSON is read; the old manifest/case pins must match.
This intentionally reuses the already exposed 2012-2018 cohort, not a fresh holdout.

[`asof.reader_review`](../src/asof/reader_review.py) selects up to 12 mention-bearing
current excerpt windows, one per issuer, by frozen hash rank `seed:case_id:family`.
Minimum six or stop; there are no replacements from raw sources. Evidence windows
are bounded at 1,024 characters. Preparation has a 30-second/256-MiB observed
RSS check before writing excerpts, with explicit input byte caps (256 KiB manifest,
1 MiB derived JSON). This is not OS mount isolation.

The private packet includes exact provenance, the metadata reporting-year target,
source windows and limitations; no model answers, expected values or proposed labels.
Two first-pass CSV templates have blank reviewer IDs, answers and blindness declarations.
The existing intake report type is reused, but the original H1 date/label profile
is **not** broadened or rewritten for this task.

The new check requires distinct declared reviewer IDs, full item coverage, no
AI-suggestion exposure, explicit supported/unsupported-within-excerpt/insufficient-context
status and rationale. Supported tuples also need finite values, the requested
year and verbatim evidence. Declarations do not authenticate independence; even
agreement remains subject to source/adjudication review and never creates gold automatically.

An excerpt may lack enough entity, definition or period context. The correct
label then is `insufficient_context`, not an invented number or a claim that the
full filing lacks the metric. This packet is conditional on prior lexical coverage,
not a representative accuracy audit. No independent reviewer is currently assigned.

Private outputs stay under `data/reader_review_v1`; public receipt contains counts,
scope and hashes only. The curator reads old text-containing JSON, including prior
snippets; it is not metadata-only. Creating blank templates is not completing
independent review, hiring reviewers or obtaining real gold.

Both operations require committed source/plan freezes and exclusive attempt markers.
No automatic promotion, weight updates, public raw-text release, source repair,
H4/H6 hold release, return trial, production ledger row or push.

Pre-execution checks for the verifier/packet profiles: **680 tests passed in
66.26 s**, with two existing synthetic rank-deficiency warnings; Ruff and local
documentation/index checks passed. Added fixtures cover unique blank-unit recovery,
ambiguity/refusal, no-gold behavior, paired metrics, source-date-before-derived-read
ordering, unlabelled templates and reviewer-independence blockers.
No new local generation or real derivative read occurred during those checks.

## Observed verifier-only result and private review preparation

Code, plans and cases were frozen at
`22f4452c183363b9f433c9ba5f19b5eba04d41fe`. The private-packet aggregate receipt
was then committed at `018e9e3bf5da1ccc2f094f2312a35dc0cc14e568`, without changing
those source files. Model generation froze those same source bytes at the latter
commit. [Actual verifier receipt](../results/verified_reader.json);
[packet preparation receipt](../results/reader_review_packet.json).

### Fresh authored robustness comparison

All **24 cases / 12 pairs** completed, using 24 initial-generation calls and **zero
judge/revision calls**, in **568.782 seconds (9.48 minutes)**.

| Arm | Correct outcomes / 24 | Answered values | Correct abstentions | Other outcomes |
|---|---:|---:|---:|---|
| Old narrow parser | 21 | 16 | 5 | Three grammar misses |
| Stronger binding parser | 24 | 19 | 5 | None on this authored fixture |
| Raw single pass | 21 | 17 | 4 | Two invalid missing-unit responses, one answer to an ambiguous source |
| Same single pass + verification | 24 | 19 | 5 | None on this authored fixture |

Verification corrected **three** outcomes and regressed **zero**:

- R10-0/R10-1: the subscriber value, reporting year and quote were present, but
  the model omitted the unit. The unique quoted binding supplied `subscribers`.
  Raw model outputs remain scored invalid; the repaired arm is distinct.
- R11-1: the source made unreconciled USD/EUR claims for the same metric/year.
  The model answered one; verification refused the ambiguous binding and abstained.

All twelve verified/binding-parser pairs had both cases correct and zero declared
relation violations. Raw single pass had ten both-correct pairs, one relation
violation and one invalid-output pair; the old parser had ten both-correct pairs
and one relation violation. Relation agreement alone can conceal wrong answers;
both-correct and invalid counts therefore remain visible.

**The stronger parser also got 24/24. That is the most important control.**
It took about **0.0069 seconds total** for the measured parsing over 24 cases, versus
**565.813 seconds** of model-call latency. Verification itself added only about
**0.0030 seconds total**, but it did not remove the cost of the original model call.
Model arms share that generation; do not sum them as independent call costs.
Unique model output tokens were 1,632.

This fixture deliberately uses a finite supported grammar and known failure types.
New names/numbers and paired perturbations are not independent financial gold or
generalization to real disclosures. **The result supports the deterministic rules
on this subset; it does not show that the LLM adds value beyond the stronger parser.**
For known supported language, prefer the deterministic path. The broader
answer-first default remains unchanged; no experimental model/verification pipeline
is automatically promoted to an unqualified real-data default.

Resource/source checks passed: observed combined peak working set
3,912,040,448 bytes (3.64 GiB), one CPU, worker exit 0. Both older judge result
hashes matched their frozen values. The one-attempt markers and all raw responses
are retained; no seed changes, retries, model pulls, training or return evaluation.

### Real-source packet: actually prepared, not independently labelled

The approved prior derivative was read only after guarding all 263 references in
its 64-case parent manifest. All declared date roles were inside the shared
2012-2018 envelope (combined 2012-09-30 through 2018-12-06).
Manifest input was 176,415 bytes; text-containing derived JSON was 629,817 bytes
and matched the preexisting pin. No raw filing cache, mixed ZIP/parquet, quarantined
source, prices or outcome dataset was opened.

Preparation selected **12 issuer-disjoint current excerpt windows** and wrote a
private packet plus two blank review CSVs under `data/reader_review_v1`.
It completed in 0.109 seconds, with process peak RSS 35,180,544 bytes, unchanged source,
zero model calls and zero raw-cache body reads.
Packet SHA-256:
`3b2cf99bbb7b4e163f0b420a6bdd1f42a13b63b2d24b209ef61cb1b25fefb2a9`.
Only aggregate hashes/counts were committed; snippets and identities remain private.

**Independent reviewers are still unassigned, intake is blocked, and gold labels
remain zero.** We prepared the evidence and neutral first-pass forms; we did not
perform two reviews, contact people, invent labels or declare agreement.
The source windows are a selected prior exposed cohort and may be too narrow to
establish identity/unit/year. Reviewers must use `insufficient_context` when necessary.
No automatic promotion or economic claim follows from packet preparation.

## Harder evaluation: format failure boundaries, not higher-looking scores

The user selected **harder_evaluation** on 2026-11-19. The previous grammar-controlled
24/24 must not be improved by adapting the same parser to another conveniently
matching fixture. Instead, the parser, binder/verifier, generator prompt, answer
schema and existing primary score remain **unchanged** for this new test.

[`asof.reader_stress`](../src/asof/reader_stress.py) generates **288 invented cases
in 144 pairs**, from a frozen [definition](../tests/fixtures/reader_stress.json).
Twelve format families each have twelve numeric/name variants and two members:
one canonical positive prose control, one stress variant. Thus 144 cases are
controls and 144 are stress formats, not 288 hard real disclosures.

Families: table-header units, scaled-unit headers, footnote unit overrides,
parenthesized negatives, missing-value dashes versus zero, superseded corrections,
consolidated/segment scope, pronoun/header entity context, noncalendar fiscal years,
counterparty distractors, quoted nonfacts and malicious source instructions.
These are authored semantic examples, not real financial outcomes or an independent
natural-language gold set. Repeated template variants are not independent market
observations and no binomial generalization claim will be made from their count.

### Frozen audit allocation

- Evaluate the two unchanged deterministic parsers on all 288 cases.
- Choose exactly one complete pair per family by minimum SHA-256 of
  `seed:pair_id`, seed `202611190824`, before any model result: **24 model cases**.
  Selection does not depend on observed correctness, difficulty or a preferred score.
- Initial generation only, no judge/revision/retry, at most 24 calls. The verified
  arm consumes that exact same raw output. No automatic training/promotion.
- Same model/digest, context/output limits, 20 minutes, one CPU, no GPU/cloud/pulls
  and 6-GiB owned-process resource contract.
- New [plan](../results/reader_stress_plan.json), result `results/reader_stress.json`
  and ignored `data/reader_stress_v1`; preserve/hash all three old model results.

The expansion is **288 deterministic cases plus a 24-case stratified model audit**,
not 288 model generations. Runtime sampling/seed/code, prompts, metrics and allocation
are committed before generation. The old simple/verified results are not overwritten.
Another shared server/native process was observed before this task; it is unrelated
to the new owned Job and must not be modified or stopped.

### Scoring without hiding contract limitations

Report control and stress strata separately, overall and by family:

1. Original strict answer/evidence contract, with invalid/missing/abstained cases
   retained in denominators.
2. Exact authored value/unit/year tuple correctness **without** the evidence-occurrence
   requirement, as a diagnostic only, never a replacement acceptance score.
3. Answer coverage, wrong tuples, correct tuples failing evidence checks and specific
   grounding failures.
4. Both-correct pairs, relation violations and invalid/unattempted pairs.
5. Same-output verified corrections/regressions and measured call/verification cost.

Example: a correct negative value read from parentheses may fail the old literal
minus-sign occurrence check. A correct pronoun-based answer can lack the issuer
name in its single-sentence quote. Those failures must be distinguished from an
incorrect financial tuple; neither diagnostic certifies general semantic truth.
No scorer or verifier is loosened after seeing which cases fail.

### Difficult output accounting

For **this profile only**, a completed generation ending at its output-token limit
counts as an invalid case and proceeds to the next frozen case, without retry.
Neither model arm may parse or repair that truncated output, even if a partial JSON
object happens to look usable. This measures bounded completion instead of allowing
the first hard output to censor the entire format audit.
Input truncation, missing input-fit/telemetry evidence, incomplete transport, HTTP/
timeout, scope or resource failures still stop the run and retain partial receipts.
The older profiles keep their original stop rules.

This is a failure-discovery experiment, not a requirement to beat the previous
24/24. Lower scores under realistic format shifts are useful evidence. Independent
real-source review remains unassigned; this batch does not read or label the private
review packet or manufacture the missing gold.

Pre-execution validation: Ruff and documentation/index checks passed. The full
684-test run had **683 passed and one failure** in the unchanged
`test_serial_start_rate_and_duplicate_request_stop`: the mocked request gap was
0.485 s against its 0.49 s assertion. The isolated timing test rerun together with
the affected reader tests passed **21/21**. No request-rate implementation or
threshold was changed, and no second clean full-suite result is claimed.
The generator/scorer and binding-verifier files were byte-compared with the prior
24-case run's recorded hashes and were unchanged before this harder execution.

## Observed harder audit: the old perfect score was format-specific

The [actual harder-audit receipt](../results/reader_stress.json) records the one run
frozen at `ebfda0d75c3c88ecbec5e1da556b26d4217d3358`.
All **288 deterministic cases** and the separate **24 model cases** completed,
with 24 initial-generation calls, no critic/retry/training, in **591.391 s (9.86 min)**.
All model responses were schema-valid and none hit the output cap.

### Offline deterministic coverage: 288 cases, not model generations

| Unchanged implementation | Canonical prose controls | Stress-format variants |
|---|---:|---:|
| Old narrow parser | 144/144 | 24/144 |
| Binding parser | 144/144 | 36/144 |

The narrow parser answered twelve quoted-nonfact examples as if their embedded
fictional sentence were a disclosure. Its other stress failures were mainly
abstentions on unfamiliar language. The binding parser avoided those wrong
answers but still missed 108 answerable stress variants.
These template repetitions are format coverage, not 288 independent real financial
observations. The old 24/24 result has not been rewritten; it was limited to its
supported grammar and did not establish generalization.

### Stratified model audit: twelve control/stress pairs

All arms scored 12/12 on their canonical control cases.
On the **twelve stress cases**:

| Arm | Full evidence-contract outcomes correct | Value/unit/year outcomes correct, ignoring evidence requirement | Answered values |
|---|---:|---:|---:|
| Old narrow parser | 2/12 | 2/12 | 2 |
| Binding parser | 3/12 | 3/12 | 1 |
| Single-pass LLM | 5/12 | 12/12 | 10 |
| Same LLM output + current verifier | 3/12 | 3/12 | 1 |

Correct outcomes include appropriate abstentions on two unanswerable stress cases.
The LLM's ten other stress answers matched the authored value/unit/year tuples;
seven did not meet the unchanged evidence contract. **Those are not seven wrong
financial tuples.** The raw primary `wrong_answer` label includes emitted answers
that fail source/evidence requirements; the new diagnostic separates that from
wrong tuple content without changing acceptance or regrading old results.
Tuple-only correctness does not certify reliable sourcing, real financial validity
or accuracy beyond these authored cases.

Across all 24 audited cases, full-contract counts were parser **14/24**, binding
parser **15/24**, single pass **17/24**, and verified **15/24**.
The verifier corrected zero outcomes and regressed two. The two regressions were
the superseded-correction and consolidated/segment-scope cases: the raw answers
already met the primary contract, but the finite binding grammar refused them.

### What actually failed

| Format | Raw tuple | Primary evidence result | Current verifier |
|---|---|---|---|
| Table headers / scaled headers | Correct | Selected quote omitted issuer, period and unit context | Refused unsupported grammar |
| Footnote unit override | Correct | Footnote quote lacked the number and issuer/year context needed to support the tuple | Refused unsupported grammar |
| Parenthesized negative | Correct | Literal minus-sign number was not present in the quoted parentheses representation | Refused unsupported grammar |
| Superseded correction | Correct | Passed primary evidence checks | Regressed to abstention |
| Consolidated versus segment | Correct | Passed primary evidence checks | Regressed to abstention |
| Pronoun, fiscal-year, counterparty context | Correct | Quote omitted explicit issuer token | Refused unsupported grammar |
| Dash-not-zero / quoted nonfact | Correct abstention | Passed | Preserved abstention |
| Malicious source instruction | Correct tuple | Passed in this one audit variant | Passed |

One resisted instruction variant is not an injection-security certificate. Likewise,
a correct tuple with an incomplete citation is not a qualified evidence-linked answer.
The failure pattern is a contract/representation limitation as well as a coverage
limitation, not a justification to loosen checks blindly.

Pairs with both members meeting the full contract were 2/12 for the narrow parser,
3/12 for the binding parser, 5/12 for the LLM and 3/12 for verified output.
Raw LLM predictions had zero declared tuple-relation violations; the verifier
introduced eight by turning valid format-dependent answers into abstentions.
Neither invariance alone nor a tuple-only score establishes semantic evidence.

### Decision and resources

The result does **not** justify default promotion of the current verifier or an
automatic return to the judge. It does show that the stronger parser's prior perfect
score was not evidence that the LLM was useless outside its grammar.
The model demonstrated broader tuple extraction on this small authored audit,
but the single-sentence citation contract and narrow verifier did not capture it reliably.

The next candidate design, if separately approved, should represent **linked evidence
bundles**: value cell/span plus applicable unit/header/footnote, reporting period,
entity and scope, and explicit correction priority. It should not merely search
for those words anywhere in a document or remove source checks to inflate accuracy.
That would be a new version, evaluated beyond these now-exposed cases and eventually
against independently reviewed real sources. No such parser/scorer change was made
during or after this audit.

Observed peak combined working set was **4,026,531,840 bytes (3.75 GiB)**; one CPU,
source/resource checks and worker exit 0 passed. Unique generated tokens were 1,484.
The 24 model calls consumed about 588.438 s; verification added about 0.0034 s but
still could not handle the out-of-grammar evidence. All four sampled owned PIDs
were confirmed absent, port 11435 closed and the shared Ollama process remained.
No actions were taken against the unrelated preexisting native process.

All three previous model-result hashes remained unchanged. No real disclosure,
private review packet, held source, prices, fundamental outcomes or production
trial-ledger content was read; no row was appended, source repaired, model pulled,
weights trained, experiment retried or push performed.
The independently reviewable private packet remains unlabelled, with reviewers unassigned.
Software validation retains the disclosed full-suite timing-test failure and isolated
recheck; a clean full regression result is not claimed for this batch.

## Linked-evidence improvement: a new explicit contract, not regraded old scores

The user requested the evidence improvements and best supported scoring on
2026-11-19. [`asof.linked_reader`](../src/asof/linked_reader.py) adds
`linked-evidence-v1`. The old single-quote scorer, old parser/verifier implementations,
generator prompt and all old results remain unchanged.

A positive result now carries a source SHA-256 and exact character-offset spans for
**value, metric, entity, unit and reporting year**, with scope, sign-convention,
footnote applicability and correction/supersession spans where applicable.
Evidence can cross a value cell, its year/header, a unit caption and its own footnote.
It is not enough for those words to occur somewhere in the document:

- Markdown year columns select their own value cells; row/selected-column units
  override declared defaults only when compatible.
- A row footnote must have the same marker and target metric. Missing/mismatched
  notes and contradictory row/column units make the query unavailable.
- Only explicit topic headings or named/first-person subjects establish entity
  context. A later different-company heading cannot inherit the earlier issuer.
- Prose period bindings are local; a publication year is not a reporting year.
- Parentheses need an explicit negative convention in prose; financial table
  amounts use the declared table convention unless source text contradicts it.
  Irregular comma grouping or double signs are rejected.
- Explicit same-query corrections supersede an original only with source priority
  evidence. Two unresolved correction values or unranked competing facts abstain.
- Marked fictional quotations and explicit source-instruction regions cannot supply
  facts, footnotes, sign rules or supersession evidence.

The validator recomputes the canonical source-bound relation and checks every span,
query identity and source hash. Changing a value, year, unit, entity, role/offset or
link path cannot manufacture an accepted proof. Construction/validation share these
deterministic rules; **they are not independent semantic adjudicators**.
This is a finite supported prose/Markdown grammar over at most 8,192 source characters,
not arbitrary financial entailment, an HTML/layout parser or XBRL conformance.
The existing float-based table baseline is preserved; exact Decimal amounts and
offset/footnote binding require this separate path rather than silently changing it.

### Same model output, explicit evidence completion

The model still emits the existing value/unit/year and original quote.
Completion requires that quote to occur in the source and seed at least one linked
component, and the explicit value/year/unit must match a unique bound fact.
Only a blank unit can be filled from that fact; an explicit wrong tuple or fabricated
quote is refused. Original citations and parsed/raw scores remain separate.
Supported abstentions are not replaced with numbers just to improve coverage.

`linked_parser` supplies a strong **no-model control** using the same source rules.
If it matches model-assisted scores, do not attribute its deterministic capability
to the LLM. A full linked score means both the authored tuple/refusal and the new
source-proof contract pass; it is **not the original single-sentence score renamed**.
Answerable and unanswerable counts are reported separately to expose abstain-all behavior.

### Development exposure versus fresh challenge

Development has already inspected the earlier 288-case format suite and 24 saved
parsed model outputs. The initial prototype replay reached 288/288 deterministic
and 24/24 completed saved outputs under the **new** contract, versus 17/24 raw
original-contract outcomes. This was an exposed, posthoc engineering diagnostic,
not an independent gain, new model run, original-score replacement or release criterion.
The final frozen replay will be recorded separately in the new receipt.

The [new 24-case challenge](../tests/fixtures/linked_challenge.json) contains twelve
paired supported/insufficient-or-conflicting cases: swapped year columns, row/column
units, row-specific footnotes, entity resets, competing corrections, consolidated
scope, sign conventions, unrelated unit mentions, publication dates, instruction-only
footnotes and duplicate facts. Positive/negative counts are 12/12.
These cases were authored with the design known; they are not secret or independent
human gold. Tests reject tampered and cross-context proofs and changing expected
labels cannot alter construction/completion.

The [plan](../results/linked_reader_plan.json), code, prompts, challenge, posthoc-replay
inputs and this contract are committed before new generation.
New private/public paths are `data/linked_reader_v1` and `results/linked_reader.json`;
all four earlier model results are hash-pinned and retained.
At most 24 generation calls, no critic/retry/training, same 20 minutes, one CPU,
no GPU/cloud/pulls and 6-GiB resource contract; seed 202611190926.
Output-token failures count invalid without salvage/retry; unsafe input/transport/
scope/resource failures still stop. No post-challenge retuning or automatic promotion.

Independent real-source reviewers remain unassigned and no new private source
window, fundamental outcome, price, production ledger row or held material is
accessed by this synthetic/model task. No public raw-source release, push or claim
that a high synthetic score establishes real-world accuracy.

Pre-inference validation for the linked version: **692 tests passed in 106.79 s**,
with two existing synthetic rank-deficiency warnings; Ruff and documentation/index
checks passed. This includes source-role tampering, cross-entity/year/unit/footnote
substitution, missing sign conventions, unranked corrections, unsupported trailing
scope qualifiers and no-gold construction tests. The older timing-test failure
remains part of its prior run history; no rate code or old test threshold was changed.

## Observed linked challenge: 23/24 completed, 24/24 deterministic control

The [actual linked receipt](../results/linked_reader.json) records the one challenge
run frozen at `4c0401438d3f12033fefc146d64fdd035e3f6d4b`.
All 24 cases completed using 24 initial-generation calls, **zero judge/revision calls**,
in **570.079 seconds (9.50 minutes)**. There was no output truncation or retry.

| Arm and scoring contract | Correct / 24 | Answerable correct / 12 | Negative correct / 12 | Wrong emitted answers |
|---|---:|---:|---:|---:|
| Old parser, original single-quote contract | 13 | 1 | 12 | 0 |
| Old binding parser, original contract | 13 | 1 | 12 | 0 |
| Raw LLM, original contract | 14 | 3 | 11 | 8 |
| Old verified LLM, original contract | 13 | 1 | 12 | 0 |
| Linked deterministic parser, **new linked contract** | **24** | **12** | **12** | **0** |
| Same raw LLM output + evidence completion, **new contract** | **23** | **11** | **12** | **0** |

These are not interchangeable score definitions. The old primary `wrong_answer`
label includes missing source-context evidence, not just wrong numeric tuples.
The new results require complete source-bound role proofs, rather than deleting
evidence checks, but they must not be presented as a like-for-like upgrade of old
single-sentence accuracy or as real financial gold.

A separately labelled **posthoc backward-compatibility check** discarded the new
bundles and applied the old scorer to the completed answers' retained quotes:
**15/24**, not 23/24. The 23/24 result specifically depends on the additional,
validated multi-span evidence. This check changed neither result files nor score
definitions and is not a new preregistered endpoint.

The one remaining completed-path miss was L01-0: the model incorrectly inferred
that the question required USD even though the applicable 2017 column explicitly
used EUR. It abstained despite identifying the EUR amount. Completion deliberately
preserved that abstention instead of silently substituting a number to hit 24/24.
The no-model linked parser resolved the column correctly.

One raw negative response was schema-invalid because its unit was blank.
The source itself had no applicable revenue-unit declaration, so the linked route
refused the unsupported source fact rather than filling a unit from unrelated text.
That is a separately scored safe refusal, not retroactive repair of the old raw score.

### Posthoc replay is development, not the fresh challenge

The final frozen rules also completed the old exposed 288 deterministic cases and
24 saved parsed stress outputs under the new contract: 288/288 and 24/24.
The latter had originally scored 17/24 under the old evidence rule. Those old scores
and raw results remain untouched. This replay used no new generation, was explicitly
after source/outcome exposure and is **not independent validation**.

### What earned support, and what did not

Within the declared financial-prose/Markdown subset, explicit source roles removed
the earlier citation bottleneck while all twelve fresh negative/cross-context
controls were correctly refused. Tampered roles/offsets and incompatible context
also have software regression tests. This is meaningful implementation evidence,
but the challenge was authored with the design known and the source grammar is bounded.

**The deterministic control matched or exceeded the model-assisted result.**
It took about **0.0131 s total** over the challenge; model-call latency was
**567.172 s** and evidence completion added about **0.0050 s**.
No incremental LLM advantage is established on this challenge, and no global
production default, model weights, source-access permission or research hypothesis
was changed. Prefer the deterministic path when its explicit input contract applies;
unknown formats and real-world semantic adequacy still need separate evidence.

Observed peak combined working set was **3,897,978,880 bytes (3.63 GiB)**.
One CPU, source/resource checks and worker exit 0 passed. Unique generated tokens
were 1,401. All four sampled owned PIDs were confirmed absent, port 11435 closed,
and the preexisting shared Ollama process remained. All four earlier model-result
hashes matched their frozen values.

The software suite passed 692 tests before this run, with two existing synthetic
rank-deficiency warnings; Ruff and documentation checks passed.
No post-challenge parser/scorer tuning, third-party model/API call, new download,
real-source/private-review read, financial backtest, training, production trial
ledger row or push occurred. The twelve real-source review windows are still
unlabelled; independent reviewer assignment and real gold remain outstanding.

## Parser-first field records: frozen comparison plan

The user approved this next step on 2026-11-19: preserve historical scores, add a
separate parser-first candidate, measure individual fields and complete records,
broaden the challenge, and obtain independent source review before real-world claims.
The first four engineering/evaluation tasks can run locally. **Actual human review
cannot be replaced by this assistant, a model judge or synthetic labels.**

### Historical scores and common new endpoint

All five prior model receipts stay immutable and historically scoped. None is
deleted, regraded or rerun to chase a perfect headline. Old single-quote and linked
scores remain different contracts. They are regression/evidence records, not a
current general-accuracy estimate.

[`asof.reader_fields`](../src/asof/reader_fields.py) introduces `field-record-v1`.
On identical new inputs, four arms share this endpoint: old linked parser, old
model-output evidence completion, guarded source parser, and parser-first routing.
Every arm must pass the same field/context requirements. Per-case legacy linked
scores are retained separately; historical result files are never altered.

The parser-first candidate tries a qualified deterministic source relation first.
It can answer independently of an unnecessary model abstention, but that is a
**separate source-selected answer**, never a rewritten raw model result.
Explicit incompatible context is refused without model fallback. Unresolved
grammar can use the saved initial model output, still subject to the same source
proof and context guards. This fallback shares the finite source validator: it
does not establish general semantic extraction outside that grammar.

New safeguards reject GAAP substrings inside a non-GAAP definition and subannual
periods for an annual year-only request. The model's new-profile input explicitly
states that annual requirement; the old generator module is unchanged.
An added exact-offset per-share rule accepts one complete canonical source
sentence, including issuer, requested metric, value, currency/denominator and year.
It has contract `field-source-v1`; existing relations retain `linked-evidence-v1`.
Both proofs feed the common field-record scorer. Unsupported prose, quoted examples,
different denominators and tampered proofs are not accepted by that extra rule.

### Field dictionary and denominators

| Field | Meaning and limit |
|---|---|
| `value`, `sign` | Exact stated decimal and derived negative/zero/positive; no economic conversion |
| `currency`, `scale`, `measure` | Explicit currency/scale; percent, subscribers and the bounded per-share form remain distinct |
| `reporting_year` | Requested four-digit annual year; no invented period start/end dates |
| `issuer_binding`, `metric_binding` | Source association to the supplied query, **not independent entity/concept discovery** |
| `scope` | Bound consolidated/segment label or explicit applicable scope caption; otherwise unknown |
| `accounting_basis` | Bound GAAP/non-GAAP label or explicit applicable basis caption; not assumed |
| `period_kind` | Explicit fiscal/calendar-year context; otherwise unknown, never automatically calendar year |
| `revision_status` | Explicit original/correction selection status; otherwise unknown, not a claim of latest real filing |
| `source_evidence` | Source hash, exact role offsets, tuple agreement and supported context validation |

`unknown`, `not_applicable` and `unanswered` are separate states. A zero is a
reported numeric value; a dash/nil is not coerced into zero. Unknown context means
not established under this bounded source grammar, not absent from an entire filing.
The source-relation constructor and validator share rules; this is not independent
semantic adjudication, XBRL conformance or proof of financial truth.

Each positive case contributes to each field denominator, including abstentions,
invalid outputs and unattempted cases. Known-value counts are also shown separately,
so correctly leaving many fields unknown cannot masquerade as discovering them.
Whole-record correctness requires **every field** plus source evidence. Negative
cases are scored as correct refusals, never as thirteen correctly extracted fields.
Answer precision, correct-answer coverage and wrong emitted records stay separate;
abstaining everywhere must not look successful.

### New authored challenge and one-run contract

The [fixture](../tests/fixtures/reader_fields.json) contains 24 cases in twelve
positive/negative pairs. Families cover zero/missing, currency/scale, annual fiscal
versus quarterly periods, consolidated/segment scope, GAAP/non-GAAP identity,
correction priority, footnote units, signs, entity resets, percent, subscriber counts
and per-share denominators. All cases are invented, author-visible and exposed
during software development; this is **not blind independent evaluation**.

The [plan](../results/reader_fields_plan.json) permits one frozen paired model
comparison: 24 initial calls maximum, no judge/revision/retry, existing qwen3.5:4b
digest, one CPU, zero GPU/cloud/pulls, 20 minutes and the same 6-GiB owned-process
contract. It uses new output/attempt locations and hashes all five older reports.
All candidates and the common scorer are frozen before generation.
Output truncation is an invalid raw response, never salvaged; an independent source
parser can still answer without using that response.

All 24 initial generations are deliberately requested for the paired comparison,
even when parser-first could have skipped them. Report actual calls separately
from **counterfactual** route-needed calls/latency. Do not call those estimated
savings an observed deployment wall-time result.
The broader answer-first application default remains unchanged; no automatic
production promotion, weight learning, hypothesis alteration or source-access release.

### Independent review: an explicit remaining prerequisite

The existing private packet has twelve excerpt windows and two blank first-pass
forms; actual reviewers remain unassigned and independent labels remain zero.
This task does not reopen those excerpts, contact anyone, fill the forms or fake
two independent passes. Two actual blind reviewers must complete them, disagreements
need adjudication and evidence provenance, and insufficient context stays unresolved.
Existing value/unit/year forms alone cannot qualify all the new scope/basis/period
fields: additional source-context annotations are required for full-record gold.
No synthetic score, model confidence or agreement between these parsers lifts that gate.

Pre-generation verification: **700 tests passed** in 95.63 seconds, with two
existing synthetic rank-deficiency warnings. Changed-file Ruff and documentation/
index checks passed. The Pylance reference request timed out; no editor type-check
success is claimed. The deterministic development check was old linked parser
21/24 versus guarded parser 24/24 under the common field contract; those authored
sources and expected labels were visible during development, before model execution.

## Observed field comparison: complete positive records; fallback still adds a failure

The [actual receipt](../results/reader_fields.json) records the single run frozen at
`f252a592149bdf57f1970cb4e6a0330afa6c926f`. It completed all 24 initial calls in
**776.922 seconds (12.95 minutes)**, without judge, revision, retry or output
truncation. There were 23 schema-valid responses and one schema-invalid response.
No candidate, scorer or fixture was changed after generation.

All four rows below use **the same new inputs and `field-record-v1` endpoint**:

| Arm | Correct outcomes / 24 | Complete positive records / 12 | Correct negative refusals / 12 | Wrong emitted records |
|---|---:|---:|---:|---:|
| Old linked parser | 21 | 11 | 10 | 2 |
| Old model-output evidence completion | 20 | 9 | 11 | 0 |
| New guarded source parser, no model | **24** | **12** | **12** | **0** |
| New parser-first + model fallback | **23** | **12** | **11** | **0** |

This is not a regrading of the five historical runs. The new primary endpoint
includes the additional context requirements, and the annual query is explicit.
The new source parser achieved 100% answer precision and correct-answer coverage
on this authored sample, not established real-world accuracy.

### Actual field checks: known values versus unknown/not-applicable targets

Both new paths passed all thirteen field checks on every positive case: **156/156
field checks**, of which **112** had known-valued targets and **44** were explicitly
unknown or not applicable (40 unknown context targets; four nonmonetary currency/
scale targets). These are correlated checks on twelve records, not 156 independent
facts. Issuer/metric identities were supplied queries; source association, not
independent entity/concept discovery, was tested.

| Field | Correct on all positive cases | Known-valued targets correct |
|---|---:|---:|
| Value, sign, measure, reporting year, issuer binding, metric binding, source evidence (each) | 12/12 | 12/12 each |
| Currency, scale (each) | 12/12 | 10/10 each |
| Scope | 12/12 | 2/2 |
| Accounting basis | 12/12 | 2/2 |
| Fiscal/calendar period kind | 12/12 | 3/3 |
| Revision status | 12/12 | 1/1 |

The tiny known-context denominators are a limitation, not evidence that these
dimensions are solved. We still do not extract complete filing schemas, arbitrary
period endpoints or every possible unit/definition.

### What improved, and what remains wrong

- The old source parser accepted the quarterly F03-1 amount as annual and matched
  GAAP inside the non-GAAP F05-1 definition. The separate candidate refused both.
  Its bounded per-share proof also answered F12-0, which the old grammar missed.
- The raw model unnecessarily refused F02-0, claiming it needed an exchange rate
  to convert the explicitly selected EUR-thousand column to a USD-million default.
  The parser-first answer used the column's stated units without conversion.
- F04-0's raw model returned `billion USD` rather than the stated `USD billion`.
  The old completion rejected that explicit noncanonical unit rather than rewriting
  it. Parser-first selected its own correctly bound source record. This does not
  establish that unit-word-order normalization is economically unsafe; it documents
  a remaining limitation of the old canonical-unit contract.
- F12-0's raw model tuple was correct, but the old source validator did not support
  that per-share grammar. The new independent source route supplied the qualified proof.
- **F06-1 remained invalid in the model-fallback path.** The source had two unranked
  corrections; the raw response violated the answer schema. It was not converted
  into a successful abstention. The no-model parser correctly refused the ambiguity.

All twelve positive records were selected by the source parser, while two explicit
context failures took the source-refusal route. Ten remaining cases used model
fallback: nine correct refusals and one invalid output, **zero added positive
completions**. For this bounded contract the guarded no-model control did better.
There is no evidence here that adding a judge, larger model or more retries is the
next useful step. Keep that conclusion local to this grammar and exposed sample.

### Runtime, provenance and remaining gates

The paired audit actually made **24 model calls** and generated 1,366 unique output
tokens. The parser-first route would have required ten calls on these same inputs:
that is a **counterfactual**, not an observed ten-call deployment.
Summed selected-route time was about 243.623 s versus 769.628 s for the old model
completion, excluding unused paired generations and startup; these are not
end-to-end deployment wall-time measurements. Measured guarded-parser computation
over the challenge totalled about 0.0229 s.

Observed peak combined working set was **3,929,235,456 bytes (3.66 GiB)**.
One CPU, source/resource checks and worker exit 0 passed. All four sampled owned
PIDs were confirmed absent, port 11435 closed and the preexisting shared server
remained present. All 96 serialized arm records were reconstructed and rescored
without changing the saved receipt; all five historical result hashes matched.
The production ledger was checked by file-size metadata only (106,246 bytes);
no row was appended and no ledger content was opened.

The 700-test, Ruff and documentation checks recorded above preceded generation.
Only result/navigation/documentation edits followed it. No model rerun, source
retuning, real-source/private-review read, financial study, download, training,
default promotion or push occurred.

**Independent source review is still blocked:** no actual human labels were
supplied. The existing twelve-window preparation receipt is not a completed review,
and its narrow blank forms cannot establish the expanded context gold without
additional annotations. Human first passes and adjudication remain a user/independent
reviewer action; they have not been fabricated or silently counted as done.

## Reliability follow-up: source gating, equivalent units and paired response shapes

The user requested further improvements on 2026-11-19 and resumed the interrupted
validation before any new model call. The [new module](../src/asof/reader_reliability.py)
targets the remaining mechanics, without rewriting historical receipts or claiming
that a repeated synthetic perfect score is independent evidence.

- **Admission before generation:** `source_gated` uses the qualified source parser
  and sends unresolved cases to review, without calling a model that the same finite
  source validator cannot admit as a new fact. This is the existing guarded parser's
  extraction coverage with an explicit no-fallback policy, not a broader parser.
  An unresolved answerable case still counts as missed, never as proof of absence.
- **Unit identity, not conversion:** the new completion accepts explicitly
  equivalent `billion USD`, `billions of USD` and `USD billion` labels, but only
  when the source-bound value, currency, scale, year and verbatim value/metric
  seed agree. It accepts the existing qualified per-share proof. It never rewrites
  a currency, scale, numeric value or reporting year, and records the original
  response and any normalization operation. Invalid responses remain invalid;
  unnecessary model abstentions are not overwritten by this completion arm.
- **Constrained response shape:** a two-branch JSON schema separates complete
  supported answers from explicit abstentions with null/empty fields. Runtime
  validation remains authoritative; a decoding constraint does not prove correct
  reasoning or source support. A model can still confidently choose the wrong fact.
- **No invented FX requirement:** both new generation arms explicitly receive
  no target currency/scale and instructions to preserve the selected fact's units.
  That reminder is shared across the paired comparison, not changed between arms.

### Frozen audit allocation and scoring

The [new fixture](../tests/fixtures/reader_reliability.json) remixes the previous
twelve authored families with new names, values, units and reporting year.
All **24** cases receive deterministic source-gated evaluation. A fixed six pairs
(`U02`, `U03`, `U04`, `U06`, `U10`, `U12`) form the **12-case model audit**:
selected currency/scale, annual versus quarter, scope, conflicting corrections,
percent and per-share denominators. Selection targets known development weaknesses;
it is not a representative sample or blind generalization test.

Each of these twelve cases gets one free-form and one schema-constrained initial
generation: **24 calls total, not 24 cases per model arm**. Both use identical
messages, model/digest, seed and resource limits except for the schema parameter.
SHA-ranked ordering puts constrained generation first on six cases and free-form
first on six. Each request is an isolated source question; no previous answer or
gold is supplied. No judges, revisions, seed retries, model pulls or training.

The [plan](../results/reader_reliability_plan.json) retains one CPU, zero GPU/cloud,
6 GiB and 20 minutes, with a 90-second call cap. Output truncation counts invalid
without salvage; transport/input/resource failures stop with partial accounting.
New attempt/result paths and all six older result hashes are frozen before execution.

On each model response, retain both the old evidence-completion baseline and the
new normalized completion. All four completion arms plus source gating share
`field-record-v1`; show whole records, field denominators, coverage and wrong answers.
Separately report original `Answer` schema conformance and stricter wire conformance,
actual call time, same-output corrections/regressions and normalization events.
This tests output shaping against the paired free arm; it does not isolate the new
shared unit reminder from historical prompts. Comparing different vintage scores
cannot establish a causal improvement in model reasoning.

The no-model source-gated control is measured before either generation and its
actual computation time is separate from the full paired audit's model time.
Do not claim that skipping post-hoc failed model answers achieved a faster deployment:
the source policy is frozen and uses no model output or expected labels.

These are author-visible format/implementation diagnostics, not human financial
gold. The independent-review gate, all held data paths, the production ledger,
historical results and broader application default remain unchanged. No real-source
packet is reopened or labelled, and no push is authorized by this experiment.

Pre-generation validation: the full suite recorded **705 passes and two failures**
in 532.84 s, with two existing rank-deficiency warnings. Both failures were unchanged
Windows Job tests whose owned children did not signal readiness within ten seconds
(`test_job_close_terminates_only_the_owned_blocked_worker` and
`test_packaged_job_pins_and_terminates_only_the_owned_gated_child`).
The isolated two containment checks plus affected reader tests then passed **31/31**
in 30.80 s. No resource code, test threshold or allocation was relaxed; a clean full
suite is not claimed for this batch. Ruff, documentation/index and input-fit checks
passed. The author-visible deterministic check was 24/24 over the new source cohort;
no new generation had yet occurred.

## Observed reliability audit: valid shapes improve; wrong-year reasoning remains

The [actual receipt](../results/reader_reliability.json) records the single frozen
`a76bc7971eb038deac1e11197df97e2156628f82` run. All **24 calls completed** in
**1,067.094 seconds (17.78 minutes)**. Each of twelve audit cases received both
generation formats; the separate offline source cohort contained 24 cases.
There was no retry, output truncation, judge, weight training or post-result tuning.

### Same twelve inputs, common field-record endpoint

| Arm | Correct / 12 | Complete positive records / 6 | Correct negative refusals / 6 | Wrong admitted records |
|---|---:|---:|---:|---:|
| Old completion on free generation | 9 | 4 | 5 | 0 |
| New completion on the same free output | 10 | 5 | 5 | 0 |
| Old completion on constrained generation | 10 | 4 | 6 | 0 |
| New completion on the same constrained output | **11** | **5** | **6** | **0** |
| Source-gated, no generation used | **12** | **6** | **6** | **0** |

Original-answer and strict-wire schema conformance were **10/12 free versus 12/12
constrained**. This is a paired format comparison, not a comparison of different
old score contracts. The new completion corrected one outcome and regressed none
on each version's saved output. Those two corrections were the same per-share case
U12-0: the new completion can use the already-qualified per-share source proof
that the old completion lacked. **The measured correctness gain was not a unit
word-order repair.** This run emitted canonical currency units; `percent` to `%`
normalization occurred once per generation arm without changing correctness.
Unit-word-order aliases have software tests, not an observed win in this audit.

The new constrained arm passed 65/78 positive field checks, including 47/56
known-valued targets. The source-gated audit control passed 78/78, including
56/56 known-valued targets. These correlated checks are not independent facts.
No new scope/basis/period discovery coverage is established by repeating templates.

### The unresolved model error is substantive, not malformed JSON

U02-0 requested the 2018 amount, whose column explicitly stated GBP thousand.
The free response selected the 2017 USD-million amount and simultaneously marked
it as an abstention with populated answer fields: invalid, not a successful refusal.
The constrained response obeyed the schema but still selected that **wrong 2017
fact**. The completion rejected the wrong period/value instead of converting it
or accepting its valid JSON. The shared no-target-currency reminder did not eliminate
the mistake. Thus **schema validity is not semantic correctness**.

U02-1's free output also mixed abstention with populated fields and remained invalid.
Its constrained counterpart correctly refused the incompatible row/column units.
The earlier conflicting-correction failure did not recur here: both fresh U06-1
outputs were valid refusals. That observation does not revise the old F06-1 failure.

The source-gated candidate selected the requested-year amount from its bound column
and sent unresolved sources to review **before any generation**. On the full
24-case offline cohort it scored **24/24**: twelve complete positive records and
twelve refusals, no wrong admitted records and zero model calls. All thirteen
positive field checks passed: 112 known targets plus 44 unknown/not-applicable targets.
This keeps the guarded parser's existing grammar; it is a routing simplification,
not evidence of a newly universal reader. Outside its grammar, an answerable item
can still be sent to review and must count against coverage.

### Actual cost and provenance

The full paired audit made 24 calls and generated 1,628 output tokens.
Free generation totalled 494.875 s, constrained generation 530.157 s (about 7.1%
more call time in this single, order-balanced run). Shared-worker conditions mean
this is not a robust latency estimate. The separately measured source-gated
computation over all 24 cases totalled 1.876 s, with no model generation used.
The 17.78-minute audit must not be described as a zero-model deployment run.

Observed peak combined working set was **3,850,702,848 bytes (3.59 GiB)**.
One CPU, source/resource checks and worker exit 0 passed. An auxiliary two-second
HTTP health probe timed out; the benchmark's own startup checks and all subsequent
generation/state requests completed without changing their limits or retrying
the experiment. All four sampled owned PIDs were confirmed absent, port 11435
closed and the preexisting shared server remained present.

All **84 serialized field records** (24 offline plus five arms on twelve audit
cases) were reconstructed and rescored. Raw schema-conformance and normalization
events were checked against saved responses. All six earlier report hashes matched
the freeze. Ledger file-size metadata remained 106,246 bytes; no ledger contents
were read or rows appended.

Validation remains the disclosed **705 passed / two unchanged startup-test failures**
in the full suite, followed by **31/31 isolated containment and affected-reader
passes**, with Ruff and documentation checks passing. Only result/documentation/
navigation edits followed generation; no clean full-suite claim is substituted.

These are author-visible invented cohorts, not independently labelled financial
sources. Independent reviewers remain unassigned, human gold stays zero, the held
sources stay held and the broader application default is not silently promoted.
The defensible gain is better response conformance and source-qualified completion,
not proof that all financial fields or model reasoning are solved.

## Source-cell selection and expanded field coverage: frozen plan

The user approved the field-audit follow-up on 2026-11-19: source-cell selection,
mandatory constrained model responses, larger known-context tests, differentiated
failure reporting and concrete independent-review preparation.
All seven prior model receipts stay immutable. No old score is rerun or rewritten.

### Select a source cell; never regenerate its tuple

[`asof.reader_cells`](../src/asof/reader_cells.py) reuses the guarded source parser
to enumerate its qualified issuer/metric cells across at most twelve candidate
reporting years. Each ID hashes the source-bound proof, including source SHA and
offsets. The catalogue can contain different-year distractors; the model sees
their explicit year, unit, value and supporting spans without any gold or target
correctness flag. A source change changes its IDs.

The model returns only an allowed `cell_id` with an empty reason, or null with a
bounded refusal reason. Numbers, units and years are not generated. Code rechecks
catalogue membership and requested year, then derives the answer from that cell's
proof. Foreign IDs, malformed selections and different-year selections are
rejected; none triggers a convenient substitution of the correct cell.
A model abstention on a supported query remains a miss.

**This is source-assisted selection, not independent table discovery.** The same
source parser can already resolve the requested year. A catalogue cannot recover
facts outside its grammar or ambiguous source contexts. The deterministic
source-only control is therefore essential; model selection must earn an increment,
not receive credit for work done by the parser.

### Known-value test expansion

[`reader_field_challenge`](../src/asof/reader_field_challenge.py) freezes **192
invented cases**: four dimension groups, each with 24 supported positives and 24
negative contrasts. Scope, accounting basis, period kind and revision status each
have **24 explicitly known positive targets** instead of mainly unknowns.
All 96 positives also have explicit value/sign/currency/scale/measure/year and
source bindings. Variants rotate signs/zero, currencies, scales and fiscal years.
Scope includes consolidated and named segment captions; basis includes GAAP and
non-GAAP; period kind includes fiscal/calendar annual captions with quarterly/YTD
contrasts; revision status includes explicitly original and superseding corrections
with missing-priority contrasts.

These are author-visible templates and mechanical variants, **not 24 independently
authored semantic formats per field or independent financial observations**.
The code records actual failure counts rather than assuming that a designed count
is a passing score. Unsupported cases remain explicit: arbitrary quarter/YTD
extraction, exact period dates, 52/53-week calendars, partial line-item restatement
semantics, independent entity/concept discovery and real financial accuracy.
Their safe rejection does not amount to extracting those fields successfully.

### Paired model audit

The [fixed plan](../results/reader_cell_selection_plan.json) permits twelve new
authored source cases (six positive/negative pairs) and **24 calls maximum**:
one strict tuple generation and one strict cell selection on each source.
Both response formats are mandatory schemas, not optional free-form arms.
Cases cover mixed column units, reversed/missing years, annual/subannual context,
GAAP definition, correction priority and per-share denominators.
The same model/digest, seed, one CPU, zero GPU/cloud/pulls, 20-minute/6-GiB limits,
90-second call cap and one-attempt receipts remain.

The reused SHA-order schedule balances cell-first and tuple-first on six sources
each. The tuple arm sees the original source and existing unit/annual constraints.
The cell arm additionally sees source-derived candidates, so this is a
**system-design comparison**, not an equal-information model-format ablation.
All three arms (strict tuple completion, cell selection and source control) use the
same `field-record-v1` endpoint. The 192 deterministic cases are separate from
the twelve model cases; no claim of 192 model generations is permitted.

Per-case diagnostics distinguish malformed response, wrong raw fields, unsupported
evidence, unnecessary abstention, unsupported grammar/context and correct refusals.
Raw tuple diagnostics compare numeric value/sign, currency, scale, measure and
year where a valid raw tuple exists. Record-level failed-field lists remain
separate: rejecting one wrong-year record is not thirteen independent numeric errors.

### Human actions still required: source-review runbook

The [public preparation receipt](../results/reader_review_packet.json) identifies
the existing private twelve-window packet and its pin:
`3b2cf99bbb7b4e163f0b420a6bdd1f42a13b63b2d24b209ef61cb1b25fefb2a9`.
No private excerpt is reopened by this implementation.

1. **Assign two actual independent reviewers.** Each must have authorized access,
   do a blind first pass without AI answers or the other person's labels, and use
   a consistent reviewer ID. This assistant does not contact people or authenticate
   reviewer identity. If you have seen model suggestions, do not declare an unseen
   blind pass; use other reviewers or disclose exposure and keep it exploratory.
2. Provide the existing private `data/reader_review_v1/packet.json` and one of the
   existing `reviewer_a.csv` / `reviewer_b.csv` forms to each reviewer. Check the
   packet pin before distribution; do not copy source snippets/identities into Git.
   Those forms cover supported value/unit/year or insufficient context.
3. Give each reviewer the matching **new supplemental context form**:
   `data/reader_review_context_v1/context_reviewer_a.csv` or
   `context_reviewer_b.csv`. These are generated from the public item count and pin
   only, without source reads, by
   `python scripts/prepare_reader_context_forms.py --prepare-blank`.
   The command creates 72 blank rows per file (six dimensions x twelve items),
   refuses overwrite and does not complete or authenticate a review.
4. For every item, annotate issuer binding, metric binding, scope, accounting basis,
   period kind and revision status. Choose `supported`, `unknown` or `not_applicable`.
   For supported values, provide zero-based character offsets `[evidence_start,
   evidence_end)` into the exact packet excerpt plus a rationale. Use `unknown`
   if required context is outside that window; do not browse a full filing or infer
   it from background knowledge to complete the form. Unknown/inapplicable rows
   have no value/span, but still require a rationale. Do not invent fiscal endpoints.
5. Return both base forms and both supplemental forms privately. The existing
   `check_reviews` validator checks base declarations. The new
   [`check_context_reviews`](../src/asof/reader_review_context.py) checks matching
   reviewer identities, packet pins, complete item/dimension coverage, blind
   declarations, offset bounds and state/value consistency, and lists value/state
   disagreements. These are mechanical checks, **not semantic gold**.
6. **Adjudicate disagreements and inspect supporting spans.** Keep both original
   passes; record an adjudicator and source-linked rationale. Equal labels or valid
   offsets alone do not certify entailment. Unresolved items stay out of accepted
   gold and remain visible in coverage counts.
7. If excerpts lack necessary context, separately approve a bounded eligible
   development-context expansion before any new reads. Existing source holds and
   holdouts stay closed. The selected twelve-window cohort cannot by itself
   establish broad representative accuracy; an independent evaluation design is
   still needed before a real-world claim or production promotion.

The required human work is reviewer assignment/access, actual independent labels,
adjudication and any explicit source-expansion/publication decision. No SEC/model
credentials, push, holdout opening or automatic release is needed for these steps.

Pre-generation validation: the affected reader/review tests passed **37/37**.
The full regression attempt stalled after 78 completed tests for over ten minutes
and its owned command was stopped; no completed/full-suite pass is claimed.
The two unchanged single-member Windows Job tests then failed their ten-second
readiness checks, while all 37 affected tests passed again (54.14 s total).
No resource helper or timeout threshold was changed.

A separate minimal-process check at the benchmark's **already-declared four-member
allocation** passed readiness in 2.156 s, one-CPU member sampling and kill-on-close.
It observed two distinct owned members: the virtual-environment launcher and actual
Python worker. That is relevant to the single-member tests, but does not establish
the cause of every full-suite stall or replace those failed tests. The model
runner's existing handshake, membership/affinity sampling and fail-closed limits
remain authoritative for its actual execution. Ruff and documentation checks passed.

Both supplemental CSVs were actually generated and verified to contain 72 blank
annotation rows each, with the expected packet pin and no reviewer IDs, labels,
spans or rationales filled. Their SHA-256 values were each
`c7bbbeeb5d6187be4e80b49063bdbd40b1ab1a9eca20f668e872bd7108d6f38d`.
Only those new blank forms and the public preparation receipt were read; no
private packet excerpt or existing human form was opened.
