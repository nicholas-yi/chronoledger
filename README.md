# ChronoLedger

**A point-in-time research engine with an executable self-audit.** ChronoLedger turns SEC filings into a point-in-time,
provenance-tracked record of public companies, then tests whether filing-derived signals predict
returns, with explicit time-travel tests for look-ahead bias rather than an assumption of safety.

**Status: DEVELOPMENT ONLY (2026-11-13).** Public inputs were rebuilt and the development runs
completed. No supported hypothesis or tradable edge is claimed. All four monthly variants,
including three missing-return assumptions each, ran in **61.1 seconds wall-clock** with validated
prepared inputs; building that input snapshot separately took 155.0 seconds.
No holdout test has been executed. Historical H4 preprocessing
contaminated its isolation ([F4](docs/FINDINGS.md#f4-h4-winsorization-used-observations-outside-development));
the correction does not restore an untouched sample. Historical estimates are not fresh-data
results; [F2-F6](docs/FINDINGS.md) document survivorship and point-in-time defects, including
corrections [D6-D9](docs/DEVIATIONS.md). See [pre-registration](docs/PREREGISTRATION.md) and
[data audit / rebuild provenance](docs/DATA_AUDIT.md).

The Python package is named `asof`, after the `as_of` queries everything is built on.

## Principles

- **Bitemporal research facts.** Temporal filing facts carry *valid time* (the period described) and *knowledge time* (EDGAR acceptance in UTC). Time-filtered queries protect these records; current-ticker and current-SIC proxies remain explicit limitations, not historical point-in-time guarantees.
- **Look-ahead is tested, not assumed away.** Time-travel checks compare full and as-of-truncated inputs, with canaries for known leaks. Passing checks are evidence for the tested paths, not a universal proof.
- **Pre-registered.** Hypotheses, thresholds, and sample splits are fixed and git-tagged before returns are examined. Deviations are logged with a timestamp and tag.
- **Every trial counts.** An append-only trial ledger feeds the Deflated Sharpe Ratio and probability-of-overfitting estimates, and the holdout can be opened only once.
- **As-traded prices.** Vendor prices adjusted for later splits are converted back to the prices that actually traded, so price filters and market caps don't leak future corporate actions.

## Verified so far

- A newly built five-issuer pilot has **132,527 facts**, all matched to exact acceptance timestamps.
  Ten fact and six revision as-of checks found zero violations; the planted period-end leak was caught.
  This is a new fixture, not a byte-for-byte restoration of the original pilot.
- The rebuild processed 32,508 H0 filing features and 12,184 H4 annual filings with zero feature
  errors. A 100-firm [pinned legacy comparison](results/h0_optimization_equivalence.json) passed
  across all four variants and 17 formation months, within its documented D7/D8 comparison scope.
- The local processed-price snapshot round-tripped **57,195 monthly rows and 14,433,060 daily
  returns** exactly. All 12 full-sample configurations then matched raw-preparation metrics exactly.
  The earlier 298.7-second timing miss remains in the [append-only ledger](results/trial_ledger.jsonl).
- There are 2,733 usable price histories among 2,753 **already current-ticker-selected** firms.
  That is not survivorship coverage. [F2](docs/FINDINGS.md#f2-distress-event-tests-are-invalid-under-a-current-ticker-universe)
  remains unresolved; [F3](docs/FINDINGS.md#f3-three-data-bugs-caught-by-an-implausible-backtest)
  records the original implausible-backtest failures.
- Local regression tests: **123 passed**. Selected Ruff `E4,E7,E9,F` checks pass; default Ruff
  retains 62 inherited findings versus 63 at the handoff, with no new findings.
  See [validation and rebuild provenance](docs/DATA_AUDIT.md).

Historical header cross-checks established that EDGAR acceptance timestamps are UTC, and the parser
found the requested sections in 30/30 real 10-Ks. Those original live-data checks were not repeated.

### Development results, not confirmatory findings

H0 signals are accepted in **2023-01-01 through 2024-06-30 UTC**; returns end by **2024-07-31**.
The expected long-short sign is positive: long low-change firms, short high-change firms.
Primary results are value-weighted and net of estimated costs.

| Cosine variant | Return months | Mean net / month | FF5+UMD alpha t |
|---|---:|---:|---:|
| `v1_10K_raw` | 17 | -0.805% | -0.45 |
| `v2_latest_raw` | 18 | +0.291% | +1.46 |
| `v2_latest_neutral` | 18 | -0.294% | -2.33 |
| `v2_10K_neutral` | 17 | -1.689% | -2.36 |

No positive-direction support is established. The zero, -30%, and -100% missing-return assumptions
coincide here because no held long/short leg lacks its next-month return; that does **not** repair
firms missing from the universe. Raw change event panels are descriptive; neutralized event panels
are **not evaluated** under D8. These neutralized cosine variants, historically logged as `H1n`,
are **not the claim-level H1 signal**. See the [full H0 output](results/returns_h0_development.json)
and [execution source](scripts/h0_backtest.py).

| Test | Development result | Interpretation |
|---|---|---|
| H4: text change and next-year fundamentals, 2012-2018 | All six absolute t values <= 1.23; primary neutralized-score -> dROA t = -1.20 | No support at the 3.0 bar in these conditional diagnostics |
| H6(a): quiet revision and a formal outcome within 365 days, 2012-2018 | Adjusted association +4.20 percentage points, t = 1.74; 22,745 filings, 499 quiet, 1,103 firms | Exactly reproduces the earlier estimate; below the 3.0 bar |
| H6(b): subsequent CAR(+1..+60), 2023-Jun 2024 | Pipeline diagnostic +4.58%, t = 1.77, 316 events | **INVALID under F2**, not a return finding |
| H5(a), historical; not rerun here | Friday-evening difference +0.97 percentage points, t = 2.01 | Opposite the expected sign; not a replication |
| H5(b)/(c), historical; not rerun here | **INVALID under F2** | Current-ticker distress selection prevents interpretation |

H6(a)'s observed formal-outcome rates are 17.84% versus 13.72%; the 4.02-only descriptive rates are
4.81% versus 1.82%. The broad outcome includes 10-K/A filings that may be Part III-only amendments.
H4 retains its no-support conclusion, but D6 changes its winsorized dROA mean and coefficients.
H4 and neutralized H0 also use current SIC as a fixed proxy, not verified historical classifications.
See [H4 output](results/h4_development.json), [H6 output](results/h6_development.json),
and [historical-versus-rebuilt reconciliation](docs/FINDINGS.md#development-rerun-reconciliation-2026-11-13).

### Relationship extraction (local Qwen 3.5, synthetic benchmark on real 10-K text)

**Historical artifacts, not model runs repeated in this continuation.**

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

**Historical calibration, not re-executed in this continuation.**

Centering ChronoBERT embeddings fixes their anisotropy. Similarity between unrelated risks drops from 0.971 to 0.045, and AUC on synthetic same-risk vs. different-risk pairs is 0.9999. See `results/change_calibration.json`.

### Executable referee: PASS is not scientific acceptance

The [executed report](results/REFEREE.md) has all **10 gating threats at level 4 or higher**.
Two known, non-gating issues remain at level 1: the unused 2018/2019 ChronoBERT vintages' COVID
knowledge, and distress-event coverage failure that blocks H5(b), H5(c), and H6(b).
The representation/extraction checks read recorded benchmark artifacts; no model was rerun.

A pass covers the defined checks, not all possible biases, historical SIC availability, scientific
approval, or holdout authorization. Project-level DSR/PBO results, formal claim-level H1, and the
neutralized event co-primary are not established by these runs. The current session-clock helper
uses the fixed 16:00 ET convention and CAR windows index valid observations; early-close and
calendar-gap handling must be qualified before execution or confirmatory event-study claims.
H4's year-cohort neutralization is retrospective, not claimed observable at each filing time.

## Setup

Windows PowerShell:

```powershell
uv venv --python 3.12
uv pip install -e ".[dev]"
$env:ASOF_USER_AGENT = "Your Name your.email@example.com"
.\.venv\Scripts\python.exe -m pytest -q
```

Use the project interpreter for every command. The `embed` extra is needed only for ChronoBERT,
not these development runs. Raw vendor data and processed price datasets stay under ignored `data/`.
Follow the [rebuild runbook](docs/DATA_AUDIT.md#data-rebuild-runbook), including the pilot fixture
and safe Windows process-pool invocation, before running the backtests and referee.
The `prices` stage creates the validated processed snapshot; after a processing/runtime change,
rebuild it with `python scripts/h0_data.py price_snapshot`. Missing or stale snapshots fail explicitly.

## Proposed next gates: approval required, not executed

1. **Delisted-price pilot.** Evaluate a personal-key source such as
   [Tiingo EOD](https://www.tiingo.com/documentation/end-of-day), subject to its current plan,
   quotas, licensing, and actual coverage. A free tier or historical prices alone do not guarantee
   historical identity mapping or terminal delisting payoffs. Start from all eligible EDGAR
   issuers, qualify ticker reuse/share classes/corporate actions, then rerun the F2 coverage
   contrast and predetermined development-only checks. No market-data API key was used and no
   paid data or compute was purchased here.
2. **Holdout readiness.** Resolve F2 where applicable, the current-SIC proxy, early-close session
   timing/calendar-gap handling, the event-time neutralization contract, outstanding preregistered inference outputs,
   and F4's historical H4 contamination. Review the ledger, freeze/tag code/config/data/windows,
   and obtain explicit owner approval. Do not silently reseal or relabel contaminated data.
3. **Timing, not authorization.** The October 2026 monthly formation needs returns through
   **2026-11-30**. Under the [scheduled NYSE calendar](https://www.nyse.com/trade/hours-calendars),
   a final late-October event anchored on 2026-11-02 needs its +60th session through
   **2027-01-29**. Recheck actual closures and data finalization before an early-February-2027
   review; valid-observation windows with gaps may extend later until that contract is fixed.
   This is not an automatic opening date. H4/H6(a) require separate label-readiness and
   isolation decisions. Audit July 2024 event-label overlap with the permitted development tail.

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
