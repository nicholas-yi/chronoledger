# Referee report

**Gate: PASS** (every gating threat must be at level 4 or higher)

```
lookahead.store                    [#####] 5/5
lookahead.formation                [#####] 5/5
lookahead.reconcile                [####.] 4/5
lookahead.representation           [#####] 5/5
lookahead.representation.all_vintages [#....] 1/5  (known issue, non-gating)
extraction.hallucination           [#####] 5/5
extraction.quality                 [####.] 4/5
multiple_testing                   [#####] 5/5
survivorship                       [####.] 4/5
survivorship.distress_events [blocks H5b, H5c, H6b] [#....] 1/5  (known issue, non-gating)
price_level_leak                   [#####] 5/5
data_integrity                     [####.] 4/5
```

## lookahead.store: level 5

*Could any fact be read before EDGAR accepted the filing?*

- PASS (check) **invariance of as-of facts**: 10 random as-of instants on pilot.duckdb, 0 violations
- PASS (check) **invariance of revision detection**: revision detection at 6 instants, 0 violations
- PASS (mutation) **planted period-end leak is caught**: planted period-end look-ahead bug was caught

## lookahead.formation: level 5

*Could future returns or post-close events change current holdings?*

- PASS (check) **formation ignores future outcome availability**: formation holdings and weights are unchanged when a future return is hidden
- PASS (check) **formation neutralization excludes post-close information**: post-close filing/share/acquisition events do not change formation residuals
- PASS (mutation) **planted future-outcome selection is caught**: planted future-return availability filter changes holdings and is caught

## lookahead.reconcile: level 4

*Can a later amendment change what was believed earlier?*

- PASS (check) **invariance over random amendment chains**: 200 random amendment sequences, 0 invariance violations
- PASS (check) **retraction vs append-only ablation**: amendment retracts link; append-only baseline keeps the stale link

## lookahead.representation: level 5

*Could the text model have read text written after the filing?*

- PASS (check) **vintage strictly before filing date**: 2000 random acceptance times; 0 used a vintage not strictly before the filing date
- PASS (check) **neologism probe on in-use vintages (2022-2024)**: 0/4 pre-coinage probes on in-use vintages show context-specific knowledge; low power: post-coinage vintages also miss rare names (docs/FINDINGS.md)
- PASS (check) **leak-proof TF-IDF path is time-invariant (D3)**: 100 random corpora, 0 differences between full and as-of-truncated fits
- PASS (mutation) **same-day vintage is refused**: a filing on 2023-12-31 does not get the same-day 2023-12-31 vintage

## lookahead.representation.all_vintages: level 1 (known issue, non-gating)

*Do any ChronoBERT vintages, including unused ones, know terms coined after their cutoff?*

- FAIL (check) **neologism probe on all vintages**: 2/16 pre-coinage probes on all vintages show context-specific knowledge: COVID@20181231 rank 1, COVID@20191231 rank 1

## extraction.hallucination: level 5

*Does the extractor name companies the text never mentions?*

- PASS (check) **prior-knowledge hallucination rate < 2% (definition: deviation D2)**: prior-knowledge 0.005; all ungrounded outputs 0.050 (stricter reading) (bench_qwen3.5-4b_n300_s0.json)
- PASS (check) **entity-swap probe: famous real partner leaked < 2%**: famous-name leak rate = 0.000 (swap_qwen3.5-4b_n160_s0.json)
- PASS (mutation) **grounding rejects fabricated links**: fabricated partner and invented quote are both rejected

## extraction.quality: level 4

*Would H2/H3 be driven by extraction errors rather than economics?*

- PASS (check) **recall >= 0.80**: recall = 0.942 (bench_qwen3.5-4b_n300_s0.json)
- PASS (check) **precision >= 0.90**: precision = 0.956 (bench_qwen3.5-4b_n300_s0.json)

## multiple_testing: level 5

*Is the reported edge just the best of many tries?*

- PASS (check) **DSR rejects best-of-noise**: best of 500 noise strategies: naive PSR 1.00, DSR 0.60
- PASS (mutation) **holdout is single-use**: second holdout access was refused
- PASS (check) **no returns computed before deviation D1**: 2 commit(s) added return outputs, all after deviation-d1

## survivorship: level 4

*Are failed or acquired firms silently missing?*

- PASS (check) **coverage audit and D1 documented**: coverage audit and deviation D1 are documented
- PASS (check) **no returns computed before deviation D1**: 2 commit(s) added return outputs, all after deviation-d1

## survivorship.distress_events [blocks H5b, H5c, H6b]: level 1 (known issue, non-gating)

*Are distressed firms that later disappeared missing from event samples? (F2)*

- FAIL (check) **distress-event coverage parity >= 0.8**: coverage relative to all 10-K filers: NT 0.30, 4.02 0.74, 4.01 0.56 (need >= 0.8)

## price_level_leak: level 5

*Do price filters or market caps use future split information?*

- PASS (check) **as-traded reconstruction on AAPL 2020 split**: AAPL 2020 split: 499.23 / 129.04
- PASS (check) **as-traded close matches the historical record (real data)**: AAPL 2014-06-06 reconstruction: absolute reference discrepancy 0.0000 (need < 0.05)
- PASS (mutation) **$5 filter canary**: adjusted $1.00 vs as-traded $28.00

## data_integrity: level 4

*Are results driven by data errors rather than economics?*

- PASS (check) **long-short means are plausible (<= 5%/month)**: all variants within +/-5% per month
- PASS (check) **share-count typos are cleaned point-in-time**: a 1,000x share-count typo is rejected
- PASS (check) **unusable daily price ratios are excluded and counted**: four unusable daily ratios are excluded; the valid return and exclusion count remain
