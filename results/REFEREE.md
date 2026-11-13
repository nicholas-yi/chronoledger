# Referee report

**Gate: BLOCKED** (every threat must be at level 4 or higher)

```
lookahead.store              [#####] 5/5
lookahead.reconcile          [####.] 4/5
lookahead.representation     [##...] 2/5
extraction.hallucination     [#####] 5/5
extraction.quality           [####.] 4/5
multiple_testing             [#####] 5/5
survivorship                 [####.] 4/5
price_level_leak             [##...] 2/5
```

## lookahead.store — level 5

*Could any fact be read before EDGAR accepted the filing?*

- PASS (check) **invariance of as-of facts**: 10 random as-of instants on pilot.duckdb, 0 violations
- PASS (check) **invariance of revision detection**: revision detection at 6 instants, 0 violations
- PASS (mutation) **planted period-end leak is caught**: planted period-end look-ahead bug was caught

## lookahead.reconcile — level 4

*Can a later amendment change what was believed earlier?*

- PASS (check) **invariance over random amendment chains**: 200 random amendment sequences, 0 invariance violations
- PASS (check) **retraction vs append-only ablation**: amendment retracts link; append-only baseline keeps the stale link

## lookahead.representation — level 2

*Could the text model have read text written after the filing?*

- PASS (check) **vintage strictly before filing date**: 2000 random acceptance times; 0 used a vintage not strictly before the filing date
- PASS (mutation) **same-day vintage is refused**: a filing on 2023-12-31 does not get the same-day 2023-12-31 vintage

## extraction.hallucination — level 5

*Does the extractor name companies the text never mentions?*

- PASS (check) **prior-knowledge hallucination rate < 2% (definition: deviation D2)**: prior-knowledge 0.005; all ungrounded outputs 0.050 (stricter reading) (bench_qwen3.5-4b_n300_s0.json)
- PASS (check) **entity-swap probe: famous real partner leaked < 2%**: famous-name leak rate = 0.000 (swap_qwen3.5-4b_n160_s0.json)
- PASS (mutation) **grounding rejects fabricated links**: fabricated partner and invented quote are both rejected

## extraction.quality — level 4

*Would H2/H3 be driven by extraction errors rather than economics?*

- PASS (check) **recall >= 0.80**: recall = 0.942 (bench_qwen3.5-4b_n300_s0.json)
- PASS (check) **precision >= 0.90**: precision = 0.956 (bench_qwen3.5-4b_n300_s0.json)

## multiple_testing — level 5

*Is the reported edge just the best of many tries?*

- PASS (check) **DSR rejects best-of-noise**: best of 500 noise strategies: naive PSR 1.00, DSR 0.60
- PASS (mutation) **holdout is single-use**: second holdout access was refused
- PASS (check) **no returns computed before deviation D1**: no return outputs exist yet

## survivorship — level 4

*Are failed or acquired firms silently missing?*

- PASS (check) **coverage audit and D1 documented**: coverage audit and deviation D1 are documented
- PASS (check) **no returns computed before deviation D1**: no return outputs exist yet

## price_level_leak — level 2

*Do price filters or market caps use future split information?*

- PASS (check) **as-traded reconstruction on AAPL 2020 split**: AAPL 2020 split: 499.23 / 129.04
- PASS (mutation) **$5 filter canary**: adjusted $1.00 vs as-traded $28.00
