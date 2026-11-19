"""Check local documentation/index references without opening results or research data."""

from __future__ import annotations

import argparse
from pathlib import Path

from asof.repository import check_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    errors = check_repository(args.root)
    for error in errors:
        print(error)
    if not errors:
        print("Local documentation targets and curated project index passed; no result/data payloads read.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
