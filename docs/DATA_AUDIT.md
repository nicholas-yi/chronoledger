# Data audit: survivorship coverage of free price data

Generated from EDGAR full-index files (2011–2026), SEC's current CIK-ticker map, and the XBRL
frames API (`dei:EntityPublicFloat`). Having a current ticker is an upper bound on whether a free
source has the firm's price history. Firms acquired, merged, taken private, or failed since then
are usually missing.

Rebuild the quarterly index with `python scripts/master_index.py`. It starts in 2011 and
stops at the current UTC quarter, reusing the EDGAR client's per-URL cache on retries.
Quarters are streamed into `data/master_index_2011_<current year>.parquet`; a failed request
leaves any previous completed output unchanged. This index contains filing metadata, not
prices, and does not open a return holdout.

When `data/raw/bulk/submissions.zip` exists, the H0 `filings` stage reads missing
firms directly from it, including every form, historical page, and exact acceptance
time. It uses the individual submissions API only for firms absent from that archive.
This avoids re-downloading metadata already obtained from the same public source;
malformed requested archive members fail explicitly rather than silently dropping a firm.
Overlapping recent/history pages are deduplicated by accession at ingestion, retaining
the recent-page row first, as in the bulk metadata reader.

### Rebuild provenance and verification

The 2026-11-13 devbox rebuild is a new download, not a byte-for-byte restoration
of the handoff's local caches. Input fingerprints may differ. New H0 ledger entries
include a hash of `data/h0_market_inputs.json`, which fingerprints the guarded
price caches and cached French factor/breakpoint archives without publishing their
contents. H4 also fingerprints the entity metadata used for SIC controls; H6
fingerprints the companyfacts archive and its sample or universe.
New lineage also records Python and core runtime package versions. The historical
entries did not pin that environment, so differences from them must not be attributed
solely to new downloads: code corrections and runtime changes may also contribute.

Development runners append a ledger entry even if execution raises after an
evaluation starts. `execution_status` describes execution, not scientific validity;
in particular, a completed H6(b) diagnostic remains invalid under F2. Partial
metrics and the failing phase are retained where available; exceptions still
propagate and the run must not be presented as complete.

After rebuilding inputs, run `python scripts/benchmark_h0.py --firms 100` before
the full backtest. It checks numerical equivalence to the pinned handoff revision
on the same corrected shares (D7) and complete-return engineering subsample (D8),
logs the engineering configurations, and writes
`results/h0_optimization_equivalence.json`. Its timings cover the subsample
comparison only. The full backtest's `elapsed_seconds` includes loading and shared
preparation and is the measurement for the all-four-variants, 180-second target.
Neither benchmark success nor historical CI proves scientific acceptance.
The formation-time repair and the legacy filing-cohort comparison are deliberately
separate: the latter is not an event-time signal and is not used for production
neutralized portfolios. Production reports the 0%, -30%, and -100% missing-return
assumptions and missing-observation counts; these do not repair the missing-firm
selection documented in F2.

Profiling the rebuilt 2,753-ticker price cache found another preparation bottleneck:
the per-window spread loop took 63.0 seconds for 57,195 ticker-months, in addition
to 74.7 seconds loading prices. Spread aggregation is now batched with the same
adjacent-valid-quote formula and minimum of three quotes. An independent real-data
100-ticker comparison (2,069 ticker-months) matched the legacy window calculation
to `rtol=atol=1e-12` and reduced that aggregation from 2.43 seconds to 0.032 seconds.
These are component timings during acquisition, not an end-to-end performance claim.
The benchmark CLI repeats a pinned legacy monthly-panel comparison on its selected
firms and records that evidence separately.

The loader also handles a listing with no pre-cutoff quotes but later split events:
it returns an empty guarded history, rather than crashing on an empty NumPy index.
The rebuild produced 2,753 cache files and 2,733 nonempty daily histories; cache-file
count alone is not price coverage.

## Coverage among public-equity issuers, by public float

| Float year | $1M–50M | $50M–500M | >$500M |
|---|---|---|---|
| 2011 | 24% | 37% | 55% |
| 2012 | 26% | 37% | 57% |
| 2013 | 27% | 38% | 58% |
| 2014 | 30% | 40% | 59% |
| 2015 | 35% | 44% | 61% |
| 2016 | 40% | 46% | 66% |
| 2017 | 45% | 49% | 68% |
| 2018 | 48% | 53% | 71% |
| 2019 | 53% | 57% | 76% |
| 2020 | 56% | 61% | 78% |
| 2021 | 56% | 55% | 78% |
| 2022 | 64% | 62% | 84% |
| 2023 | 72% | 76% | 88% |
| 2024 | 84% | 85% | 92% |
| 2025 | 94% | 94% | 97% |

Issuer counts per bucket range from about 1,000 to 2,700 per year.

## Implications

- The pre-registered development period (2011–2018) would lose 30–45% of large issuers with free data. The missing firms aren't random: they include acquisition targets, which tend to earn takeover premiums, and failures, which tend to earn large losses. **The direction of the bias is unknown**, so delisting-return sensitivity bounds can't fully repair it.
- Validation (2019–2021) and holdout (2022–2026) coverage is higher but still incomplete before 2024.
- **Decision:** the original decision was to wait for a survivorship-free source. It was superseded by deviation D1: return tests run only on signals from 2023 onward, where coverage of large issuers is 88–97%, with delisting sensitivities. See `docs/DEVIATIONS.md`.

## Holdout hygiene disclosure

On 2026-11-12, before the price guard existed, AAPL's full daily price history was downloaded once to validate split handling. That file contained post-2024 prices. It was used only to confirm the as-traded close on 2014-06-06 and on 2020-08-28, then deleted. No returns were computed from it.

From then on, `asof.periods.price_end_allowed` refuses any price request past 2024-07-31 unless the holdout is explicitly opened, so holdout-period prices never reach disk.

## Price-request change (F3)

Yahoo adjusts *all* historical prices for every split up to today. A request that stopped at the development cutoff therefore returned prices already adjusted for later splits, but not the later split *events*. That made as-traded price reconstruction impossible for stocks that split afterward; for example, FFAI showed $1,200 when it traded at pennies.

From 2026-11-13, each request spans the full history. **Every quote and dividend after the cutoff is discarded in memory before caching**, and only split events (date and ratio) are kept. Those later split events are used solely to reverse the vendor's own adjustment. No post-cutoff price, return, or dividend is stored or used.

The devbox rebuild also exposed a metadata gap in that implementation:
Yahoo's `meta` object can contain a current price and current 52-week range even
when the quote arrays are truncated. The strip function now retains only
`exchangeTimezoneName` from metadata, which is all date reconstruction requires.
This correction was made before price acquisition began on this devbox. Historical
cache hygiene is not established by this fix; old price caches should be rebuilt
with the corrected code. No metadata price is used to calculate returns.
