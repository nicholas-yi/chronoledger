# H7: social-media sentiment (design note, not registered)

**Status (2026-11-21):** the code is built and tested offline, but no X data has been
fetched and no hypothesis is registered. Two things block a test: a finance-qualified
sentiment scorer, and an owner-approved X budget with the owner's own API token.

## Why this is a separate hypothesis

Social sentiment does not fix the monthly calibration problem
([F10](FINDINGS.md#f10-status-a-permanent-limit-of-this-design-2026-11-20)). That problem
comes from having only 17-18 independent months for the H0 text-change test, and a
second signal adds no months. H7 is a **new, short-horizon** question with its own trial
family and its own threshold.

The published evidence points to predictability over hours to a few days, not months:

- [Renault 2017](https://www.sciencedirect.com/science/article/pii/S0378426617301589):
  intraday only.
- [Lachanski & Pav 2017](https://econjwatch.org/file_download/1037/LachanskiPavSept2017.pdf):
  the famous Bollen et al. result does not replicate.
- [Chen et al. 2014](https://econpapers.repec.org/RePEc:oup:rfinst:v:27:y:2014:i:5:p:1367-1403.)
  find longer horizons only for long-form articles.

A daily test has about 390 trading days in the development window, so unlike the monthly
H0 test it can be calibrated.

## Data: X API (owner decision required)

- **Pricing:** pay-per-use, about $0.005 per post read; full-archive search is available
  ([X pricing](https://docs.x.com/x-api/getting-started/pricing),
  [search](https://docs.x.com/x-api/posts/search/introduction.md)). A million posts costs
  about $5,000.
- **Terms:**
  - Scraping is prohibited ([ToS](https://x.com/tos)).
  - Stored posts must be deleted or updated when they change on X
    ([Developer Policy](https://docs.x.com/developer-terms/policy.md)).
  - Aggregate analysis without personal identifiers is allowed.

  So the pipeline keeps only post IDs, creation times and scores. Text is scored in memory
  and discarded, and a deletion request can remove an ID.
- **Unavoidable point-in-time gaps:** posts deleted before collection are missing, edits
  return the latest version, and bots and promoters are mixed in. The price universe is
  current-ticker (the F2 limit), so returns are survivorship-biased.

[`XArchiveClient`](../src/asof/social.py) refuses to start unless the owner sets
`ASOF_X_BEARER_TOKEN` and a positive `ASOF_X_BUDGET_USD`. It refuses any page that would
exceed the budget, and it logs every request with the cumulative spend. No request has
been made.

## Scorer qualification (failed for VADER)

The scorer must be fixed in advance, must not have learned from text written after the
posts it scores, and must beat a trivial baseline on human-labelled finance text.

| Scorer | Data | Accuracy | Majority baseline | Macro-F1 | Verdict |
|---|---|---:|---:|---:|---|
| VADER 3.3.2 (MIT, 2014 lexicon) | Financial PhraseBank, all annotators agree (2,264) | 57.1% | 61.4% | 0.49 | **Not qualified** |
| VADER 3.3.2 | PhraseBank, at least half agree (4,846) | 54.3% | 59.4% | 0.49 | **Not qualified** |

Source: [scorer qualification receipt](../results/sentiment_scorer_validation.json).
VADER misses finance vocabulary: "raising guidance", for example, scores as neutral.
The next candidate needs the `embed` dependencies, and must be qualified on labelled text
it was **not** trained on. For example, a PhraseBank-trained model should be tested on a
different labelled finance set.

## Proposed sequence (each step needs the owner)

1. Choose and qualify a finance scorer offline (no cost).
2. **Pilot, about $25 (5,000 posts):** cashtag posts for a stratified sample of 50 H0
   universe firms over one development month. This measures posts per firm-day, the
   share of firm-days with enough posts, and the full-design cost. It is not a return test.
3. Register H7 before the full pull: the daily signal is abnormal sentiment (posts in the
   24 hours ending 15 minutes before the close, minus the firm's own trailing mean),
   tested against next-day returns as a daily long-short, development 2023-01 to
   2024-07 only, with |t| >= 3 and the D12 robust checks.
4. Full pull within a fixed budget cap, one development run, results reported whatever
   they show.
