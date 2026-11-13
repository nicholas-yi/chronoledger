"""H0 (Lazy Prices replication) data acquisition for the development period. Resumable.

Stages (each skips work already cached):
  universe  -> 10-K filers on major exchanges with public float >= $200M (generous pre-filter)
  filings   -> submissions JSON (exact acceptance times) into data/h0.duckdb
  signals   -> consecutive-10-K similarities (full text and Item 1A), data/h0_signals.parquet
  shares    -> XBRL frames dei:EntityCommonStockSharesOutstanding with knowledge times
  prices    -> daily prices through the development cutoff only

Usage: python scripts/h0_data.py universe filings signals shares
       python scripts/h0_data.py prices        (separate host; can run concurrently)
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone

import pandas as pd

from asof import store
from asof.config import DATA_DIR
from asof.edgar import EdgarClient
from asof.periods import DEV_RETURN_CUTOFF
from asof.sections import cosine_similarity, extract_sections, html_to_text, jaccard_similarity
from asof.universe import current_tickers

DB = DATA_DIR / "h0.duckdb"
UNIVERSE = DATA_DIR / "h0_universe.parquet"
SIGNALS = DATA_DIR / "h0_signals.parquet"
SHARES = DATA_DIR / "h0_shares.parquet"
FILING_FROM = datetime(2021, 7, 1, tzinfo=timezone.utc)
FILING_TO = datetime(2024, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
EXCHANGES = {"NYSE", "Nasdaq", "NYSE American"}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", file=sys.stderr, flush=True)


def stage_universe(client: EdgarClient) -> pd.DataFrame:
    idx = pd.concat(pd.read_parquet(p) for p in DATA_DIR.glob("master_index_*.parquet"))
    tenk = idx[(idx["form"] == "10-K") & (idx["date_filed"] >= date(2021, 7, 1))
               & (idx["date_filed"] <= date(2024, 7, 15))]
    floats = []
    for y in (2021, 2022, 2023):
        for q in range(1, 5):
            try:
                d = client.get_json(
                    f"https://data.sec.gov/api/xbrl/frames/dei/EntityPublicFloat/USD/CY{y}Q{q}I.json")
                floats.append(pd.DataFrame(d["data"])[["cik", "val"]])
            except FileNotFoundError:
                pass
    flt = pd.concat(floats).groupby("cik")["val"].max()
    tick = current_tickers(client)
    tick = tick[tick["exchange"].isin(EXCHANGES)].drop_duplicates("cik")
    uni = tick[tick["cik"].isin(set(tenk["cik"])) & tick["cik"].isin(set(flt[flt >= 2e8].index))]
    uni = uni[["cik", "ticker", "exchange", "name"]].reset_index(drop=True)
    uni.to_parquet(UNIVERSE)
    log(f"universe: {len(uni)} firms")
    return uni


def stage_filings(client: EdgarClient, uni: pd.DataFrame) -> None:
    from asof.bulk import BULK, iter_submissions

    con = store.connect(str(DB))
    done = set(con.execute("SELECT DISTINCT cik FROM filings").df()["cik"])
    if (BULK / "submissions.zip").exists():
        missing = set(uni["cik"]) - done
        for cik, rows in iter_submissions(missing):
            store.ingest_submissions(con, rows)
            done.add(cik)
        log(f"filings: bulk archive supplied {len(done & missing)} additional firms")
    for i, cik in enumerate(uni["cik"]):
        if cik in done:
            continue
        try:
            store.ingest_submissions(con, client.submissions(int(cik)))
        except FileNotFoundError:
            pass
        if i % 200 == 0:
            log(f"filings: {i}/{len(uni)}")
    con.close()


def stage_signals(client: EdgarClient) -> None:
    con = store.connect(str(DB), read_only=True)
    tenks = con.execute(
        "SELECT cik, accession, primary_doc, knowledge_time FROM filings "
        "WHERE form = '10-K' AND knowledge_time BETWEEN ? AND ? ORDER BY cik, knowledge_time",
        [FILING_FROM, FILING_TO]).df()
    con.close()
    done = pd.read_parquet(SIGNALS) if SIGNALS.exists() else pd.DataFrame(columns=["accession"])
    rows = done.to_dict("records")
    seen = set(done["accession"])
    for n, (cik, grp) in enumerate(tenks.groupby("cik")):
        prev = None
        for r in grp.itertuples():
            try:
                text = html_to_text(client.filing_document(int(cik), r.accession, r.primary_doc))
            except FileNotFoundError:
                prev = None
                continue
            risk = extract_sections(text, items=("1A",)).get("1A")
            cur = {"text": text, "risk": risk.text if risk else ""}
            if prev is not None and r.accession not in seen:
                rows.append({
                    "cik": int(cik), "accession": r.accession, "knowledge_time": r.knowledge_time,
                    "prev_accession": prev["accession"], "prev_knowledge_time": prev["knowledge_time"],
                    "cos_full": cosine_similarity(prev["text"], cur["text"]),
                    "jac_full": jaccard_similarity(prev["text"], cur["text"]),
                    "cos_1a": cosine_similarity(prev["risk"], cur["risk"]) if prev["risk"] and cur["risk"] else float("nan"),
                    "len_full": len(cur["text"]), "len_1a": len(cur["risk"]),
                })
            prev = {**cur, "accession": r.accession, "knowledge_time": r.knowledge_time}
        if n % 100 == 0:
            pd.DataFrame(rows).to_parquet(SIGNALS)
            log(f"signals: {n} firms, {len(rows)} pairs")
    pd.DataFrame(rows).to_parquet(SIGNALS)
    log(f"signals: done, {len(rows)} pairs")


def stage_features() -> None:
    from asof.features import build

    con = store.connect(str(DB), read_only=True)
    jobs = con.execute(
        "SELECT cik, accession, primary_doc, form FROM filings "
        "WHERE form IN ('10-K', '10-Q') AND knowledge_time BETWEEN ? AND ? ORDER BY knowledge_time",
        [FILING_FROM, FILING_TO]).fetchall()
    con.close()
    log(f"features: {len(jobs)} filings (10-K and 10-Q)")
    errors = build([(int(c), a, d, f) for c, a, d, f in jobs])
    log(f"features: done, {len(errors)} errors")
    (DATA_DIR / "h0_feature_errors.json").write_text(__import__("json").dumps(errors, indent=1))


def stage_pairs() -> None:
    """10-K vs previous 10-K; 10-Q vs the same fiscal quarter one year earlier (Lazy Prices)."""
    from asof.features import cosine, jaccard, load

    con = store.connect(str(DB), read_only=True)
    f = con.execute(
        "SELECT cik, accession, form, report_date, knowledge_time FROM filings "
        "WHERE form IN ('10-K', '10-Q') AND knowledge_time BETWEEN ? AND ? ORDER BY cik, knowledge_time",
        [FILING_FROM, FILING_TO]).df()
    con.close()
    f["report_date"] = pd.to_datetime(f["report_date"])
    rows = []
    for (cik, form), g in f.groupby(["cik", "form"]):
        g = g.dropna(subset=["report_date"]).sort_values("knowledge_time")
        for r in g.itertuples():
            if form == "10-K":
                prev = g[g["knowledge_time"] < r.knowledge_time].tail(1)
            else:
                lag = (r.report_date - g["report_date"]).dt.days
                prev = g[(g["knowledge_time"] < r.knowledge_time) & lag.between(340, 390)].tail(1)
            if prev.empty:
                continue
            a, b = load(prev["accession"].iloc[0]), load(r.accession)
            if a is None or b is None:
                continue
            rows.append({
                "cik": int(cik), "form": form, "accession": r.accession, "knowledge_time": r.knowledge_time,
                "prev_accession": prev["accession"].iloc[0],
                "cos_full": cosine(a["full"], b["full"]), "jac_full": jaccard(a["full"], b["full"]),
                "cos_1a": cosine(a.get("sec_1A"), b.get("sec_1A")),
                "len_full": b["len_full"], "len_1a": b.get("len_1A", 0),
            })
    out = pd.DataFrame(rows)
    out.to_parquet(SIGNALS)
    log(f"pairs: {len(out)} ({(out['form'] == '10-K').sum()} 10-K, {(out['form'] == '10-Q').sum()} 10-Q)")


def stage_shares(client: EdgarClient) -> None:
    frames = []
    for y in (2021, 2022, 2023, 2024):
        for q in range(1, 5):
            try:
                d = client.get_json(
                    "https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/"
                    f"shares/CY{y}Q{q}I.json")
                frames.append(pd.DataFrame(d["data"])[["accn", "cik", "end", "val"]])
            except FileNotFoundError:
                pass
    sh = pd.concat(frames).drop_duplicates()
    con = store.connect(str(DB), read_only=True)
    kt = con.execute("SELECT accession AS accn, knowledge_time FROM filings").df()
    con.close()
    sh = sh.merge(kt, on="accn", how="inner")  # exact acceptance time only; unknown accessions dropped
    sh.to_parquet(SHARES)
    log(f"shares: {len(sh)} facts with exact knowledge time")


def stage_prices(uni: pd.DataFrame) -> None:
    from asof.prices import YahooPrices

    y = YahooPrices()
    for i, t in enumerate(uni["ticker"]):
        try:
            y.raw(t, end=DEV_RETURN_CUTOFF)
        except Exception as exc:  # keep going; coverage is audited later
            log(f"prices: {t} failed: {exc!r}")
        if i % 200 == 0:
            log(f"prices: {i}/{len(uni)}")


def main() -> None:
    stages = sys.argv[1:] or ["universe", "filings", "signals", "shares"]
    client = EdgarClient()
    uni = pd.read_parquet(UNIVERSE) if UNIVERSE.exists() else None
    if "universe" in stages or uni is None:
        uni = stage_universe(client)
    if "filings" in stages:
        stage_filings(client, uni)
    if "signals" in stages:
        stage_signals(client)
    if "features" in stages:
        stage_features()
    if "pairs" in stages:
        stage_pairs()
    if "shares" in stages:
        stage_shares(client)
    if "prices" in stages:
        stage_prices(uni)


if __name__ == "__main__":
    main()
