# ChronoLedger

**A research engine that can't see the future.** ChronoLedger turns SEC filings into a point-in-time,
provenance-tracked record of public companies, then tests whether filing-derived signals predict
returns, with look-ahead bias ruled out by tests rather than by assumption.

**Status:** early development. No return results yet. See [docs/PREREGISTRATION.md](docs/PREREGISTRATION.md),
[docs/DEVIATIONS.md](docs/DEVIATIONS.md), and [docs/DATA_AUDIT.md](docs/DATA_AUDIT.md).

The Python package is named `asof`, after the `as_of` queries everything is built on.

## Principles

- **Bitemporal by construction.** Every fact carries *valid time* (the period it describes) and *knowledge time* (when it became public, from EDGAR acceptance in UTC). Research code reads only through `as_of` queries.
- **Look-ahead is tested, not assumed away.** A time-travel invariance test checks that each research function gives identical results on the full store and on a store truncated at the as-of instant. Canary tests confirm that known-leaky code fails.
- **Pre-registered.** Hypotheses, thresholds, and sample splits are fixed and git-tagged before returns are examined. Deviations are logged with a timestamp and tag.
- **Every trial counts.** An append-only trial ledger feeds the Deflated Sharpe Ratio and probability-of-overfitting estimates, and the holdout can be opened only once.
- **As-traded prices.** Vendor prices adjusted for later splits are converted back to the prices that actually traded, so price filters and market caps don't leak future corporate actions.

## Verified so far

- EDGAR `acceptanceDateTime` is true UTC, confirmed against the US/Eastern timestamps in filing headers in both EST and EDT.
- On 5 large filers (16,070 filings, 151,979 XBRL facts), 100% of facts resolved to an exact acceptance timestamp, with 0 invariance violations across randomized as-of checks.
- The 10-K section parser finds Items 1, 1A, and 7 in 30/30 sampled real filings (2012–2026) and skips tables of contents.
- Free-price survivorship coverage was audited by public float; see `docs/DATA_AUDIT.md`.

## Setup

```bash
uv venv && uv pip install -e ".[dev]"
export ASOF_USER_AGENT="Your Name your.email@example.com"   # required by SEC EDGAR
pytest
```

Raw data and caches are written to `data/` and never committed.

## Data sources and licenses

- SEC EDGAR filings and XBRL APIs: public records.
- Prices: free sources for personal research only. **Raw prices are never redistributed; only derived statistics are published.**
- Factors: Kenneth French Data Library, which is linked and cited but not re-hosted.

## License

MIT for code.
