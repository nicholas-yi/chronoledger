"""Read-only acceptance-time/source adjudication; no ingestion fix or research rerun."""

from __future__ import annotations

import gzip
import html
import json
import re
import sys
import zipfile
from datetime import datetime

import httpx
import numpy as np
import pandas as pd
from sec_identity_audit import BudgetClient, RequestBudgetExceeded

from asof import ledger, store
from asof.config import DATA_DIR, PROJECT_ROOT, RAW_DIR
from asof.timeutil import close_time_utc, parse_header_acceptance_et

RECEIPT = DATA_DIR / "p0_SEC_request_receipt.json"


def header_fields(raw: str) -> dict:
    text = html.unescape(raw)
    match = re.search(r"ACCEPTANCE-DATETIME[^0-9]{0,100}(\d{14})", text, re.IGNORECASE)
    value = None if match is None else match.group(1)
    return {
        "header_raw": value,
        "UTC_if_header_ET": None if value is None else parse_header_acceptance_et(value).isoformat(),
        "header_CIKs": sorted(set(re.findall(
            r"CENTRAL\s+INDEX\s+KEY[^0-9]{0,80}(\d{10})", text, re.IGNORECASE))),
    }


def timing_impact(frame: pd.DataFrame, days: list) -> dict:
    """Conditional column comparison only; neither column is promoted to authority."""
    identities = frame[["cik_pair", "accession"]]
    calendar = pd.DatetimeIndex([close_time_utc(d) for d in days]).as_unit("ns")
    before = pd.to_datetime(frame["knowledge_time_pair"], utc=True).dt.as_unit("ns")
    after = pd.to_datetime(frame["knowledge_time_bulk"], utc=True).dt.as_unit("ns")
    left = np.searchsorted(calendar.asi8, before.array.asi8, side="right")
    right = np.searchsorted(calendar.asi8, after.array.asi8, side="right")
    formation = pd.Series(days, index=pd.PeriodIndex(days, freq="M")).groupby(level=0).max()
    formation = formation.loc[pd.Period("2023-01", "M"):pd.Period("2024-06", "M")]
    changed = np.zeros(len(frame), dtype=bool)
    instances = 0
    latest_instances = 0
    for day in formation:
        close = close_time_utc(day)
        a = (before < close) & (before >= close - pd.Timedelta(days=365))
        b = (after < close) & (after >= close - pd.Timedelta(days=365))
        mask = a.to_numpy() != b.to_numpy()
        changed |= mask
        instances += int(mask.sum())
        selected = []
        for eligible, timestamp in ((a, before), (b, after)):
            part = identities.loc[eligible].copy()
            part["time"] = timestamp.loc[eligible]
            selected.append(part.sort_values("time", kind="stable").groupby("cik_pair").tail(1)
                            .set_index("cik_pair")["accession"])
        index = selected[0].index.union(selected[1].index)
        latest_instances += int((
            selected[0].reindex(index).fillna("absent")
            != selected[1].reindex(index).fillna("absent")).sum())
    return {
        "rows": len(frame), "first_registered_close_differs": int((left != right).sum()),
        "formation_eligibility_rows_differ": int(changed.sum()),
        "formation_row_month_instances_differ": instances,
        "latest_signal_firm_month_choices_differ": latest_instances,
        "calendar_year_assignments_differ": int((before.dt.year != after.dt.year).sum()),
        "first_close_unassigned_at_cutoff": int(((left == len(calendar)) |
                                               (right == len(calendar))).sum()),
        "note": "Conditional comparison of supplied timestamps, not a universal authoritative correction. "
                "No signal values, portfolio weights, prices or outcomes used.",
    }


def factor_calendar() -> list:
    calendars = []
    for name in ("F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
                 "F-F_Momentum_Factor_daily_CSV.zip"):
        path = RAW_DIR / "french" / name
        if not path.exists():
            raise FileNotFoundError("P0 calendar cache absent: no vendor fetch permitted")
        with zipfile.ZipFile(path) as archive:
            text = archive.read(archive.namelist()[0]).decode("latin-1")
        stamps = {line.partition(",")[0].strip() for line in text.splitlines()}
        calendars.append({datetime.strptime(s, "%Y%m%d").date()
                          for s in stamps if len(s) == 8 and s.isdigit() and s <= "20240731"})
    return sorted(calendars[0] & calendars[1])


