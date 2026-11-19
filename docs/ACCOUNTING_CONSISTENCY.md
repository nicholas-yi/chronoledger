# Accounting consistency: a narrow deterministic oracle

[`asof.accounting`](../src/asof/accounting.py) reconciles one supplied weighted sum
over compatible, exact-decimal fact intervals. It is pure in-memory code: no filing
loader, taxonomy download, LLM, gold generation or trial logging.

## Why this addition

[XBRL Calculations 1.1, Recommendation 22 February 2023](https://www.xbrl.org/Specification/calculation-1.1/REC-2023-02-22/calculation-1.1-REC-2023-02-22.html)
addresses misleading calculation failures caused by rounding and duplicate facts.
Its [adoption guidance](https://www.xbrl.org/guidance/adopting-calc1-1/) also explains
important limits: incomplete facts or calculation trees can cause false warnings
or missed inconsistencies; the standard is not a cross-period/dimensional model.

We borrow the **interval-consistency principle**, not a claim of implementing an
XBRL-conformant processor. There is no taxonomy/arcrole parsing, OIM validation,
dimensional default resolution, tuple handling or full standard error-code behavior.
No conformance suite or real report has been evaluated.

## Input contract

`AccountingContext` requires:

- an explicit entity and canonical unit identifier, including currency where applicable;
- an instant (`period_start=None`) or ordered duration, with actual date endpoints;
- a canonical immutable set of distinct dimension-axis/member pairs.

Matching is exact. USD is not EUR, instant assets are not annual flows, and a segment
is not consolidated scope. A matching concept in a different context is not silently
substituted. Taxonomy concept IDs must be supplied consistently; name similarity
does not identify economic equivalence.

`ReportedFact` declares concept, context, source ID, exact displayed decimal,
optional displayed `decimals`, decimal `scale`, and rounding mode:

- Values must be `Decimal` or decimal strings; binary floats are rejected.
- `None` is nil/unavailable, not zero.
- `decimals=None` means exact; otherwise it is an integer in `[-18,18]`.
- `scale` is an integer in `[-18,18]`; canonical values are displayed values times
  `10**scale`. Currency/unit conversion is not inferred.
- `decimals` describes **displayed** precision. A source adapter must map actual
  Inline XBRL scale/accuracy metadata to this API explicitly; never copy fields
  without checking their semantics.
- Unexpected digits beyond declared precision fail rather than being silently rounded.
- Finite values/weights are limited to 128 digits and exponents in `[-100,100]`.
  Local precision 1,024 and a 256-term cap make this declared subset's arithmetic
  independent of the caller's ambient Decimal precision.

## Interval and duplicate semantics

With canonical center `v` and quantum `q=10**(scale-decimals)`:

| Representation | Admissible interval |
|---|---|
| Exact | `[v,v]` |
| Round-to-nearest | `[v-q/2,v+q/2]` |
| Positive truncation toward zero | `[v,v+q)` |
| Negative truncation toward zero | `(v-q,v]` |
| Zero truncation | `(-q,q)` |

Nearest ties are conservatively closed: a particular tie-breaking rule is not claimed.
This can accept a boundary that a stricter specified rounding convention would exclude.
Negative contribution weights reverse bounds **and** endpoint inclusion.

Compatible duplicate facts are reconciled by interval intersection; they are not
summed or overwritten by whichever source was read last. Disjoint duplicate intervals
report inconsistency. Repeating the same source ID for a concept/context is rejected.
Any required nil fact makes the check unavailable rather than supplying a number.
This conservative nil handling is a subset policy, not full XBRL duplicate semantics.

## Results mean existence, not truth

`reconcile` receives a target context, unique total concept and nonzero weighted
contribution terms. It returns:

- **consistent:** the total interval intersects the weighted contribution interval;
- **inconsistent:** intervals or compatible duplicate evidence conflict;
- **unavailable:** required context-compatible evidence is missing or nil.

For example, displayed `1.0 - 0.3` is not exactly `0.8`, but at one decimal place
the intervals admit a consistent set of underlying values. The demo exposes this
without changing any empirical number:

```powershell
uv run --no-sync asof demo
```

Expected accounting status: `consistent`. This is not a real-company example.

The oracle checks whether some values satisfy **one declared relationship**.
Multiple separately consistent equations need not have one jointly feasible solution;
there is no global constraint solver here. The relationship itself must be justified.
An inconsistency does not establish fraud or an extraction error; a consistent
output does not establish correct source, entity, period, accounting treatment or truth.

## Independent-review workflow

Reuse [annotation intake](../src/asof/research_intake.py) for source/evidence identity,
reviewer independence and explicit unresolved cases. The oracle can supply an
additional diagnostic on independently selected compatible facts; it must not
overwrite annotations, fill missing values, alter H1 labels or certify its own gold.

A future approved adapter must bind the normalized value, period role, currency,
unit/scale, scope and evidence spans to actual sources, and separately declare
precision/rounding metadata. No such real-data extraction, human review or standard
conformance was performed by adding this module.

[Invented tests](../tests/test_accounting.py) cover rounding false alarms, real
interval conflicts, negative weights/open endpoints, scale, entity/unit/period/
dimension mismatch, duplicate intersections/conflicts, nil, excess digits and
ambient Decimal precision. They are mathematical/software evidence only.
