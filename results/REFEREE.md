# Referee report

**Gate: BLOCKED** (every gating threat must be at level 4 or higher)

This reports defined executable checks, not scientific acceptance or permission to open holdouts. Some checks read recorded model/extraction artifacts; passing does not mean those models were rerun.

```
time_authority                     [####.] 4/5
inference.calibration              [#....] 1/5
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

## time_authority: level 4

*Have the required filing clocks been historically qualified?*

- PASS (check) **qualified per-accession clocks, not conditional agreement**: Latest integrated audit: historically qualified UTC=16921 of 16921 required, unresolved=0; every required accession must qualify
- PASS (check) **recorded metadata evidence hashes remain intact**: 8 private metadata artifact hashes match; not clock authority
- PASS (check) **H0 knowledge times in use never precede their qualified time**: D16 inputs in use: 16921 qualified signals, 0 differ from their qualified time, 0 qualified accessions absent; unaudited rows are assignment-insensitive

## inference.calibration: level 1

*Does the registered monthly test have acceptable null size?*

- FAIL (check) **registered NW6 meets its recorded calibration adoption rule**: Recorded registered NW6 null-size evidence at T=17/18/28: {"17": {"status": "unreliable_at_this_geometry", "worst_95_upper_5percent": 0.39057733744216394}, "18": {"status": "unreliable_at_this_geometry", "worst_95_upper_5percent": 0.37996260652320607}, "28": {"status": "unreliable_at_this_geometry", "worst_95_upper_5percent": 0.24908182100081513}}; no method substitution, project-return test or new simulation performed
- PASS (check) **synthetic calibration harness completed**: Recorded synthetic harness completion; not scientific acceptance or a rerun

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
- PASS (check) **no returns computed before deviation D1**: 3 commit(s) added return outputs, all after deviation-d1

## survivorship: level 4

*Are failed or acquired firms silently missing?*

- PASS (check) **coverage audit and D1 documented**: coverage audit and deviation D1 are documented
- PASS (check) **no returns computed before deviation D1**: 3 commit(s) added return outputs, all after deviation-d1

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

## Run provenance

Generated UTC: `2026-11-24T19:31:42.144745+00:00`.

The holdout-seal mutation uses a temporary synthetic ledger, not the project holdout.

```json
{
  "git_commit": "0bf44e43a62aeffc74bef06b8204f49df0a98d42",
  "git_dirty": false,
  "inputs": {
    "data/pilot.duckdb": "8192692acd2d987ac4611d81cc40e2e4c0a9f9d722ceaf8e1ea796d9e90fc31c",
    "data/bulk_filings.parquet": "dc804237f3c77be81c19cf47cfcb1e60be65e916ca96bdbc874d6340b711f7a4",
    "data/h0_universe.parquet": "b1c0c856e9be9c1e3be1e3b647e40a75a8cdc184893262544234834119dee017",
    "data/h0_price_snapshot.json": "8e6e90669feebe78b5177d54bb2a0a718fe500c3c11f1262bc3eef0847ca0ab9",
    "results/returns_h0_development_d16.json": "6f6eaa6bde468dba1dc6ac7e94e2ae92d165bc5e5b6a814dbc8f1eb09560d6f9",
    "results/bench_qwen3.5-4b_n300_s0.json": "f0b1c7371fdaa8552bf4f2b6a633c0c686fdafd62182485512803eca2aecdd3d",
    "results/swap_qwen3.5-4b_n160_s0.json": "df99ef309ed2c70e4c4382ce7095751fbf7af4659ecca8e466bfdb0361d47428",
    "results/leakprobe_chronobert.json": "135bb0713aef6070525bbafb4654135042da1de0854910730c7999c59e6d1d3e",
    "docs/DATA_AUDIT.md": "e2dc704c4369db73f4b4df834b1dcb7c7d56fc66ef5dea4d38d080a5f10106ba",
    "docs/DEVIATIONS.md": "9d14f8ec912275fccc6fe1037c7dd2acb184f8e5b84047f7ad3dc61ec8aaa330",
    "data/raw/yahoo/AAPL_to20240731_v2.json.gz": "1445c9d8e507440deb1bcf8dbc2bfc00255da74ee183e8b535c4ac5a273623d3"
  },
  "input_status": {
    "data/pilot.duckdb": "present",
    "data/bulk_filings.parquet": "present",
    "data/h0_universe.parquet": "present",
    "data/h0_price_snapshot.json": "present",
    "results/returns_h0_development_d16.json": "present",
    "results/bench_qwen3.5-4b_n300_s0.json": "present",
    "results/swap_qwen3.5-4b_n160_s0.json": "present",
    "results/leakprobe_chronobert.json": "present",
    "docs/DATA_AUDIT.md": "present",
    "docs/DEVIATIONS.md": "present",
    "data/raw/yahoo/AAPL_to20240731_v2.json.gz": "present"
  },
  "missing_inputs": [],
  "environment": {
    "python": "3.12.10",
    "duckdb": "2.0.0",
    "pandas": "3.1.1",
    "pyarrow": "26.0.1",
    "httpx": "0.28.1",
    "numpy": "2.5.4",
    "scipy": "1.18.1",
    "statsmodels": "0.15.0",
    "lxml": "6.1.3"
  }
}
```
