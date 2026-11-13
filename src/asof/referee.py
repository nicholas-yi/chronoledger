"""Socratic referee: a strict, executable gate on every claimed result.

Adapted from the structure of Jane Street's open-source ``socratic-tutor`` agent skill (MIT):
its skill map becomes a threat map, levels are earned only through independent checks, and
"find the flaw in a plausible-but-wrong claim" becomes mutation (canary) checks. Questions are
answered by code, never by model opinion.

Levels per threat:
  0  no checks run
  1  at least one check failed (capped until fixed)
  2  one independent check passed
  4  >= 2 independent checks passed, none failed
  5  level 4 plus a passing mutation check (a planted bug was caught)

A result may enter the README only if every threat is at level >= 4.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from asof.config import DATA_DIR, PROJECT_ROOT


@dataclass
class Check:
    name: str
    fn: Callable[[], tuple[bool, str]]
    mutation: bool = False


@dataclass
class Threat:
    tid: str
    question: str
    checks: list[Check] = field(default_factory=list)
    gating: bool = True


@dataclass
class Outcome:
    tid: str
    question: str
    level: int
    results: list[tuple[str, bool, str, bool]]
    gating: bool = True


def level(results: list[tuple[str, bool, str, bool]]) -> int:
    if not results:
        return 0
    if any(not ok for _, ok, _, _ in results):
        return 1
    independent = [r for r in results if not r[3]]
    if len(independent) < 2:
        return 2
    return 5 if any(r[3] for r in results) else 4


def evaluate(threats: list[Threat]) -> list[Outcome]:
    out = []
    for t in threats:
        results = []
        for c in t.checks:
            try:
                ok, evidence = c.fn()
            except Exception as exc:  # a crashing check is a failed check
                ok, evidence = False, f"error: {exc!r}"
            results.append((c.name, ok, evidence, c.mutation))
        out.append(Outcome(t.tid, t.question, level(results), results, t.gating))
    return out


def render(outcomes: list[Outcome]) -> str:
    lines = ["# Referee report", ""]
    gating = [o for o in outcomes if o.gating]
    gate = all(o.level >= 4 for o in gating)
    lines.append(f"**Gate: {'PASS' if gate else 'BLOCKED'}** (every gating threat must be at level 4 or higher)")
    lines += ["", "```"]
    for o in outcomes:
        bar = "#" * o.level + "." * (5 - o.level)
        tag = "" if o.gating else "  (known issue, non-gating)"
        lines.append(f"{o.tid:<34} [{bar}] {o.level}/5{tag}")
    lines += ["```", ""]
    for o in outcomes:
        suffix = "" if o.gating else " (known issue, non-gating)"
        lines += [f"## {o.tid}: level {o.level}{suffix}", "", f"*{o.question}*", ""]
        for name, ok, evidence, mutation in o.results:
            tag = "mutation" if mutation else "check"
            lines.append(f"- {'PASS' if ok else 'FAIL'} ({tag}) **{name}**: {evidence}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- concrete checks


def _store_invariance(db: Path, n: int = 10) -> tuple[bool, str]:
    from asof import store
    from asof.invariance import invariance_violation

    con = store.connect(str(db), read_only=True)
    fn = lambda c, t: store.facts_as_of(c, t)[["cik", "tag", "period_end", "value"]]  # noqa: E731
    rng = random.Random(0)
    start, end = datetime(2010, 1, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc)
    bad = 0
    for _ in range(n):
        t = start + (end - start) * rng.random()
        bad += invariance_violation(con, fn, t) is not None
    return bad == 0, f"{n} random as-of instants on {db.name}, {bad} violations"


def _store_revision_invariance(db: Path, n: int = 6) -> tuple[bool, str]:
    from asof import store
    from asof.invariance import invariance_violation

    con = store.connect(str(db), read_only=True)
    fn = lambda c, t: store.revisions_as_of(c, t)[["cik", "tag", "period_end", "value", "prev_value"]]  # noqa: E731
    rng = random.Random(1)
    start, end = datetime(2012, 1, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc)
    bad = sum(invariance_violation(con, fn, start + (end - start) * rng.random()) is not None for _ in range(n))
    return bad == 0, f"revision detection at {n} instants, {bad} violations"


def _store_canary(db: Path) -> tuple[bool, str]:
    from asof import store
    from asof.invariance import invariance_violation

    con = store.connect(str(db), read_only=True)

    def leaky(c, t):  # data treated as known at period end
        return c.execute(
            "SELECT cik, tag, period_end, value FROM xbrl_facts WHERE period_end <= CAST(? AS DATE) "
            "QUALIFY row_number() OVER (PARTITION BY cik, tag, period_end "
            "ORDER BY knowledge_time DESC, accession DESC) = 1", [t]).df()

    t = datetime(2020, 2, 5, tzinfo=timezone.utc)
    caught = invariance_violation(con, leaky, t) is not None
    return caught, "planted period-end look-ahead bug " + ("was caught" if caught else "was NOT caught")


def _reconcile_invariance() -> tuple[bool, str]:
    from asof.extraction import Link
    from asof.reconcile import FilingEvent, reconcile

    rng = random.Random(2)
    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bad = 0
    for trial in range(200):
        events, originals = [], []
        for i in range(rng.randint(1, 20)):
            d = t0 + timedelta(days=rng.randint(0, 1500))
            link = Link(rng.choice(["A Co", "B Co", "C Co"]), "customer", float(rng.randint(10, 40)), "e")
            if originals and rng.random() < 0.3:
                events.append(FilingEvent(f"{trial}-{i}", 1, "10-K/A", d, (link,),
                                          amends=rng.choice(originals), restates_section=rng.random() < 0.7))
            else:
                events.append(FilingEvent(f"{trial}-{i}", 1, "10-K", d, (link,)))
                originals.append(f"{trial}-{i}")
        as_of = t0 + timedelta(days=rng.randint(0, 1600))
        a = reconcile(events, as_of)
        b = reconcile([e for e in events if e.knowledge_time <= as_of], as_of)
        bad += {k: v.support for k, v in a.links.items()} != {k: v.support for k, v in b.links.items()}
    return bad == 0, f"200 random amendment sequences, {bad} invariance violations"


def _reconcile_ablation() -> tuple[bool, str]:
    from asof.extraction import Link
    from asof.reconcile import FilingEvent, append_only, reconcile

    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    ev = [FilingEvent("a", 1, "10-K", t0, (Link("X Co", "customer", 12.0, "e"),)),
          FilingEvent("a1", 1, "10-K/A", t0 + timedelta(days=30), (), amends="a")]
    as_of = t0 + timedelta(days=60)
    retracted = not reconcile(ev, as_of).links[(1, "x", "customer")].supported
    stale = any(k == (1, "x", "customer") for k, _ in append_only(ev, as_of))
    return retracted and stale, "amendment retracts link; append-only baseline keeps the stale link"


def _vintage_rule() -> tuple[bool, str]:
    from asof.chrono import vintage_for

    rng = random.Random(3)
    bad = 0
    for _ in range(2000):
        t = datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=rng.randint(0, 27 * 365 * 86400))
        cutoff = datetime.strptime(vintage_for(t)[-8:], "%Y%m%d").date()
        bad += not cutoff < t.date()
    return bad == 0, f"2000 random acceptance times; {bad} used a vintage not strictly before the filing date"


IN_USE_VINTAGES = {"20221231", "20231231", "20241231"}  # filings from 2023 onward (deviation D1)


def _neologism_probe(path: Path, in_use_only: bool) -> tuple[bool, str]:
    """Context-specific leak (deviation D4): pre-coinage evoking rank <= 10 and control rank >= 100."""
    if not path.exists():
        return False, f"missing {path.name}; run scripts/leakprobe.py"
    rows = json.loads(path.read_text())
    control = {(r["term"], r["vintage"]): r["first_rank"] for r in rows if r["context"] == "control"}
    pre = [r for r in rows if r["before_first_use"] and r["context"] == "evoking"
           and (not in_use_only or r["vintage"] in IN_USE_VINTAGES)]
    leaks = [r for r in pre if r["first_rank"] <= 10 and control.get((r["term"], r["vintage"]), 0) >= 100]
    detail = ", ".join(f"{r['term']}@{r['vintage']} rank {r['first_rank']}" for r in leaks)
    scope = "in-use vintages" if in_use_only else "all vintages"
    return not leaks, (f"{len(leaks)}/{len(pre)} pre-coinage probes on {scope} show context-specific knowledge"
                       + (f": {detail}" if leaks else "")
                       + ("; low power: post-coinage vintages also miss rare names (docs/FINDINGS.md)"
                          if in_use_only else ""))


def _tfidf_invariance() -> tuple[bool, str]:
    import numpy as np

    from asof.changes import AsOfTfidf

    rng = random.Random(4)
    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    words = ["supply", "risk", "tariff", "cyber", "labor", "demand", "pandemic", "credit", "rate"]
    bad = 0
    for _ in range(100):
        docs = [(t0 + timedelta(days=rng.randint(0, 900)),
                 " ".join(rng.choice(words) for _ in range(rng.randint(1, 10)))) for _ in range(rng.randint(1, 25))]
        as_of = t0 + timedelta(days=rng.randint(0, 1000))
        a = AsOfTfidf(min_df=1).fit(docs, as_of)
        b = AsOfTfidf(min_df=1).fit([d for d in docs if d[0] <= as_of], as_of)
        probe = ["supply risk", "pandemic credit rate"]
        bad += a.vocab != b.vocab or not np.allclose(a.transform(probe), b.transform(probe))
    return bad == 0, f"100 random corpora, {bad} differences between full and as-of-truncated fits"


def _distress_coverage_parity(min_ratio: float = 0.8) -> tuple[bool, str]:
    """Price-universe coverage of distress-event filers relative to all 10-K filers (F2)."""
    import pandas as pd

    from asof.periods import DEV_END, DEV_START

    fpath, upath = DATA_DIR / "bulk_filings.parquet", DATA_DIR / "h0_universe.parquet"
    if not fpath.exists() or not upath.exists():
        return False, "bulk filings or universe missing"
    f = pd.read_parquet(fpath)
    uni = set(pd.read_parquet(upath)["cik"])
    lo, hi = pd.Timestamp(DEV_START, tz="UTC"), pd.Timestamp(DEV_END, tz="UTC") + pd.Timedelta(days=1)
    w = f[f["knowledge_time"].between(lo, hi)]
    items = w["items"].fillna("")

    def cov(g):
        c = set(g["cik"])
        return len(c & uni) / len(c) if c else float("nan")

    base = cov(w[w["form"] == "10-K"])
    ratios = {"NT": cov(w[w["form"].str.startswith("NT ")]) / base,
              "4.02": cov(w[(w["form"] == "8-K") & items.str.contains(r"\b4\.02\b")]) / base,
              "4.01": cov(w[(w["form"] == "8-K") & items.str.contains(r"\b4\.01\b")]) / base}
    ok = all(r >= min_ratio for r in ratios.values())
    return ok, "coverage relative to all 10-K filers: " + ", ".join(f"{k} {v:.2f}" for k, v in ratios.items()) + f" (need >= {min_ratio})"


def _as_traded_real() -> tuple[bool, str]:
    from asof.periods import DEV_RETURN_CUTOFF
    from asof.prices import YahooPrices

    df = YahooPrices().daily("AAPL", end=DEV_RETURN_CUTOFF)
    row = df[df["date"].astype(str) == "2014-06-06"]
    if row.empty:
        return False, "AAPL 2014-06-06 not in cached prices"
    close = float(row["close"].iloc[0])
    return abs(close - 645.57) < 0.05, f"AAPL as-traded close 2014-06-06 = {close:.2f} (record: 645.57)"


def _vintage_canary() -> tuple[bool, str]:
    from asof.chrono import vintage_for

    t = datetime(2023, 12, 31, 23, tzinfo=timezone.utc)
    ok = not vintage_for(t).endswith("20231231")
    return ok, "a filing on 2023-12-31 does not get the same-day 2023-12-31 vintage"


def _bench_metric(path: Path, key: str, cmp: Callable[[float], bool], label: str) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing {path.name}"
    m = json.loads(path.read_text())
    return cmp(m[key]), f"{label} = {m[key]:.3f} ({path.name})"


def _hallucination(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing {path.name}"
    m = json.loads(path.read_text())
    prior = m.get("prior_knowledge_hallucination_rate")
    if prior is None:
        return False, "benchmark predates the D2 metric; rerun scripts/run_bench.py"
    return prior < 0.02, (f"prior-knowledge {prior:.3f}; all ungrounded outputs "
                          f"{m['raw_hallucination_rate']:.3f} (stricter reading) ({path.name})")


def _grounding_canary() -> tuple[bool, str]:
    from asof.extraction import Link, ground

    chunk = "We compete with Orbique Labs."
    fabricated = Link("Apple", "customer", None, "We compete with Orbique Labs.")
    invented = Link("Orbique Labs", "customer", None, "Orbique Labs is our largest customer.")
    ok = ground(fabricated, chunk) is not None and ground(invented, chunk) is not None
    return ok, "fabricated partner and invented quote are both rejected"


def _ledger_seal() -> tuple[bool, str]:
    import tempfile

    from asof import ledger

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "l.jsonl"
        ledger.log_trial("HX", {"a": 1}, "holdout", {}, p)
        try:
            ledger.log_trial("HX", {"a": 2}, "holdout", {}, p)
        except PermissionError:
            return True, "second holdout access was refused"
    return False, "holdout could be reopened"


def _dsr_noise() -> tuple[bool, str]:
    import numpy as np

    from asof.inference import deflated_sharpe_ratio, probabilistic_sharpe_ratio

    rng = np.random.default_rng(1)
    trials = rng.normal(0, 0.05, size=(240, 500))
    srs = trials.mean(0) / trials.std(0, ddof=1)
    naive = probabilistic_sharpe_ratio(srs.max(), 240, 0.0, 3.0)
    dsr = deflated_sharpe_ratio(trials[:, int(srs.argmax())], srs)
    return naive > 0.95 and dsr < 0.95, f"best of 500 noise strategies: naive PSR {naive:.2f}, DSR {dsr:.2f}"


def _no_returns_before_deviation() -> tuple[bool, str]:
    """Every commit that first added a return output must descend from the deviation-d1 tag."""
    import subprocess

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True)

    if git("rev-parse", "deviation-d1").returncode != 0:
        return False, "tag deviation-d1 not found"
    added = git("log", "--diff-filter=A", "--format=%H", "--", "results/returns_*").stdout.split()
    early = [c for c in added if git("merge-base", "--is-ancestor", "deviation-d1", c).returncode != 0]
    uncommitted = [p.name for p in (PROJECT_ROOT / "results").glob("returns_*")
                   if git("ls-files", "--error-unmatch", str(p)).returncode != 0]
    if early:
        return False, f"{len(early)} commit(s) added return outputs before deviation D1"
    return True, (f"{len(added)} commit(s) added return outputs, all after deviation-d1"
                  + (f"; uncommitted: {', '.join(uncommitted)}" if uncommitted else ""))


def _coverage_audit_present() -> tuple[bool, str]:
    p = PROJECT_ROOT / "docs" / "DATA_AUDIT.md"
    d = PROJECT_ROOT / "docs" / "DEVIATIONS.md"
    ok = p.exists() and d.exists() and "D1" in d.read_text(encoding="utf-8")
    return ok, "coverage audit and deviation D1 are documented"


def _as_traded_unit() -> tuple[bool, str]:
    from datetime import date

    import numpy as np

    from asof.prices import as_traded_close

    out = as_traded_close([date(2020, 8, 28), date(2020, 8, 31)], np.array([124.8075, 129.04]),
                          [(date(2020, 8, 31), 4.0)])
    return abs(out[0] - 499.23) < 0.01 and out[1] == 129.04, f"AAPL 2020 split: {out[0]:.2f} / {out[1]:.2f}"


def _price_filter_canary() -> tuple[bool, str]:
    # A $5 filter on split-adjusted prices would wrongly exclude a stock that traded at $28.
    from datetime import date

    import numpy as np

    from asof.prices import as_traded_close

    adjusted = np.array([1.0])
    traded = as_traded_close([date(2010, 1, 4)], adjusted, [(date(2014, 6, 9), 7.0), (date(2020, 8, 31), 4.0)])
    return adjusted[0] < 5 <= traded[0], f"adjusted $1.00 vs as-traded ${traded[0]:.2f}"


def default_threats(db: Path | None = None, bench: Path | None = None,
                    swap: Path | None = None) -> list[Threat]:
    db = db or DATA_DIR / "pilot.duckdb"
    bench = bench or PROJECT_ROOT / "results" / "bench_qwen3.5-4b_n300_s0.json"
    swap = swap or PROJECT_ROOT / "results" / "swap_qwen3.5-4b_n160_s0.json"
    return [
        Threat("lookahead.store", "Could any fact be read before EDGAR accepted the filing?", [
            Check("invariance of as-of facts", lambda: _store_invariance(db)),
            Check("invariance of revision detection", lambda: _store_revision_invariance(db)),
            Check("planted period-end leak is caught", lambda: _store_canary(db), mutation=True),
        ]),
        Threat("lookahead.reconcile", "Can a later amendment change what was believed earlier?", [
            Check("invariance over random amendment chains", _reconcile_invariance),
            Check("retraction vs append-only ablation", _reconcile_ablation),
        ]),
        Threat("lookahead.representation", "Could the text model have read text written after the filing?", [
            Check("vintage strictly before filing date", _vintage_rule),
            Check("neologism probe on in-use vintages (2022-2024)",
                  lambda: _neologism_probe(PROJECT_ROOT / "results" / "leakprobe_chronobert.json", True)),
            Check("leak-proof TF-IDF path is time-invariant (D3)", _tfidf_invariance),
            Check("same-day vintage is refused", _vintage_canary, mutation=True),
        ]),
        Threat("lookahead.representation.all_vintages",
               "Do any ChronoBERT vintages, including unused ones, know terms coined after their cutoff?", [
            Check("neologism probe on all vintages",
                  lambda: _neologism_probe(PROJECT_ROOT / "results" / "leakprobe_chronobert.json", False)),
        ], gating=False),
        Threat("extraction.hallucination", "Does the extractor name companies the text never mentions?", [
            Check("prior-knowledge hallucination rate < 2% (definition: deviation D2)", lambda: _hallucination(bench)),
            Check("entity-swap probe: famous real partner leaked < 2%", lambda: _bench_metric(
                swap, "famous_name_leak_rate", lambda v: v < 0.02, "famous-name leak rate")),
            Check("grounding rejects fabricated links", _grounding_canary, mutation=True),
        ]),
        Threat("extraction.quality", "Would H2/H3 be driven by extraction errors rather than economics?", [
            Check("recall >= 0.80", lambda: _bench_metric(bench, "recall", lambda v: v >= 0.80, "recall")),
            Check("precision >= 0.90", lambda: _bench_metric(bench, "precision", lambda v: v >= 0.90, "precision")),
        ]),
        Threat("multiple_testing", "Is the reported edge just the best of many tries?", [
            Check("DSR rejects best-of-noise", _dsr_noise),
            Check("holdout is single-use", _ledger_seal, mutation=True),
            Check("no returns computed before deviation D1", _no_returns_before_deviation),
        ]),
        Threat("survivorship", "Are failed or acquired firms silently missing?", [
            Check("coverage audit and D1 documented", _coverage_audit_present),
            Check("no returns computed before deviation D1", _no_returns_before_deviation),
        ]),
        Threat("survivorship.distress_events [blocks H5b, H5c, H6b]",
               "Are distressed firms that later disappeared missing from event samples? (F2)", [
            Check("distress-event coverage parity >= 0.8", _distress_coverage_parity),
        ], gating=False),
        Threat("price_level_leak", "Do price filters or market caps use future split information?", [
            Check("as-traded reconstruction on AAPL 2020 split", _as_traded_unit),
            Check("as-traded close matches the historical record (real data)", _as_traded_real),
            Check("$5 filter canary", _price_filter_canary, mutation=True),
        ]),
    ]


def main() -> None:
    outcomes = evaluate(default_threats())
    report = render(outcomes)
    out = PROJECT_ROOT / "results" / "REFEREE.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
