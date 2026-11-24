"""Monthly portfolio backtest with point-in-time signals, sizes, filters, and trading costs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd

from asof.prices import clean_price_returns
from asof.timeutil import close_time_utc


def _split_consistent_quotes(d: pd.DataFrame) -> pd.DataFrame:
    """Close/high/low on one split basis, so a split is not mistaken for a price move."""
    if "close_split_adj" not in d:
        return d[["close", "high", "low"]]
    scale = d["close_split_adj"] / d["close"]
    return pd.DataFrame({"close": d["close_split_adj"], "high": d["high"] * scale,
                         "low": d["low"] * scale}, index=d.index)


def abdi_ranaldo_spread(daily: pd.DataFrame) -> float:
    """Close-high-low effective spread estimate (Abdi & Ranaldo 2017) for one window.

    S^2 = 4 * mean[(c_t - eta_t) * (c_t - eta_{t+1})], with c the log close and eta the log
    mid-range. Negative estimates are set to zero. Prices are put on one split basis first.
    """
    d = _split_consistent_quotes(daily).dropna(subset=["close", "high", "low"])
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
    d = d.dropna(subset=["ticker", "month"]).reset_index(drop=True)
    groups = d.groupby(["ticker", "month"], sort=True)
    if not groups.ngroups:
        raise ValueError("monthly_panel requires dated price observations")
    codes = groups.ngroup().to_numpy()
    basis = _split_consistent_quotes(d)
    valid = basis.notna().all(axis=1).to_numpy()
    quote_codes = codes[valid]
    counts = np.bincount(quote_codes, minlength=groups.ngroups)
    usable = counts[quote_codes] >= 3
    quote_codes = quote_codes[usable]
    quotes = basis.loc[valid, ["close", "high", "low"]].to_numpy(dtype=float)[usable]
    c = np.log(quotes[:, 0])
    eta = 0.5 * (np.log(quotes[:, 1]) + np.log(quotes[:, 2]))
    same = quote_codes[:-1] == quote_codes[1:]
    terms = (c[:-1] - eta[:-1]) * (c[:-1] - eta[1:])
    totals = np.bincount(
        quote_codes[:-1][same], weights=terms[same], minlength=groups.ngroups)
    spread = np.full(groups.ngroups, np.nan)
    enough = counts >= 3
    spread[enough] = np.sqrt(np.maximum(4 * totals[enough] / (counts[enough] - 1), 0.0))
    last = groups.tail(1)
    p = last.rename(columns={"date": "last_day"})[
        ["ticker", "month", "last_day", "close", "adjclose"]].copy()
    p["spread"] = spread[codes[last.index.to_numpy()]]
    p = p.reset_index(drop=True).sort_values(["ticker", "month"])
    p["ret_next"] = p.groupby("ticker")["adjclose"].shift(-1) / p["adjclose"] - 1.0
    nxt = p.groupby("ticker")["month"].shift(-1)
    p.loc[nxt != p["month"] + 1, "ret_next"] = np.nan  # gaps are not silently bridged
    p["ret_next"] = clean_price_returns(p["ret_next"], "monthly")
    return p


def latest_as_of(facts: pd.DataFrame, key: str, as_of: datetime, value_cols: list[str],
                 *, strict: bool = False) -> pd.DataFrame:
    """Latest row per ``key`` known at ``as_of`` (strictly before it when ``strict``)."""
    known = facts[facts["knowledge_time"] < as_of] if strict else facts[facts["knowledge_time"] <= as_of]
    if known.empty:
        return pd.DataFrame(columns=[key, *value_cols])
    idx = known.sort_values("knowledge_time", kind="stable").groupby(key).tail(1)
    return idx[[key, *value_cols]]


def _as_date(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="coerce").dt.date


def split_factor(cik: pd.Series, start: pd.Series, stop: pd.Series,
                 splits: pd.DataFrame | None) -> np.ndarray:
    """Product of split ratios with ``start < ex_date <= stop`` for each row's ``cik``.

    Rolls a share count measured on ``start`` onto the as-traded basis of ``stop``. Only split
    ex-dates up to ``stop`` are used, so later (future) splits never enter.
    """
    factor = np.ones(len(cik))
    if splits is None or splits.empty:
        return factor
    cik, start, stop = cik.to_numpy(), start.to_numpy(), stop.to_numpy()
    known = pd.notna(start) & pd.notna(stop)
    for ev in splits.itertuples(index=False):
        hit = known & (cik == ev.cik)
        if hit.any():
            rows = np.flatnonzero(hit)
            inside = [(start[i] < ev.ex_date <= stop[i]) for i in rows]
            factor[rows[np.asarray(inside, dtype=bool)]] *= ev.ratio
    return factor


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
    known = known.assign(knowledge_time=known["knowledge_time"].dt.as_unit("ns"))
    known = known.sort_values("knowledge_time", kind="stable").rename(columns={"knowledge_time": "_known_at"})
    left = queries.assign(
        as_of=queries["as_of"].dt.as_unit("ns"), _query_order=np.arange(len(queries)),
    ).sort_values("as_of")
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
    *,
    splits: pd.DataFrame | None = None,
) -> dict[pd.Period, pd.DataFrame]:
    """Precompute formation data once for variants using the same latest-filing rule.

    Only stocks quoted on the formation session itself are eligible; shares and signals must be
    known strictly before that session's close, and shares are rolled onto its split basis.
    """
    if panel.empty:
        return {}
    formation_day = panel.groupby("month")["last_day"].transform("max")
    queries = panel[panel["last_day"] == formation_day].copy()
    queries["as_of"] = queries["last_day"].map(close_time_utc)
    share_cols = ["shares", "share_end"]
    facts = shares.rename(columns={"val": "shares", "end": "share_end"})
    if "share_end" not in facts:
        facts = facts.assign(share_end=pd.NaT)
    queries = values_as_of(queries, facts, share_cols, allow_exact_matches=False)
    queries["shares"] = queries["shares"] * split_factor(
        queries["cik"], _as_date(queries["share_end"]), queries["last_day"], splits)
    queries = queries.drop(columns=["share_end"])
    columns = [c for c in signals if c not in panel.columns and c != "knowledge_time"]
    facts = signals.assign(_signal_time=signals["knowledge_time"])
    queries = values_as_of(
        queries, facts, [*columns, "_signal_time"],
        allow_exact_matches=False,
    )
    age = queries["as_of"] - queries["_signal_time"]
    queries = queries[age <= pd.Timedelta(days=max_signal_age_days)]
    return {m: g.drop(columns=["as_of", "_signal_time"]) for m, g in queries.groupby("month")}


def clean_shares(shares: pd.DataFrame, jump: float = 10.0, confirm_tol: float = 0.2,
                 *, splits: pd.DataFrame | None = None) -> pd.DataFrame:
    """Point-in-time cleaning of reported shares outstanding.

    A value more than ``jump``x away from the last accepted value is held as pending and only takes
    effect when a later filing confirms it (within ``confirm_tol``), as of that later filing's
    knowledge time. This removes 1,000x tagging typos while still accepting genuine reverse
    splits, and never uses information before it was public. With ``splits``, values are compared
    on the same split basis (by measurement date ``end``), so a known split is not a jump.
    """
    out = []
    has_end = "end" in shares
    order = ["knowledge_time", *[c for c in ("end", "accn") if c in shares]]
    ordered = shares.dropna(subset=["val"]).sort_values(order, kind="stable")
    ordered = ordered.drop_duplicates(["cik", "knowledge_time"], keep="last")
    ends = _as_date(ordered["end"]) if has_end else pd.Series(pd.NaT, index=ordered.index)
    ordered = ordered.assign(measured=ends)
    by_cik = {} if splits is None else dict(list(splits.groupby("cik")))

    def rolled(cik, value, start, stop, known_by):
        events = by_cik.get(cik)
        if events is None or pd.isna(start) or pd.isna(stop):
            return value
        inside = (events["ex_date"] > start) & (events["ex_date"] <= stop) & (events["ex_date"] <= known_by)
        return value * float(events.loc[inside, "ratio"].prod())

    for cik, g in ordered.groupby("cik"):
        accepted = pending = None  # (value, measurement date)
        for r in g.itertuples():
            v = float(r.val)
            if v <= 0:
                continue
            known_by = pd.Timestamp(r.knowledge_time).date()
            if accepted is not None:
                base = rolled(cik, accepted[0], accepted[1], r.measured, known_by)
            if pending is not None:
                pend = rolled(cik, pending[0], pending[1], r.measured, known_by)
            if accepted is None or 1 / jump <= v / base <= jump or (pending is not None and abs(v / pend - 1) <= confirm_tol):
                accepted, pending = (v, r.measured), None
                out.append((cik, v, r.knowledge_time, r.measured))
            else:
                pending = (v, r.measured)
    result = pd.DataFrame(out, columns=["cik", "val", "knowledge_time", "end"])
    return result if has_end else result.drop(columns=["end"])


@dataclass(frozen=True)
class Config:
    signal: str = "cos_full"
    n_quantiles: int = 5
    weighting: str = "value"  # or "equal"
    min_price: float = 5.0
    size_pct: str = "p20"
    max_signal_age_days: int = 365
    long_high: bool = True  # long high-similarity (non-changers), short low-similarity
    missing_return: float = 0.0  # pre-registered primary; sensitivities: -0.3 and -1.0


def form_portfolios(
    month: pd.Period,
    signals: pd.DataFrame,
    shares: pd.DataFrame,
    panel_m: pd.DataFrame,
    breakpoint_musd: float,
    cfg: Config,
    *,
    snapshot: pd.DataFrame | None = None,
    splits: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Assign quantiles at the close of the month's last trading day using only known data.

    Only stocks quoted on that session are eligible; stale earlier quotes are not tradable.
    """
    if panel_m.empty:
        return pd.DataFrame()
    if snapshot is None:
        formation_day: date = max(panel_m["last_day"])
        as_of = close_time_utc(formation_day)
        sig = signals[(signals["knowledge_time"] < as_of)
                      & (signals["knowledge_time"] >= as_of - pd.Timedelta(days=cfg.max_signal_age_days))]
        sig = sig.sort_values("knowledge_time", kind="stable").groupby("cik").tail(1)[["cik", cfg.signal]].dropna()
        cols = ["val", "end"] if "end" in shares else ["val"]
        sh = latest_as_of(shares, "cik", as_of, cols, strict=True).rename(columns={"val": "shares"})
        quoted = panel_m[panel_m["last_day"] == formation_day]
        df = quoted.merge(sig, on="cik").merge(sh, on="cik")
        if "end" in df:
            df["shares"] = df["shares"] * split_factor(
                df["cik"], _as_date(df["end"]), df["last_day"], splits)
            df = df.drop(columns=["end"])
    else:
        df = snapshot[[*panel_m.columns, cfg.signal, "shares"]].dropna(
            subset=[cfg.signal, "shares"]).reset_index(drop=True)
    df["mcap_musd"] = df["shares"] * df["close"] / 1e6
    df = df[(df["close"] >= cfg.min_price) & (df["mcap_musd"] >= breakpoint_musd)]
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
        gross = float((cur["w"] * cur["ret_next"].fillna(cfg.missing_return)).sum())
        if prev is None or prev.empty:
            turnover_cost = float((cur["w"] * cur["spread"].fillna(0) / 2).sum())
        else:
            p = prev[prev["q"] == q].set_index("ticker")
            drifted = p["w"] * (1 + p["ret_next"].fillna(cfg.missing_return))
            total = drifted.sum()
            drifted = drifted / total if total else drifted
            new, old = cur["w"].align(drifted, join="outer", fill_value=0.0)
            # Trades happen at this formation, so this month's spread applies; exits fall back
            # to their last estimate.
            spread = cur["spread"].combine_first(p["spread"]).reindex(new.index).fillna(0.0)
            turnover_cost = float(((new - old).abs() * spread / 2).sum())
        out[f"{leg}_gross"] = gross
        out[f"{leg}_cost"] = turnover_cost
        out[f"{leg}_n"] = len(cur)
        out[f"{leg}_missing"] = int(cur["ret_next"].isna().sum())
    out["ls_gross"] = out["long_gross"] - out["short_gross"]
    out["ls_net"] = out["ls_gross"] - out["long_cost"] - out["short_cost"]
    return out
