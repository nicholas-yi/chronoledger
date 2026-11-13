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
    idx = known.sort_values("knowledge_time", kind="stable").groupby(key).tail(1)
    return idx[[key, *value_cols]]


def values_as_of(
    queries: pd.DataFrame,
    facts: pd.DataFrame,
    value_cols: list[str],
    *,
    allow_exact_matches: bool = True,
) -> pd.DataFrame:
    """Batch latest facts for (cik, as_of) queries, preserving query order and index."""
    known = facts.dropna(subset=["knowledge_time"])[["cik", "knowledge_time", *value_cols]]
    if queries.empty or known.empty:
        return queries.assign(**{c: known[c].iloc[:0].reindex(queries.index) for c in value_cols})
    known = known.sort_values("knowledge_time", kind="stable").rename(columns={"knowledge_time": "_known_at"})
    left = queries.assign(_query_order=np.arange(len(queries))).sort_values("as_of")
    out = pd.merge_asof(
        left, known, by="cik", left_on="as_of", right_on="_known_at",
        direction="backward", allow_exact_matches=allow_exact_matches,
    ).sort_values("_query_order").drop(columns=["_query_order", "_known_at"])
    out.index = queries.index
    return out


def formation_snapshots(
    signals: pd.DataFrame,
    shares: pd.DataFrame,
    panel: pd.DataFrame,
    max_signal_age_days: int = 365,
) -> dict[pd.Period, pd.DataFrame]:
    """Precompute formation data once for variants using the same latest-filing rule."""
    if panel.empty:
        return {}
    queries = panel.copy()
    closes = panel.groupby("month")["last_day"].max().map(close_time_utc)
    queries["as_of"] = queries["month"].map(closes)
    queries = values_as_of(queries, shares.rename(columns={"val": "shares"}), ["shares"])
    columns = [c for c in signals if c not in panel.columns and c != "knowledge_time"]
    facts = signals.assign(_signal_time=signals["knowledge_time"])
    queries = values_as_of(
        queries, facts, [*columns, "_signal_time"],
        allow_exact_matches=False,
    )
    age = queries["as_of"] - queries["_signal_time"]
    queries = queries[age <= pd.Timedelta(days=max_signal_age_days)]
    return {m: g.drop(columns=["as_of", "_signal_time"]) for m, g in queries.groupby("month")}


def clean_shares(shares: pd.DataFrame, jump: float = 10.0, confirm_tol: float = 0.2) -> pd.DataFrame:
    """Point-in-time cleaning of reported shares outstanding.

    A value more than ``jump``x away from the last accepted value is held as pending and only takes
    effect when a later filing confirms it (within ``confirm_tol``), as of that later filing's
    knowledge time. This removes 1,000x tagging typos while still accepting genuine reverse
    splits, and never uses information before it was public.
    """
    out = []
    order = ["knowledge_time", *[c for c in ("end", "accn") if c in shares]]
    ordered = shares.dropna(subset=["val"]).sort_values(order, kind="stable")
    ordered = ordered.drop_duplicates(["cik", "knowledge_time"], keep="last")
    for cik, g in ordered.groupby("cik"):
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
    *,
    snapshot: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Assign quantiles at the close of the month's last trading day using only known data."""
    if panel_m.empty:
        return pd.DataFrame()
    if snapshot is None:
        formation_day: date = max(panel_m["last_day"])
        as_of = close_time_utc(formation_day)
        sig = signals[(signals["knowledge_time"] < as_of)
                      & (signals["knowledge_time"] >= as_of - pd.Timedelta(days=cfg.max_signal_age_days))]
        sig = sig.sort_values("knowledge_time", kind="stable").groupby("cik").tail(1)[["cik", cfg.signal]].dropna()
        sh = latest_as_of(shares, "cik", as_of, ["val"]).rename(columns={"val": "shares"})
        df = panel_m.merge(sig, on="cik").merge(sh, on="cik")
    else:
        df = snapshot[[*panel_m.columns, cfg.signal, "shares"]].dropna(
            subset=[cfg.signal, "shares"]).reset_index(drop=True)
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
            total = drifted.sum()
            drifted = drifted / total if total else drifted
            new, old = cur["w"].align(drifted, join="outer", fill_value=0.0)
            spread = p["spread"].combine_first(cur["spread"]).reindex(new.index).fillna(0.0)
            turnover_cost = float(((new - old).abs() * spread / 2).sum())
        out[f"{leg}_gross"] = gross
        out[f"{leg}_cost"] = turnover_cost
        out[f"{leg}_n"] = len(cur)
    out["ls_gross"] = out["long_gross"] - out["short_gross"]
    out["ls_net"] = out["ls_gross"] - out["long_cost"] - out["short_cost"]
    return out
