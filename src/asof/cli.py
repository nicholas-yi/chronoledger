"""Command-line entry points."""

from __future__ import annotations

import argparse
import sys

from asof import store
from asof.config import DB_PATH
from asof.edgar import EdgarClient


def ingest(ciks: list[int], db_path: str) -> None:
    client = EdgarClient()
    con = store.connect(db_path)
    try:
        for cik in ciks:
            n_filings = store.ingest_submissions(con, client.submissions(cik))
            try:
                facts = store.flatten_companyfacts(client.companyfacts(cik))
            except FileNotFoundError:
                facts = None  # filer has no XBRL data
            n_facts = store.ingest_facts(con, facts) if facts is not None else 0
            print(f"CIK {cik}: {n_filings} filings, {n_facts} facts", file=sys.stderr)
    finally:
        con.close()
        client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="asof")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ingest = sub.add_parser("ingest", help="ingest filings and XBRL facts for CIKs")
    p_ingest.add_argument("ciks", nargs="+", type=int)
    p_ingest.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args(argv)
    if args.cmd == "ingest":
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        ingest(args.ciks, args.db)


if __name__ == "__main__":
    main()
