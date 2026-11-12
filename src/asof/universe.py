"""Universe construction and survivorship-coverage auditing from EDGAR full-index files."""

from __future__ import annotations

import io

import pandas as pd

from asof.edgar import EdgarClient

ANNUAL_FORMS = {"10-K", "10-K405", "10-KSB", "10-KT"}
DELISTING_FORMS = {"25", "25-NSE", "15-12B", "15-12G", "15-15D", "15"}


def master_index(client: EdgarClient, year: int, quarter: int) -> pd.DataFrame:
    """Parse EDGAR's quarterly master index (pipe-delimited; date only, no time of day)."""
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
    text = client.get_bytes(url).decode("latin-1")
    start = text.index("CIK|Company Name|Form Type|Date Filed|Filename")
    body = text[start:].splitlines()
    lines = [body[0]] + [ln for ln in body[2:] if ln.count("|") == 4]
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep="|", dtype=str)
    df.columns = ["cik", "company", "form", "date_filed", "filename"]
    df["cik"] = df["cik"].astype(int)
    df["date_filed"] = pd.to_datetime(df["date_filed"]).dt.date
    return df


def current_tickers(client: EdgarClient) -> pd.DataFrame:
    """SEC's current CIK-ticker map. It reflects today's listings only (survivorship!)."""
    data = client.get_json("https://www.sec.gov/files/company_tickers_exchange.json", refresh=False)
    df = pd.DataFrame(data["data"], columns=data["fields"])
    return df.rename(columns={"cik": "cik", "ticker": "ticker", "exchange": "exchange"})


def coverage_audit(index: pd.DataFrame, tickers: pd.DataFrame) -> pd.DataFrame:
    """Per filing year: annual-report filers, how many still have a ticker, how many delisted."""
    annual = index[index["form"].isin(ANNUAL_FORMS)].copy()
    annual["year"] = pd.to_datetime(annual["date_filed"]).dt.year
    delist = index[index["form"].isin(DELISTING_FORMS)][["cik", "date_filed"]]
    first_delist = delist.groupby("cik")["date_filed"].min()
    has_ticker = set(tickers["cik"].astype(int))
    last_annual = annual.groupby("cik")["year"].max()
    final_year = int(annual["year"].max())

    rows = []
    for year, grp in annual.groupby("year"):
        ciks = set(grp["cik"])
        with_ticker = ciks & has_ticker
        later_delist = {c for c in ciks if c in first_delist.index}
        stopped = {c for c in ciks if last_annual[c] < final_year - 1}
        rows.append(
            {
                "year": year,
                "annual_filers": len(ciks),
                "with_current_ticker": len(with_ticker),
                "coverage": len(with_ticker) / len(ciks),
                "filed_form_25_or_15_ever": len(later_delist),
                "stopped_filing_annual": len(stopped),
                "missing_and_stopped": len((ciks - has_ticker) & stopped),
            }
        )
    return pd.DataFrame(rows)
