"""Prepare a private unlabelled packet from the prior approved development derivative only."""

import argparse
import json
from pathlib import Path

from asof.reader_review import prepare


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        parser.error("--execute required for the frozen bounded derivative read")
    result = prepare(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    return 0 if result["status"].startswith("prepared_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
