"""Create new blank supplemental forms from the public preparation receipt; never open excerpts."""

import argparse
import json
from pathlib import Path

from asof.reader_review_context import write_templates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-blank", action="store_true", required=True)
    args = parser.parse_args(argv)
    if not args.prepare_blank:
        parser.error("--prepare-blank required")
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "results" / "reader_review_packet.json").read_bytes())
    if (receipt["status"] != "prepared_unlabelled_not_independently_reviewed"
            or receipt["item_count"] != 12):
        raise ValueError("expected prior twelve-item private packet preparation receipt")
    paths = write_templates(root / "data" / "reader_review_context_v1",
                            item_count=receipt["item_count"], packet_sha256=receipt["packet_sha256"])
    print(json.dumps({"status": "blank_forms_only_no_source_read", "gold_labels": 0,
                      "forms": [str(path) for path in paths], "rows_per_form": 72}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
