# Data audit: survivorship coverage of free price data

Generated from EDGAR full-index files (2011–2026), SEC's current CIK-ticker map, and the XBRL
frames API (`dei:EntityPublicFloat`). Having a current ticker is an upper bound on whether a free
source has the firm's price history. Firms acquired, merged, taken private, or failed since then
are usually missing.

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
- **Decision:** no return-based test of H0–H3 will run on free prices for the development period. Components that don't need prices continue: extraction, the reconciliation graph, the synthetic benchmark, and the representation pipeline. Return tests wait for a survivorship-free price source, such as one with explicit coverage of delisted securities.
