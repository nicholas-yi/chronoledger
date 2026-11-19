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