def main() -> None:
    comparison = pd.read_parquet(DATA_DIR / "p0_pair_metadata_comparison.parquet")
    sample = pd.read_parquet(DATA_DIR / "p0_header_sample.parquet")
    extra = []
    for agent in ("0000950170", "0001564590"):
        for offset in (4.0, 5.0):
            part = comparison[(comparison["agent"] == agent) & (comparison["offset_hours"] == offset)]
            extra.append(part.sort_values("accession").head(1))
    h4_sample = pd.read_parquet(DATA_DIR / "h4_sample.parquet", columns=["cik"])["cik"]
    h4_meta = pd.read_parquet(
        DATA_DIR / "bulk_filings.parquet", columns=["cik", "accession", "form", "knowledge_time"],
        filters=[("knowledge_time", ">=", pd.Timestamp("2012-01-01", tz="UTC")),
                 ("knowledge_time", "<=", pd.Timestamp("2018-12-31 23:59:59", tz="UTC")),
                 ("cik", "in", h4_sample.tolist())], use_threads=False)
    for year, month in ((2012, 2), (2012, 7), (2018, 2), (2018, 7)):
        part = h4_meta[(h4_meta["knowledge_time"].dt.year == year)
                       & (h4_meta["knowledge_time"].dt.month == month)
                       & h4_meta["form"].isin(["10-K", "10-Q"])].sort_values("accession").head(1)
        if not part.empty:
            extra.append(part.rename(columns={
                "cik": "cik_pair", "form": "form_pair", "knowledge_time": "knowledge_time_pair"}).assign(
                    cik_bulk=lambda x: x["cik_pair"], knowledge_time_bulk=lambda x: x["knowledge_time_pair"],
                    offset_hours=0.0, agent=lambda x: x["accession"].str[:10]))
    sample = pd.concat([sample, *extra], ignore_index=True).drop_duplicates("accession")
    prior = json.loads(RECEIPT.read_text())["actual_HTTP_attempts"] if RECEIPT.exists() else 0

    class Client(BudgetClient):
        def _count_request(self, request: httpx.Request) -> None:
            if prior + self.http_attempts >= 150:
                raise RequestBudgetExceeded("P0 total150 HTTP attempt ceiling")
            super()._count_request(request)

    client = Client()
    result = {
        "scope": "Read-only P0 metadata/source audit; no timestamps, CIKs or research inputs changed",
        "header_timezone_interpretation": "ET candidate recorded separately; header and own index "
                                        "wall times compared without choosing internal source",
        "authority_sample": [], "official_sources": [],
        "status": "incomplete_or_ambiguous", "universal_fix_applied": False,
    }
    try:
        url = "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data"
        try:
            text = html.unescape(client.get_bytes(url).decode("utf-8", errors="replace"))
            stripped = " ".join(re.sub(r"<[^>]*>", " ", text).split())
            match = re.search(r"EDGAR accepts new filer applications.{0,400}", stripped)
            result["official_sources"].append({
                "url": url, "retrieval": "direct project client",
                "business_hours_quote": None if match is None else match.group(0)[:450],
                "limitation": "ET operating/dissemination clock, not yet a field-specific "
                              "acceptanceDateTime JSON guarantee.",
            })
        except (httpx.HTTPError, FileNotFoundError) as exc:
            result["official_sources"].append({"url": url, "retrieval": "failed", "error": repr(exc)})
        for row in sample.itertuples():
            cik, acc = int(row.cik_pair), row.accession
            record = {
                "cik_pair": cik, "cik_bulk": int(row.cik_bulk), "accession": acc,
                "agent_prefix": row.agent, "pair_UTC": row.knowledge_time_pair.isoformat(),
                "bulk_UTC": row.knowledge_time_bulk.isoformat(), "offset_hours": row.offset_hours,
            }
            try:
                record.update(header_fields(client.filing_header(cik, acc)))
                index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.html"
                raw_index = client.get_bytes(index_url).decode("utf-8", errors="replace")
                accepted = re.search(
                    r"Accepted\s*</div>\s*<div[^>]*>\s*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)",
                    raw_index, re.IGNORECASE)
                record["index_Accepted"] = None if accepted is None else accepted.group(1)
                record["index_url"] = index_url
                record["header_index_wall_match"] = (accepted is not None
                    and re.sub(r"\D", "", accepted.group(1)) == record["header_raw"])
                candidate = record["UTC_if_header_ET"]
                record["ET_candidate_matches_pair"] = (candidate is not None
                    and pd.Timestamp(candidate) == row.knowledge_time_pair)
                record["ET_candidate_matches_bulk"] = (candidate is not None
                    and pd.Timestamp(candidate) == row.knowledge_time_bulk)
            except (httpx.HTTPError, FileNotFoundError, RequestBudgetExceeded) as exc:
                record["authority_error"] = repr(exc)
            result["authority_sample"].append(record)
            print(f"{acc}: header/index={record.get('header_index_wall_match')}, "
                  f"ET candidate pair={record.get('ET_candidate_matches_pair')} "
                  f"bulk={record.get('ET_candidate_matches_bulk')}", file=sys.stderr, flush=True)
            if "authority_error" in record:
                break

        # Inspect original API caches only: no refresh and no new submissions endpoint calls.
        traces = []
        targets = set(comparison.loc[comparison["offset_hours"] != 0, "accession"])
        for cik in sorted(set(comparison.loc[comparison["offset_hours"] != 0, "cik_pair"])):
            base = "https://data.sec.gov/submissions/"
            path = client._cache_path(f"{base}CIK{int(cik):010d}.json")
            if not path.exists():
                traces.append({"cik": int(cik), "API_cache": "absent"})
                continue
            top = json.loads(gzip.decompress(path.read_bytes()))
            blocks = [("root_recent", path.name, top["filings"]["recent"])]
            for page in top["filings"].get("files", []):
                p = client._cache_path(base + page["name"])
                if p.exists():
                    blocks.append(("historical_page", page["name"],
                                   json.loads(gzip.decompress(p.read_bytes()))))
            for kind, name, block in blocks:
                for i, acc in enumerate(block.get("accessionNumber", [])):
                    if acc in targets:
                        traces.append({"cik": int(cik), "accession": acc, "source_kind": kind,
                                       "source_member": name,
                                       "raw_acceptanceDateTime": block["acceptanceDateTime"][i]})
        result["original_API_cache_traces"] = traces
        days = factor_calendar()
        result["full_H0_pair_vs_bulk_impact"] = timing_impact(comparison, days)
        result["development_H0_pair_vs_bulk_impact"] = timing_impact(comparison[
            comparison["knowledge_time_pair"].between(
                pd.Timestamp("2023-01-01", tz="UTC"),
                pd.Timestamp("2024-06-30 23:59:59", tz="UTC"))], days)
        result["development_annual_H0_pair_vs_bulk_impact"] = timing_impact(comparison[
            (comparison["form_pair"] == "10-K") & comparison["knowledge_time_pair"].between(
                pd.Timestamp("2023-01-01", tz="UTC"),
                pd.Timestamp("2024-06-30 23:59:59", tz="UTC"))], days)
        con = store.connect(str(DATA_DIR / "h0.duckdb"), read_only=True)
        try:
            con.execute("SET threads=1")
            db = con.execute(
                "SELECT cik,accession,form,knowledge_time FROM filings WHERE form IN "
                "('10-K','10-Q','10-K/A','10-Q/A','8-K','NT 10-K','NT 10-Q') "
                "AND knowledge_time>=TIMESTAMPTZ '2012-01-01' "
                "AND knowledge_time<=TIMESTAMPTZ '2024-07-31 23:59:59'").df()
        finally:
            con.close()
        bulk = pd.read_parquet(
            DATA_DIR / "bulk_filings.parquet", columns=["cik", "accession", "form", "knowledge_time"],
            filters=[("knowledge_time", ">=", pd.Timestamp("2012-01-01", tz="UTC")),
                     ("knowledge_time", "<=", pd.Timestamp("2024-07-31 23:59:59", tz="UTC"))],
            use_threads=False)
        joined = db.merge(bulk, on="accession", suffixes=("_pair", "_bulk"), validate="one_to_one")
        joined["offset_hours"] = (
            joined["knowledge_time_bulk"] - joined["knowledge_time_pair"]).dt.total_seconds() / 3600
        summaries = {}
        windows = {
            "H5_underlying_DB_events": joined["form_pair"].isin(["8-K", "NT 10-K", "NT 10-Q"])
                & joined["knowledge_time_pair"].between(
                    pd.Timestamp("2023-01-01", tz="UTC"),
                    pd.Timestamp("2024-06-30 23:59:59", tz="UTC")),
            "H4_H6a_underlying_DB_overlap": joined["knowledge_time_pair"].between(
                pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2018-12-31 23:59:59", tz="UTC")),
        }
        for label, mask in windows.items():
            part = joined[mask]
            summaries[label] = {
                "rows_compared": len(part),
                "offset_counts": {str(k): int(v) for k, v in part["offset_hours"].value_counts().items()},
                "conditional_column_impact": timing_impact(part, days),
                "limitation": "DB/bulk overlap only, not header-authoritative certification "
                              "of all bulk-only filers or regenerated H6 quiet events.",
            }
        result["event_source_comparisons"] = summaries
        h4_pairs = pd.read_parquet(
            DATA_DIR / "h4_pairs.parquet", columns=["cik", "accession", "knowledge_time"],
            filters=[("knowledge_time", ">=", pd.Timestamp("2012-01-01", tz="UTC")),
                     ("knowledge_time", "<=", pd.Timestamp("2018-12-31 23:59:59", tz="UTC"))],
            use_threads=False)
        checked = h4_pairs.merge(bulk, on="accession", suffixes=("_pair", "_bulk"),
                                  how="left", validate="one_to_one")
        result["H4_actual_development_pair_path"] = {
            "rows": len(h4_pairs), "bulk_reference_missing": int(checked["cik_bulk"].isna().sum()),
            "timestamp_disagreements": int(
                (checked["knowledge_time_pair"] != checked["knowledge_time_bulk"]).sum()),
            "source_path": "Both H4 pairs and H6a underlying filings use bulk; equality is "
                           "path consistency, not independent authority.",
            "H6a_regular_or_amendment_input_rows": int(
                h4_meta["form"].isin(["10-K", "10-Q", "10-K/A", "10-Q/A"]).sum()),
            "limitation": "H6 quiet detection not rerun and bulk-only CIKs not exhaustively "
                          "header certified; no claim all H6 event times are correct.",
        }
        uni = pd.read_parquet(DATA_DIR / "h0_universe.parquet", columns=["cik", "ticker"])
        shares = pd.read_parquet(DATA_DIR / "h0_shares.parquet", columns=["cik"])
        mismatch = comparison[comparison["cik_pair"] != comparison["cik_bulk"]]
        result["co_registrants"] = {
            "signal_accessions_under_multiple_CIKs": int(
                comparison.groupby("accession")["cik_pair"].nunique().gt(1).sum()),
            "mismatching_signal_rows": len(mismatch),
            "bulk_CIK_in_price_universe_rows": int(mismatch["cik_bulk"].isin(uni["cik"]).sum()),
            "pair_CIK_with_share_metadata_rows": int(mismatch["cik_pair"].isin(shares["cik"]).sum()),
            "bulk_CIK_with_share_metadata_rows": int(mismatch["cik_bulk"].isin(shares["cik"]).sum()),
            "example6201_in_universe": uni[uni["cik"].isin([6201, 4515])].to_dict("records"),
            "examples": [{"pair_CIK": int(r.cik_pair), "bulk_CIK": int(r.cik_bulk),
                          "accession": r.accession} for r in mismatch.head(10).itertuples()],
            "action": "No CIK remap/dedup applied. Accession identity is not a unique share class.",
        }
        sampled = pd.DataFrame([{
            "cik_pair": r["cik_pair"], "accession": r["accession"],
            "knowledge_time_pair": pd.Timestamp(r["pair_UTC"]),
            "knowledge_time_bulk": pd.Timestamp(r["UTC_if_header_ET"]),
        } for r in result["authority_sample"] if r.get("UTC_if_header_ET")])
        if not sampled.empty:
            result["sample_pair_vs_ET_header_impact"] = timing_impact(sampled, days)
            result["sample_pair_vs_ET_header_impact"]["scope"] = (
                "Header/index sample only; latest-signal choices are sample-local, "
                "not the complete formation cross-sections.")
        result["sample_both_CIKs_in_own_header"] = [
            {"accession": r["accession"],
             "both_present": f"{r['cik_pair']:010d}" in r.get("header_CIKs", [])
                             and f"{r['cik_bulk']:010d}" in r.get("header_CIKs", [])}
            for r in result["authority_sample"] if r["cik_pair"] != r["cik_bulk"]]
        result["lineage"] = ledger.lineage()
    finally:
        total = prior + client.http_attempts
        result["actual_P0_HTTP_attempts_cumulative"] = total
        RECEIPT.write_text(json.dumps({"actual_HTTP_attempts": total, "ceiling": 150}))
        client.close()
        (PROJECT_ROOT / "results" / "p0_acceptance_authority_audit.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
