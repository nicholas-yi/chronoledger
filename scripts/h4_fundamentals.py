"""H4: does 10-K text change predict future fundamentals? (pre-registration v2, section 3)

Stages: bulk  -> entities and filings for all filers from submissions.zip
        sample -> 1,500 CIKs (seed 20261112): any 10-K in the window and max public float >= $50M
        features, pairs -> 10-K text features and consecutive-10-K similarities
        outcomes -> first-reported fiscal-year values from companyfacts.zip
        test   -> development-period regressions only (validation and holdout untouched)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT

ENT, FIL = DATA_DIR / "bulk_entities.parquet", DATA_DIR / "bulk_filings.parquet"
SAMPLE, PAIRS, OUT = DATA_DIR / "h4_sample.parquet", DATA_DIR / "h4_pairs.parquet", DATA_DIR / "h4_outcomes.parquet"
SEED, N_SAMPLE = 20261112, 1500
WIN_LO = pd.Timestamp("2011-01-01", tz="UTC")
WIN_HI = pd.Timestamp("2025-06-30 23:59:59", tz="UTC")
DEV = (pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2018-12-31 23:59:59", tz="UTC"))
NI_TAGS = ["NetIncomeLoss", "ProfitLoss"]
REV_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", file=sys.stderr, flush=True)


def stage_bulk() -> None:
    from asof.bulk import read_submissions

    ent, fil = read_submissions()
    ent.to_parquet(ENT)
    fil.to_parquet(FIL)
    log(f"bulk: {len(ent)} entities, {len(fil)} filings")


def stage_sample() -> None:
    from asof.bulk import max_public_float

    fil = pd.read_parquet(FIL)
    k = fil[(fil["form"] == "10-K") & fil["knowledge_time"].between(WIN_LO, WIN_HI)]
    flt = max_public_float()
    eligible = sorted(set(k["cik"]) & set(flt[flt >= 5e7].index))
    rng = np.random.default_rng(SEED)
    chosen = sorted(rng.choice(eligible, size=min(N_SAMPLE, len(eligible)), replace=False).tolist())
    pd.DataFrame({"cik": chosen}).to_parquet(SAMPLE)
    log(f"sample: {len(chosen)} of {len(eligible)} eligible")


def stage_features() -> None:
    from asof.features import build

    fil = pd.read_parquet(FIL)
    s = set(pd.read_parquet(SAMPLE)["cik"])
    k = fil[(fil["form"] == "10-K") & fil["cik"].isin(s) & fil["knowledge_time"].between(WIN_LO, WIN_HI)]
    jobs = [(int(r.cik), r.accession, r.primary_doc, r.form) for r in k.itertuples()]
    log(f"features: {len(jobs)} 10-Ks")
    errors = build(jobs)
    log(f"features: done, {len(errors)} errors")


def stage_pairs() -> None:
    from asof.features import cosine, load

    fil = pd.read_parquet(FIL)
    s = set(pd.read_parquet(SAMPLE)["cik"])
    k = fil[(fil["form"] == "10-K") & fil["cik"].isin(s)].copy()
    k["report_date"] = pd.to_datetime(k["report_date"])
    rows = []
    for cik, g in k.sort_values("knowledge_time").groupby("cik"):
        g = g.dropna(subset=["report_date"])
        for i in range(1, len(g)):
            cur, prev = g.iloc[i], g.iloc[i - 1]
            lag = (cur["report_date"] - prev["report_date"]).days
            if not 300 <= lag <= 430:
                continue
            a, b = load(prev["accession"]), load(cur["accession"])
            if a is None or b is None:
                continue
            rows.append({"cik": cik, "accession": cur["accession"], "knowledge_time": cur["knowledge_time"],
                         "report_date": cur["report_date"], "cos_full": cosine(a["full"], b["full"]),
                         "cos_1a": cosine(a.get("sec_1A"), b.get("sec_1A"))})
    pd.DataFrame(rows).to_parquet(PAIRS)
    log(f"pairs: {len(rows)}")


def _first_reported(facts: dict, tags: list[str], accession: str, end: str, duration: bool) -> float | None:
    for tag in tags:
        units = facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
        for f in units:
            if f.get("accn") != accession or f.get("end") != end:
                continue
            if duration:
                if not f.get("start"):
                    continue
                days = (pd.Timestamp(f["end"]) - pd.Timestamp(f["start"])).days
                if not 330 <= days <= 400:
                    continue
            return float(f["val"])
    return None


def stage_outcomes() -> None:
    from asof.bulk import read_companyfacts

    fil = pd.read_parquet(FIL)
    s = set(pd.read_parquet(SAMPLE)["cik"])
    k = fil[(fil["form"] == "10-K") & fil["cik"].isin(s)].dropna(subset=["report_date"])
    cf = read_companyfacts(s)
    rows = []
    for r in k.itertuples():
        facts = cf.get(int(r.cik), {}).get("facts", {})
        end = str(r.report_date)[:10]
        rows.append({
            "cik": int(r.cik), "accession": r.accession, "report_date": end,
            "ni": _first_reported(facts, NI_TAGS, r.accession, end, True),
            "assets": _first_reported(facts, ["Assets"], r.accession, end, False),
            "revenue": _first_reported(facts, REV_TAGS, r.accession, end, True),
            "gw_impair": _first_reported(facts, ["GoodwillImpairmentLoss"], r.accession, end, True),
        })
    out = pd.DataFrame(rows)
    out.to_parquet(OUT)
    log(f"outcomes: {len(out)} 10-Ks, {out['ni'].notna().mean():.0%} with NI, {out['assets'].notna().mean():.0%} with assets")


def build_panel() -> pd.DataFrame:
    pairs = pd.read_parquet(PAIRS)
    out = pd.read_parquet(OUT)
    out["report_date"] = pd.to_datetime(out["report_date"])
    out = out.sort_values(["cik", "report_date"])
    nxt = out.groupby("cik").shift(-1)
    lag = (nxt["report_date"] - out["report_date"]).dt.days
    out["roa"] = out["ni"] / out["assets"]
    out["roa_next"] = (nxt["ni"] / nxt["assets"]).where(lag.between(300, 430))
    out["d_roa"] = out["roa_next"] - out["roa"]
    out["decline"] = (nxt["ni"] < out["ni"]).astype(float).where(lag.between(300, 430) & nxt["ni"].notna())
    out["impair_next"] = (nxt["gw_impair"].fillna(0) > 0).astype(float).where(lag.between(300, 430))
    prev_rev = out.groupby("cik")["revenue"].shift(1)
    out["sales_growth"] = out["revenue"] / prev_rev - 1
    out["log_assets"] = np.log(out["assets"].where(out["assets"] > 0))
    panel = pairs.merge(out.drop(columns=["report_date"]), on=["cik", "accession"])
    ent = pd.read_parquet(ENT)[["cik", "sic"]]
    panel = panel.merge(ent, on="cik", how="left")
    panel["sic2"] = panel["sic"].astype(str).str[:2]
    panel["year"] = pd.to_datetime(panel["knowledge_time"]).dt.year
    # Winsorize ratio variables at 1%/99% (standard; set before seeing outcomes).
    for c in ("roa", "d_roa", "sales_growth"):
        lo, hi = panel[c].quantile([0.01, 0.99])
        panel[c] = panel[c].clip(lo, hi)
    panel["change"] = 1.0 - panel["cos_full"]
    return panel


def stage_test() -> None:
    import statsmodels.api as sm

    from asof.events import neutralize

    panel = build_panel()
    dev = panel[pd.to_datetime(panel["knowledge_time"]).between(*DEV)].copy()
    dev["change_n"] = np.nan
    for y, g in dev.groupby("year"):
        dev.loc[g.index, "change_n"] = neutralize(g, "change", "sic2", ["log_assets"])
    results = {}
    for sig in ("change_n", "change"):
        for outcome in ("d_roa", "decline", "impair_next"):
            cols = [sig, "log_assets", "roa", "sales_growth"]
            d = dev.dropna(subset=[outcome, *cols, "sic2"])
            fe = pd.get_dummies(d[["sic2", "year"]].astype(str), drop_first=True, dtype=float)
            x = sm.add_constant(pd.concat([d[cols], fe], axis=1))
            groups = np.column_stack([pd.factorize(d["cik"])[0], pd.factorize(d["year"])[0]])
            fit = sm.OLS(d[outcome], x).fit(cov_type="cluster", cov_kwds={"groups": groups})
            res = {"coef": float(fit.params[sig]), "t": float(fit.tvalues[sig]), "n": len(d),
                   "firms": int(d["cik"].nunique()), "years": int(d["year"].nunique()),
                   "outcome_mean": float(d[outcome].mean())}
            results[f"{sig}->{outcome}"] = res
            ledger.log_trial("H4", {"signal": sig, "outcome": outcome}, "development", res,
                             inputs=[PAIRS, OUT, SAMPLE])
    out = {"note": "Development period (10-Ks accepted 2012-2018) only. Primary: change_n -> d_roa; "
                   "expected sign: negative for d_roa, positive for decline and impair_next.",
           "results": results}
    (PROJECT_ROOT / "results" / "h4_development.json").write_text(json.dumps(out, indent=2))
    json.dump(out, sys.stdout, indent=2)


def main() -> None:
    stages = sys.argv[1:]
    for name in stages:
        globals()[f"stage_{name}"]()


if __name__ == "__main__":
    main()
