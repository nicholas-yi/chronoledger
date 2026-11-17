"""Offline counts-only confidence set; does not read audit files or verify sampling."""

from __future__ import annotations

import argparse
import json

from asof.audit_cs import audit_confidence_set


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", type=int, required=True)
    parser.add_argument("--drawn", type=int, required=True)
    parser.add_argument("--errors", type=int, required=True)
    parser.add_argument("--unread", type=int, default=0, help="sampled, not unsampled, members")
    parser.add_argument("--delta", type=float, default=0.05)
    args = parser.parse_args(argv)
    try:
        result = audit_confidence_set(
            args.population, args.drawn, args.errors, args.unread, args.delta)
    except (ValueError, ArithmeticError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.summary(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
