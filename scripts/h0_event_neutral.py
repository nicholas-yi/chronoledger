"""D17: event-time neutralized H0 event panels on development data (exploratory).

Declared before execution (owner approval 2026-11-21, after earlier development results):
- Signal: change = 1 - cos_full on the D16-corrected H0 signals. For each variant (latest
  filing of either form; 10-K only), the event-time residual comes from
  ``asof.event_neutral.trailing_residuals``: OLS of change on log market cap, a prior-365-day
  8-K Item 2.01 flag and SIC2 dummies, fitted on that variant's filings accepted in the 365
  days before the event's 00:00 ET, with at least 200 reference filings and SIC2 levels of at
  least 5 (rare codes pooled; unseen levels unresolved).
- Controls are as of the acceptance time: shares known strictly before it, the previous
  month-end close, and M&A 8-Ks known strictly before it. SIC2 is the current bulk mapping (a
  disclosed limit shared with the monthly variants).
- Test: CAR +1..+60 (FF5+UMD, the existing engine) on the residual, for events accepted
  2023-01-01..2024-06-30, OLS with month-clustered errors, plus D12's wild cluster
  restricted bootstrap by month (Webb weights, seed 2026112101, 9,999 draws). Expected sign:
  negative. Registered bar: |t| >= 3.2 with the D12 robust check at 0.137%; here reported as
  exploratory development evidence only. Each variant is one logged trial.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta

import h0_backtest as h0
import numpy as np
import pandas as pd

from asof import ledger
from asof.backtest import values_as_of
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.event_neutral import trailing_residuals
from asof.events import CarEngine, event_panel
from asof.factors import ff5_umd_daily
from asof.periods import DEV_END, DEV_RETURN_CUTOFF, DEV_START
from asof.robust_inference import significance, wild_cluster_restricted
from asof.runtime import frozen_receipt, write_receipt
from asof.timeutil import first_tradable_close

SIGNALS = DATA_DIR / "h0_signals_d16.parquet"
RESULTS = PROJECT_ROOT / "results" / "h0_event_neutral_development.json"
SOURCES = ("scripts/h0_event_neutral.py", "src/asof/event_neutral.py", "scripts/h0_backtest.py")
SEED, DRAWS = 2026112101, 9999


def with_controls(signals: pd.DataFrame, shares: pd.DataFrame, panel: pd.DataFrame,
                  ent: pd.DataFrame, ma: pd.DataFrame) -> pd.DataFrame:
    q = signals.assign(as_of=signals["knowledge_time"])
    shares_known = values_as_of(q[["cik", "as_of"]], shares, ["val"], allow_exact_matches=False)
    month = signals["knowledge_time"].dt.tz_convert(None).dt.to_period("M") - 1
    close = pd.DataFrame({"cik": signals["cik"], "month": month}).merge(
        panel[["month", "cik", "close"]], on=["month", "cik"], how="left")["close"].to_numpy()
    mcap = shares_known["val"].to_numpy(float) * close
    recent = values_as_of(q[["cik", "as_of"]], ma.assign(ma_time=ma["knowledge_time"]), ["ma_time"],
                          allow_exact_matches=False)
    sic = signals[["cik"]].merge(ent, on="cik", how="left")["sic"]
    return signals.assign(
        change=1.0 - signals["cos_full"],
        log_mcap=np.log(np.where(mcap > 0, mcap, np.nan)),
        ma_flag=(recent["ma_time"] >= q["as_of"] - pd.Timedelta(days=365)).astype(float).to_numpy(),
        sic2=sic.astype("string").str[:2].where(sic.notna()).to_numpy())


def panel_test(events: pd.DataFrame, daily_ret, engine: CarEngine, uni: pd.DataFrame) -> tuple[dict, dict]:
    s = events.merge(uni[["cik", "ticker"]], on="cik").dropna(subset=["change_et"])
    rows = []
    for r in s.itertuples():
        if r.ticker not in daily_ret:
            continue
        day = first_tradable_close(r.knowledge_time.to_pydatetime(), engine.days)
        if day is not None:
            rows.append({"car": engine.car(r.ticker, daily_ret[r.ticker], day, horizon=60),
                         "x": r.change_et, "month": r.knowledge_time.strftime("%Y-%m")})
    c = pd.DataFrame(rows).dropna()
    p = event_panel(c, "car", "x", "month")
    wcr = wild_cluster_restricted(c["car"].to_numpy(), np.column_stack([np.ones(len(c)), c["x"].to_numpy()]),
                                  c["month"].to_numpy(), 1, seed=SEED, draws=DRAWS, cluster_axis="month")
    check = significance(wcr, 0.001374, direction=-1)
    return ({"coef": p.coef, "t": p.t_stat, "n_events": p.n_events, "clusters": p.n_clusters,
             "WCR_p": wcr.p_value, "WCR_status": wcr.status,
             "D12_robust_rejects_at_0.137pct_expected_sign": check.rejected,
             "D12_robust_status": check.reason,
             "registered_bar_met": bool(abs(p.t_stat) >= 3.2 and p.coef < 0 and check.rejected)},
            {"events_with_car": len(c)})


def main() -> None:
    if RESULTS.exists():
        raise RuntimeError("D17 already executed; preserve it")
    freeze = frozen_receipt(PROJECT_ROOT, SOURCES)
    uni, _, shares, ent, ma, panel, daily_ret = h0.load_inputs(SIGNALS)
    signals = pd.read_parquet(SIGNALS)
    factors = ff5_umd_daily()
    engine = CarEngine(factors[factors.index <= DEV_RETURN_CUTOFF])
    full = with_controls(signals, shares, panel, ent, ma)
    lo = datetime.combine(DEV_START, datetime.min.time(), tzinfo=UTC)
    hi = datetime.combine(DEV_END, datetime.max.time(), tzinfo=UTC)
    output = {}
    inputs = [p if p.name != "h0_signals.parquet" else SIGNALS for p in h0.INPUTS]
    for name, frame in (("latest", full), ("10K", full[full["form"] == "10-K"])):
        frame = frame.assign(change_et=trailing_residuals(frame, "change", window=timedelta(days=365)))
        dev = frame[frame["knowledge_time"].between(lo, hi)]
        config = {"variant": f"v2_{name}_event_time_neutral", "neutralization": "trailing365_ET_day_v1",
                  "test": "event_panel_car60", "controls": ["log_mcap", "ma_flag", "sic2"]}
        with ledger.development_trial("H1n", config, inputs=inputs) as metrics:
            result, extra = panel_test(dev, daily_ret, engine, uni)
            metrics.update(result)
        output[config["variant"]] = {
            **result, **extra, "development_events": len(dev),
            "events_with_residual": int(dev["change_et"].notna().sum()),
            "config_hash": ledger.config_hash(config)}
        print(name, json.dumps(output[config["variant"]], default=float), file=sys.stderr, flush=True)
    write_receipt(RESULTS, {
        "label": "D17 EXPLORATORY development evidence: registered after earlier development results were "
                 "seen; not confirmatory, not a tradable edge",
        **freeze, "declared_rule": __doc__.split("Declared before execution")[1].strip(),
        "results": output, "n_trials_H1n_after": ledger.n_trials("H1n"),
        "limits": "About 18 monthly clusters; F10 shows monthly clustering is unreliable at this length, so "
                  "the WCR bootstrap is the more relevant check. SIC2 uses current metadata.",
    })
    print(RESULTS.read_text())


if __name__ == "__main__":
    if any(os.environ.get(k) != "1" for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("set numerical library thread caps to 1")
    main()
