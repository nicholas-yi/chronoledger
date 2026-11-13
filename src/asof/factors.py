"""Kenneth French Data Library loaders (linked and cited; files are cached locally, not re-hosted)."""

from __future__ import annotations

import io
import zipfile

import httpx
import pandas as pd

from asof.config import RAW_DIR

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"


def _fetch(name: str) -> str:
    path = RAW_DIR / "french" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        r = httpx.get(BASE + name, timeout=120, follow_redirects=True)
        r.raise_for_status()
        path.write_bytes(r.content)
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as zf:
        return zf.read(zf.namelist()[0]).decode("latin-1")


def _monthly_table(text: str) -> pd.DataFrame:
    """Parse the first block of YYYYMM rows (the monthly table) from a French CSV."""
    rows, header = [], None
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if header is None and len(parts) > 1 and parts[0] == "" and parts[1]:
            header = parts[1:]
            continue
        if header is not None:
            if len(parts[0]) == 6 and parts[0].isdigit():
                rows.append(parts)
            elif rows:
                break
    df = pd.DataFrame(rows, columns=["yyyymm", *header[: len(rows[0]) - 1]])
    df["month"] = pd.PeriodIndex(df.pop("yyyymm"), freq="M")
    return df.set_index("month").astype(float)


def ff5_umd_monthly() -> pd.DataFrame:
    ff5 = _monthly_table(_fetch("F-F_Research_Data_5_Factors_2x3_CSV.zip"))
    mom = _monthly_table(_fetch("F-F_Momentum_Factor_CSV.zip"))
    mom.columns = ["UMD"]
    out = ff5.join(mom, how="inner") / 100.0
    out.columns = [c.replace("-", "_") for c in out.columns]
    return out


def nyse_me_breakpoints() -> pd.DataFrame:
    """Monthly NYSE market-equity breakpoints in $ millions; columns p5..p100."""
    text = _fetch("ME_Breakpoints_CSV.zip")
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts[0]) == 6 and parts[0].isdigit() and len(parts) >= 22:
            rows.append([parts[0]] + parts[2:22])
    df = pd.DataFrame(rows, columns=["yyyymm"] + [f"p{5 * i}" for i in range(1, 21)])
    df["month"] = pd.PeriodIndex(df.pop("yyyymm"), freq="M")
    return df.set_index("month").astype(float)


def _daily_table(text: str) -> pd.DataFrame:
    rows, header = [], None
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if header is None and len(parts) > 1 and parts[0] == "" and parts[1]:
            header = parts[1:]
            continue
        if header is not None:
            if len(parts[0]) == 8 and parts[0].isdigit():
                rows.append(parts)
            elif rows:
                break
    df = pd.DataFrame(rows, columns=["yyyymmdd", *header[: len(rows[0]) - 1]])
    df["date"] = pd.to_datetime(df.pop("yyyymmdd"), format="%Y%m%d").dt.date
    return df.set_index("date").astype(float)


def ff5_umd_daily() -> pd.DataFrame:
    ff5 = _daily_table(_fetch("F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"))
    mom = _daily_table(_fetch("F-F_Momentum_Factor_daily_CSV.zip"))
    mom.columns = ["UMD"]
    out = ff5.join(mom, how="inner") / 100.0
    out.columns = [c.replace("-", "_") for c in out.columns]
    return out
