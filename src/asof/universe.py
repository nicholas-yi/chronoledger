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
