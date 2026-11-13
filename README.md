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

### Relationship extraction (local Qwen 3.5, synthetic benchmark on real 10-K text)

Ground truth comes from construction: fictitious companies are injected into real filing text, with no human labels.

| | Qwen 3.5 4B (300 cases) | Qwen 3.5 9B (80 cases) | Gate |
|---|---|---|---|
| Recall | 0.942 | 0.835 | ≥ 0.80 |
| Precision | 0.956 | 0.981 | ≥ 0.90 |
| Prior-knowledge hallucination | 0.5% | 0.0% | < 2% |
| All ungrounded raw outputs | 5.0% | 0.8% | reported |
| Entity-swap probe: famous real partner leaked | 0/159 | 0/40 | < 2% |

Every accepted link is verified by deterministic quote grounding.

### Change detection

Centering ChronoBERT embeddings fixes their anisotropy. Similarity between unrelated risks drops from 0.971 to 0.045, and AUC on synthetic same-risk vs. different-risk pairs is 0.9999. See `results/change_calibration.json`.

### Socratic referee: gate BLOCKED

`python -m asof.referee` evaluates 8 threats with executable checks and mutation tests; see `results/REFEREE.md`.

- **7 of 8 threats are at level 4 or higher.**
- **Representation look-ahead is at level 1.** A neologism probe found context-specific "COVID" knowledge in the 2018 and 2019 ChronoBERT vintages; see [docs/FINDINGS.md](docs/FINDINGS.md).
- No return-based result will be reported until the gate passes.

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

## Provenance of ideas and code

All code in this repository was written from scratch for this project. It contains no code, data, or
unpublished material from any employer. Methods are implemented from public sources and cited
where used: SEC EDGAR documentation, peer-reviewed finance and statistics papers, and public arXiv
preprints (for example, the episode-provenance reconciliation idea described in arXiv:2609.34242).

## License

MIT for code.
