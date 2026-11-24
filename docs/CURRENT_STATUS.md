# Start here: current status

The short map of what is known, what is held and what can be run. **No tradable-edge claim is
supported.** Details live in [FINDINGS](FINDINGS.md), [DEVIATIONS](DEVIATIONS.md),
[DATA_AUDIT](DATA_AUDIT.md) and [FOCUSED_READER](FOCUSED_READER.md).

## Where the research stands

- **Filing times are verified.** The SEC header clock was established against the 5:30 p.m.
  Eastern filing-date rule, and **all 16,921** timing-sensitive H0 accessions qualified. Five MHLA
  filings had stored times 4-5 hours early;
  [D16](DEVIATIONS.md#d16-replace-h0-knowledge-times-with-qualified-acceptance-times) corrected
  them and reran H0, and no conclusion changed. The 262 timing-sensitive 2012-2018 H4/H6a filings
  were also audited, with no assignment changes.
- **H0 (Lazy Prices) shows no reliable premium after costs** on the development sample. The
  exploratory event-time neutralized panel (D17) points the wrong way.
- **Engine audit (2026-11-24):** five backtest defects (stale formation prices, split-basis share
  counts and spreads, last month's spread in trading costs, and event windows that skipped missing
  returns) were corrected under
  [D19](DEVIATIONS.md#d19-correct-five-engine-defects-found-by-the-2026-11-24-audit) and H0 was
  rerun; means moved by at most 0.25 percentage points a month and no conclusion changed.
- **Reproducibility:** the earlier F8 numerical gap is explained by the BLAS thread setting; H0
  and H4 reproduce exactly (D14, D15).
- **Monthly calibration fails, as a
  [permanent design limit](FINDINGS.md#f10-status-a-permanent-limit-of-this-design-2026-11-20).**
  With 17-18 independent months, textbook tests find effects that are not there. This is the only
  threat blocking the [referee](../results/REFEREE.md).
- **H5b, H5c and H6b are invalid** because of distress-specific survivorship (F2). Fixing it needs paid
  delisting-inclusive prices, which the owner declined on 2026-11-21.
- **H4/H6a confirmation moved to a
  [prospective holdout](DEVIATIONS.md#d18-move-h4-and-h6a-confirmatory-evaluation-to-a-prospective-holdout)**
  (D18): filings accepted 2026-11-22 to 2027-11-21, evaluated once, not before 2028-12-31 (H6a)
  and 2029-03-31 (H4).
- **Social sentiment (H7) is closed unregistered.** The VADER scorer failed qualification and the
  owner declined paid model or social-media access.

## The focused reader

The active measurement work is one
[evidence-linked metric reader with deterministic checks](FOCUSED_READER.md). The model judge is
nondefault, and its failed comparisons are retained. Headline results:

- The source-proved claim checks resolve the supported claim set **24/24**, and **37/37 policy
  controls** pass.
- On real 10-K MD&A text, the guards defer **2.1% / 4.7% / 9.8%** of revenue sentences
  (alone / ±1 / ±3 sentences) on fresh issuers. That is deferral, not accuracy.
- The rules-first pipeline v2 scored **30/30 with zero false supports** on a fresh 30-probe round.

All probes are invented or AI-authored, not human gold. **Human independent labels remain zero;
real-source accuracy is not established.** Twelve private review windows and two blank forms
are ready, but independent reviewers are unassigned; see the
[human review runbook](FOCUSED_READER.md#human-actions-still-required-source-review-runbook).

## What can be run

After the [locked installation](../README.md#run-it):

```powershell
uv run --no-sync asof demo
uv run --no-sync python scripts/check_repository.py
uv run --no-sync pytest -q
```

The demo is deterministic and invented. It needs no SEC User-Agent, data, models or network,
and writes nothing. Expected accounting status is `consistent`, signed areas are `-0.5` and `0.5`,
and the unknown-short lower bound is the string `-infinity`.

| Entrypoint | Status |
|---|---|
| `asof demo`, `scripts/check_repository.py`, `scripts/smoke_wheel.py` | Safe, offline; all run in CI |
| `asof ingest` | Network, cache and database operation; needs a valid development `--scope-file` |
| H0 and H5 study runners | Development evidence operations; every run is logged to the append-only ledger |
| `scripts/h4_fundamentals.py`, `scripts/h6_quiet.py` | **Held** for the D18 prospective holdout |
| Reader tools | Regression replay is offline; review preparation is a one-time, no-overwrite operation |

Every script is listed with its purpose in the [project index](project_index.json), and
[`check_repository.py`](../scripts/check_repository.py) fails CI if a script is unlisted or a
result file is unreferenced. Completed one-shot runs and superseded versions are at the tag
`archive-2026-11` ([ARCHIVE.md](ARCHIVE.md)); each result records the commit it ran from.

## Next substantive work

1. Obtain genuinely independent, outcome-blind labels for the reader and for H1 claim pairs.
2. Use deterministic accounting constraints as diagnostics, not surrogate human gold.
3. Only then assess incremental forecasts and net-of-cost decision value.
4. Evaluate H4/H6a once on the prospective holdout after its dates.

No new empirical run, hold release, model call, source purchase or return trial is authorized by
this page.
