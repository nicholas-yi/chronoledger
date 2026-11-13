"""Monthly portfolio backtest with point-in-time signals, sizes, filters, and trading costs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd

from asof.timeutil import close_time_utc


def abdi_ranaldo_spread(daily: pd.DataFrame) -> float:
    """Close-high-low effective spread estimate (Abdi & Ranaldo 2017) for one window.

    S^2 = 4 * mean[(c_t - eta_t) * (c_t - eta_{t+1})], with c the log close and eta the log
    mid-range. Negative estimates are set to zero.
    """
    d = daily.dropna(subset=["close", "high", "low"])
    if len(d) < 3:
        return float("nan")
    c = np.log(d["close"].to_numpy())
    eta = 0.5 * (np.log(d["high"].to_numpy()) + np.log(d["low"].to_numpy()))
    s2 = 4.0 * np.mean((c[:-1] - eta[:-1]) * (c[:-1] - eta[1:]))
    return float(np.sqrt(max(s2, 0.0)))


def monthly_panel(daily: pd.DataFrame) -> pd.DataFrame:
    """One row per (ticker, month): last trading day, as-traded close, total return, spread."""
    d = daily.sort_values(["ticker", "date"]).copy()
    d["month"] = pd.PeriodIndex(pd.to_datetime(d["date"]), freq="M")
    rows = []
    for (t, m), g in d.groupby(["ticker", "month"], sort=True):
        rows.append({"ticker": t, "month": m, "last_day": g["date"].iloc[-1],
                     "close": g["close"].iloc[-1], "adjclose": g["adjclose"].iloc[-1],
                     "spread": abdi_ranaldo_spread(g)})
    p = pd.DataFrame(rows).sort_values(["ticker", "month"])
    p["ret_next"] = p.groupby("ticker")["adjclose"].shift(-1) / p["adjclose"] - 1.0
    nxt = p.groupby("ticker")["month"].shift(-1)
    p.loc[nxt != p["month"] + 1, "ret_next"] = np.nan  # gaps are not silently bridged
    p.loc[p["ret_next"] <= -1.0, "ret_next"] = np.nan  # a loss beyond -100% is a data error
    return p


def latest_as_of(facts: pd.DataFrame, key: str, as_of: datetime, value_cols: list[str]) -> pd.DataFrame:
    """Latest row per ``key`` with knowledge_time <= as_of."""
    known = facts[facts["knowledge_time"] <= as_of]
    if known.empty:
        return pd.DataFrame(columns=[key, *value_cols])
    idx = known.sort_values("knowledge_time").groupby(key).tail(1)
    return idx[[key, *value_cols]]


def clean_shares(shares: pd.DataFrame, jump: float = 10.0, confirm_tol: float = 0.2) -> pd.DataFrame:
    """Point-in-time cleaning of reported shares outstanding.

    A value more than ``jump``x away from the last accepted value is held as pending and only takes
    effect when a later filing confirms it (within ``confirm_tol``), as of that later filing's
    knowledge time. This removes 1,000x tagging typos while still accepting genuine reverse
    splits, and never uses information before it was public.
    """
    out = []
    for cik, g in shares.dropna(subset=["val"]).sort_values("knowledge_time").groupby("cik"):
        accepted = pending = None
        for r in g.itertuples():
            v = float(r.val)
            if v <= 0:
                continue
            if accepted is None or 1 / jump <= v / accepted <= jump:
                accepted, pending = v, None
                out.append((cik, v, r.knowledge_time))
            elif pending is not None and abs(v / pending - 1) <= confirm_tol:
                accepted, pending = v, None
                out.append((cik, v, r.knowledge_time))
            else:
                pending = v
    return pd.DataFrame(out, columns=["cik", "val", "knowledge_time"])


@dataclass(frozen=True)
class Config:
    signal: str = "cos_full"
    n_quantiles: int = 5
    weighting: str = "value"  # or "equal"
    min_price: float = 5.0
    size_pct: str = "p20"
    max_signal_age_days: int = 365
    long_high: bool = True  # long high-similarity (non-changers), short low-similarity


def form_portfolios(
    month: pd.Period,
    signals: pd.DataFrame,
    shares: pd.DataFrame,
    panel_m: pd.DataFrame,
    breakpoint_musd: float,
    cfg: Config,
) -> pd.DataFrame:
    """Assign quantiles at the close of the month's last trading day using only known data."""
    if panel_m.empty:
        return pd.DataFrame()
    formation_day: date = max(panel_m["last_day"])
    as_of = close_time_utc(formation_day)
    sig = signals[(signals["knowledge_time"] < as_of)
                  & (signals["knowledge_time"] >= as_of - pd.Timedelta(days=cfg.max_signal_age_days))]
    sig = sig.sort_values("knowledge_time").groupby("cik").tail(1)[["cik", cfg.signal]].dropna()
    sh = latest_as_of(shares, "cik", as_of, ["val"]).rename(columns={"val": "shares"})
    df = panel_m.merge(sig, on="cik").merge(sh, on="cik")
    df["mcap_musd"] = df["shares"] * df["close"] / 1e6
    df = df[(df["close"] >= cfg.min_price) & (df["mcap_musd"] >= breakpoint_musd)].dropna(subset=["ret_next"])
    if len(df) < cfg.n_quantiles * 5:
        return pd.DataFrame()
    df["q"] = pd.qcut(df[cfg.signal].rank(method="first"), cfg.n_quantiles, labels=False) + 1
    w = df["mcap_musd"] if cfg.weighting == "value" else pd.Series(1.0, index=df.index)
    df["w"] = w / df.groupby("q")["mcap_musd" if cfg.weighting == "value" else "q"].transform(
        "sum" if cfg.weighting == "value" else "count")
    df["month"] = month
    return df


def long_short(port: pd.DataFrame, prev: pd.DataFrame | None, cfg: Config) -> dict:
    """Gross and net long-short return for one month; costs from spread-weighted turnover."""
    top, bot = port["q"].max(), port["q"].min()
    long_q, short_q = (top, bot) if cfg.long_high else (bot, top)
    out = {}
    for leg, q in (("long", long_q), ("short", short_q)):
        cur = port[port["q"] == q].set_index("ticker")
        gross = float((cur["w"] * cur["ret_next"]).sum())
        if prev is None or prev.empty:
            turnover_cost = float((cur["w"] * cur["spread"].fillna(0) / 2).sum())
        else:
            p = prev[prev["q"] == q].set_index("ticker")
            drifted = p["w"] * (1 + p["ret_next"])
            drifted = drifted / drifted.sum() if drifted.sum() else drifted
            both = pd.concat([cur["w"].rename("new"), drifted.rename("old")], axis=1).fillna(0.0)
            spread = pd.concat([cur["spread"], p["spread"]]).groupby(level=0).last().reindex(both.index).fillna(0.0)
            turnover_cost = float(((both["new"] - both["old"]).abs() * spread / 2).sum())
        out[f"{leg}_gross"] = gross
        out[f"{leg}_cost"] = turnover_cost
        out[f"{leg}_n"] = len(cur)
    out["ls_gross"] = out["long_gross"] - out["short_gross"]
    out["ls_net"] = out["ls_gross"] - out["long_cost"] - out["short_cost"]
    return out
