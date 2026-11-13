"""Quiet-revision detection (hypothesis H6).

A quiet downward revision is a prior-period ``NetIncomeLoss`` value restated more than 1% lower in
a later regular 10-K or 10-Q comparative column, with no amendment (10-K/A, 10-Q/A) and no 8-K
Item 4.02 by the firm in the prior 120 days. Filings that revise three or more income-statement
tags by an identical ratio are treated as unit/scale changes and excluded.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

IS_TAGS = ["NetIncomeLoss", "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
           "OperatingIncomeLoss", "CostOfRevenue", "IncomeTaxExpenseBenefit"]
REGULAR = {"10-K", "10-Q"}
AMEND = {"10-K/A", "10-Q/A"}


def flatten_usd(facts: dict, cik: int, tags: list[str]) -> pd.DataFrame:
    rows = []
    for tag in tags:
        for f in facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", []):
            if f.get("val") is None or not f.get("accn"):
                continue
            rows.append((cik, tag, f.get("start"), f["end"], float(f["val"]), f["accn"], f.get("form")))
    return pd.DataFrame(rows, columns=["cik", "tag", "start", "end", "val", "accession", "form"])


def quiet_down_revisions(
    facts: pd.DataFrame, filings: pd.DataFrame, rel: float = 0.01, min_abs: float = 1e6
) -> pd.DataFrame:
    """One row per (cik, revising accession) with a quiet downward NetIncomeLoss revision.

    ``facts``: output of ``flatten_usd``. ``filings``: cik, accession, form, items, knowledge_time.
    """
    if facts.empty:
        return pd.DataFrame(columns=["cik", "accession", "knowledge_time", "rel_change"])
    f = facts.merge(filings[["accession", "knowledge_time"]], on="accession", how="inner")
    f = f.sort_values("knowledge_time")
    first = f.groupby(["cik", "tag", "start", "end"], dropna=False).first()[["val", "accession"]]
    first.columns = ["first_val", "first_accession"]
    f = f.join(first, on=["cik", "tag", "start", "end"])
    later = f[(f["accession"] != f["first_accession"]) & (f["first_val"].abs() > min_abs)].copy()
    later["ratio"] = later["val"] / later["first_val"]
    later["rel_change"] = (later["val"] - later["first_val"]) / later["first_val"].abs()

    # Unit/scale changes: >= 3 tags in one filing revised by the same ratio.
    revised = later[(later["ratio"] - 1).abs() > 1e-6]
    scale = (revised.assign(r=revised["ratio"].round(3))
             .groupby(["accession", "r"])["tag"].nunique().reset_index())
    scale_accs = set(scale.loc[scale["tag"] >= 3, "accession"])

    ni = later[(later["tag"] == "NetIncomeLoss") & (later["rel_change"] < -rel)
               & later["form"].isin(REGULAR) & ~later["accession"].isin(scale_accs)]
    if ni.empty:
        return pd.DataFrame(columns=["cik", "accession", "knowledge_time", "rel_change"])

    flags = filings[filings["form"].isin(AMEND)
                    | filings["items"].fillna("").str.contains(r"\b4\.02\b")][["cik", "knowledge_time"]]
    keep = []
    for r in ni.itertuples():
        prior = flags[(flags["cik"] == r.cik) & (flags["knowledge_time"] < r.knowledge_time)
                      & (flags["knowledge_time"] >= r.knowledge_time - timedelta(days=120))]
        keep.append(prior.empty)
    ni = ni[keep]
    return (ni.groupby(["cik", "accession", "knowledge_time"], as_index=False)["rel_change"].min())
