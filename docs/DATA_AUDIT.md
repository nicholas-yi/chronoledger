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
