"""Command-line entry points."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from pathlib import Path

from asof import store
from asof.bulk import FrozenFactWindow, filter_submissions, load_fact_window, require_fact_window
from asof.config import DB_PATH
from asof.edgar import EdgarClient
from asof.periods import HoldoutAccessError


def ingest(ciks: list[int], db_path: str, *, scope: FrozenFactWindow | None = None) -> None:
    scope = require_fact_window(scope)
    if not ciks or any(isinstance(cik, bool) or not isinstance(cik, int) or cik <= 0 for cik in ciks):
        raise ValueError("positive integer CIKs required")
    with ExitStack() as cleanup:
        client = EdgarClient()
        cleanup.callback(client.close)
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        con = store.connect(db_path)
        cleanup.callback(con.close)
        for cik in ciks:
            submissions, submission_scope = filter_submissions(client.submissions(cik), scope)
            n_filings = store.ingest_submissions(con, submissions)
            try:
                scoped = client.companyfacts(cik, scope=scope)
            except FileNotFoundError:
                scoped = None
                print(f"CIK {cik}: companyfacts unavailable (404); no facts ingested", file=sys.stderr)
            n_facts = store.ingest_facts(con, store.flatten_companyfacts(scoped)) if scoped else 0
            print(json.dumps({
                "cik": cik, "filings": n_filings, "facts": n_facts,
                "submission_scope": submission_scope,
                "fact_scope": scoped["_scope_filter"] if scoped else None,
            }), file=sys.stderr)


def check_claim(source_path: Path, claim: str) -> dict:
    """Decide one claim from one source file with the deterministic rules; no model is called."""
    from asof.claim_verifier import verify_claim
    from asof.text_normalization import normalize_filing_text

    source, changes = normalize_filing_text(source_path.read_text(encoding="utf-8"))
    return {**verify_claim(source, claim), "source_normalization": changes}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="asof")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ingest = sub.add_parser("ingest", help="ingest filings and XBRL facts for CIKs")
    p_ingest.add_argument("ciks", nargs="+", type=int)
    p_ingest.add_argument("--db", default=str(DB_PATH))
    p_ingest.add_argument("--scope-file", type=Path, help="frozen development date-window JSON")
    sub.add_parser("demo", help="run an invented, dataset-free example; no network or data writes")
    p_claim = sub.add_parser(
        "check-claim", help="decide supported/contradicted/review for a claim against a source file")
    p_claim.add_argument("source", type=Path, help="UTF-8 text of the source passage")
    p_claim.add_argument("claim", help='e.g. "Contoso reported revenue of 18 USD million for 2017."')
    args = parser.parse_args(argv)
    if args.cmd == "ingest":
        try:
            scope = load_fact_window(args.scope_file)
        except (HoldoutAccessError, ValueError, TypeError, OSError) as exc:
            parser.error(str(exc))
        ingest(args.ciks, args.db, scope=scope)
    elif args.cmd == "demo":
        from asof.demo import demo

        print(json.dumps(demo(), indent=2, allow_nan=False))
    elif args.cmd == "check-claim":
        print(json.dumps(check_claim(args.source, args.claim), indent=2))


if __name__ == "__main__":
    main()
