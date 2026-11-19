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
