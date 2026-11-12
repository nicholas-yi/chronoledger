# AsOf

A point-in-time, provenance-reconciled research engine for US equities built from SEC filings.

**Status:** early development. No return results yet. See [docs/PREREGISTRATION.md](docs/PREREGISTRATION.md).

## Principles

- **Bitemporal by construction.** Every fact carries *valid time* (the period it describes) and *knowledge time* (when it became public, from EDGAR acceptance in UTC). Research code reads only through `as_of` queries.
- **Look-ahead is tested, not assumed away.** A time-travel invariance test checks that each research function gives identical results on the full store and on a store truncated at the as-of instant. Canary tests confirm that known-leaky code fails.
- **Pre-registered.** Hypotheses, thresholds, and sample splits are fixed before returns are examined.

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
