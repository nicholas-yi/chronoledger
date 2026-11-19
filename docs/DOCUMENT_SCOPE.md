# D13 document-reading guard

The shared [document scope check](../src/asof/document_scope.py) is required before
financial-document bodies, derived report text or document-byte fingerprints are read.
It implements the prospective correction in [D13](DEVIATIONS.md#d13-exploratory-kpi-disclosure-screen-crossed-reserved-calendars);
it does not repair historical exposure or release any reserved period.

## Date contract

Every document declares acceptance, knowledge and report-period-end dates, plus the same
information for **every used context**. Missing, empty, unparseable or naive timestamp
metadata fail closed. Report-year IDs alone are insufficient. ISO dates, timezone-aware
ISO timestamps and explicit English named-month dates are supported. Timestamp checks
use their UTC calendar date; this does not certify the SEC field's historical clock.

The conservative reading envelope is 2012-01-01 through 2018-12-31, inclusive, for **all**
date roles and context. This rejects:

- H4/H6 validation sources in 2019-2021;
- H4/H6(a) holdout sources in 2022-01-01 through 2025-06-30;
- the D1 return holdout beginning 2024-07-01;
- reserved follow-up sources, including H6's 365-day tail and late next-fiscal-year H4
  filings. No arbitrary finite H4 availability endpoint is treated as a release.

Dates outside that development envelope are not implicitly authorized merely because
they fall outside one named interval. There is no `holdout_opened` bypass.
Knowledge cannot precede acceptance by date, and period end cannot follow availability.
These are declared-date consistency checks, not permission authentication, source/vintage
certification, scientific acceptance or a host-level filesystem sandbox.

```python
from asof.document_scope import DocumentDates, require_eligible_documents

context = DocumentDates("2017-01-20", "2017-01-20", "2017-01-20")
source = DocumentDates(
    "2017-02-01T10:00:00Z", "2017-02-01T10:00:00Z", "December 31, 2016",
    contexts=(context,),
)
require_eligible_documents((source,))  # Before opening or fingerprinting its body.
```

For SEC bulk metadata, the ingestion's reported `acceptanceDateTime` is stored as
`knowledge_time`. A new caller can explicitly declare that value in both date roles;
the guard does not silently infer acceptance from an absent field. This mapping is not
independent verification that the original timestamp is true UTC.

## Enforced entrypoints

| Reader | Enforcement |
|---|---|
| Full SEC filing documents | `EdgarClient.filing_document(..., dates=...)` checks before cache/transport; covers the existing H0, feature, extraction-benchmark, calibration and identity-audit callers |
| Derived report features | `features.load(..., dates=...)` and `features.build(..., dates_by_accession=...)`; cached jobs are not exempt |
| KPI raw cache/fingerprints | `pin_filing`, `read_cached` and the runner's roster/context preflight use the shared check |
| Financial-QA benchmark assets | `verified_assets`, benchmark `fetch`, FinQA quarantine checks, REAL3 native pins and blind input loading refuse unknown dates before body/fingerprint access |
| Legacy TAT-QA comparison execution | An explicit pre-read check blocks its old unknown-date source path |
| API companyfacts and ingestion | `EdgarClient.companyfacts(..., scope=...)` and `asof ingest --scope-file` use the shared bulk fact-date/filing-date policy; missing scope refuses before fetch or CLI resource creation |

The API/ZIP fact filter constrains returned records, not raw response/member bytes.
Both are decoded in memory before filtering. The CLI also filters returned submission
metadata using period, filing and acceptance dates with omission diagnostics.
Unknown dates are omitted, not converted into zero or implicitly authorized.
The general submissions/transport utilities are not universally date-scoped.
Independent H4/H6 hard holds are not lifted by a valid dataset window.

Legacy runners which lack complete document-date manifests now stop instead of assuming
that a price cutoff or a document's printed year clears the whole project. This is an
intentional access restriction, not a change to any hypothesis, sign, outcome, window,
threshold or frozen historical result. No legacy job was rerun to exercise the guard.

Pure in-memory parsers/calculators and invented fixtures do not open empirical source
files. Metadata-only inventory and nonfinancial SEC-manual review are separate from
issuer-document study reads. New runners must use the guarded entrypoints; arbitrary
direct filesystem access is not sandboxed by this module.

## Verification and development-cache inventory

[Guard tests](../tests/test_document_scope.py) cover each date role at development,
validation, holdout and follow-up boundaries; unknown dates; UTC date crossings; named
months; and used context. [Entrypoint tests](../tests/test_document_scope_entrypoints.py)
verify rejection before source/client/cache access and a metadata-only inventory using
invented files. Existing HTML-comment and named-month/ISO parser regressions also remain.

The [development-cache counter](../scripts/count_kpi_development_cache.py) projects only
filing metadata, checks the shared guard and uses file-existence checks, not decompression
or cache hashing. It counts one latest eligible annual triple per issuer, with 330-400-day
period gaps and eligible used context. Fewer than 30 eligible issuers means stop: no download,
new roster, model, body screen, return trial or ledger row. Only if sufficient sources exist
may a separately frozen development-only roster precede a bounded new execution.
