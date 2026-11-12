"""Run the synthetic extraction benchmark on real 10-K backgrounds.

Usage: python scripts/run_bench.py --model qwen3.5:4b --cases 300 --seed 0
Requires ASOF_USER_AGENT, a populated data/pilot.duckdb, data/master_index_*.parquet, and Ollama.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from asof import store
from asof.bench import build_cases, build_swap_cases, dump_cases, run, run_swap
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.edgar import EdgarClient
from asof.extraction import Extractor, candidate_chunks
from asof.sections import extract_sections, html_to_text


def backgrounds(db: Path) -> list[str]:
    con = store.connect(str(db), read_only=True)
    client = EdgarClient()
    rows = con.execute(
        "SELECT cik, accession, primary_doc FROM filings WHERE form='10-K' "
        "AND knowledge_time >= '2012-01-01' ORDER BY cik, knowledge_time"
    ).fetchall()
    out = []
    for cik, acc, doc in rows:
        sections = extract_sections(html_to_text(client.filing_document(cik, acc, doc)))
        for sec in sections.values():
            out += candidate_chunks(sec.text, max_chars=1200)
    return [b for b in out if len(b) > 200]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:4b")
    ap.add_argument("--cases", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--db", default=str(DATA_DIR / "pilot.duckdb"))
    ap.add_argument("--swap", type=int, default=0, help="number of entity-swap probe cases")
    args = ap.parse_args()

    bgs = backgrounds(Path(args.db))
    index = pd.concat(pd.read_parquet(p) for p in DATA_DIR.glob("master_index_*.parquet"))
    real_names = set(index["company"].dropna().unique())
    cases = build_cases(bgs, real_names, args.cases, seed=args.seed)
    (DATA_DIR / "bench").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "bench" / f"cases_seed{args.seed}_n{args.cases}.jsonl").write_text(dump_cases(cases))

    t = time.time()
    metrics = run(cases, Extractor(model=args.model))
    metrics.update(model=args.model, cases=args.cases, seed=args.seed,
                   backgrounds=len(bgs), seconds=round(time.time() - t, 1))
    out = PROJECT_ROOT / "results" / f"bench_{args.model.replace(':', '-')}_n{args.cases}_s{args.seed}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2))
    json.dump(metrics, sys.stdout, indent=2)

    if args.swap:
        swap_cases = build_swap_cases(bgs, real_names, args.swap, seed=args.seed)
        swap = run_swap(swap_cases, Extractor(model=args.model))
        swap.update(model=args.model, seed=args.seed)
        sout = PROJECT_ROOT / "results" / f"swap_{args.model.replace(':', '-')}_n{args.swap}_s{args.seed}.json"
        sout.write_text(json.dumps(swap, indent=2))
        json.dump(swap, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
