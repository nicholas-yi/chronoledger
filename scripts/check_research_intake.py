"""Prepare draft packets or validate supplied offline receipts; never acquire data or create gold."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from asof import ledger
from asof.config import PROJECT_ROOT
from asof.research_intake import (
    ANNOTATION_FIELDS,
    RIGHTS,
    AnnotationManifest,
    FieldReceipt,
    RightsReceipt,
    SourceCaseReceipt,
    SourcePacket,
    annotation_intake,
    read_annotation_csv,
    source_intake,
)

PANEL = PROJECT_ROOT / "results" / "price_source_test_panel.json"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def templates(directory: Path) -> dict:
    if directory.exists():
        raise FileExistsError("choose a new directory; intake evidence is never overwritten")
    panel = json.loads(PANEL.read_bytes())
    directory.mkdir(parents=True)
    write_json(directory / "annotation_manifest.json", AnnotationManifest().model_dump(mode="json"))
    write_json(directory / "annotation_manifest.schema.json", AnnotationManifest.model_json_schema())
    for name in ("annotator_a.csv", "annotator_b.csv"):
        with (directory / name).open("x", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(ANNOTATION_FIELDS)
    source = SourcePacket(
        panel_SHA256=ledger.file_sha256(PANEL),
        rights={name: RightsReceipt() for name in RIGHTS},
        cases=[SourceCaseReceipt(
            case_id=case["case_id"],
            fields={name: FieldReceipt() for name in panel["required_future_sample_fields"]},
        ) for case in panel["cases"]],
    )
    write_json(directory / "source_receipts.json", source.model_dump(mode="json"))
    write_json(directory / "source_receipts.schema.json", SourcePacket.model_json_schema())
    return {
        "status": "draft_templates_created_not_qualified",
        "annotation_rows": 0, "source_cases": len(source.cases),
        "data_acquired": False, "gold_created": False, "scientific_acceptance": False,
        "next": "Fill approved private manifest, obtain two independent human files or documented "
                "rights/case receipts; then use annotations/source validation. Never paste raw "
                "vendor price tables into the metadata receipt packet.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("templates")
    prepare.add_argument("--directory", type=Path, required=True)
    human = sub.add_parser("annotations")
    human.add_argument("--manifest", type=Path, required=True)
    human.add_argument("--annotators", type=Path, nargs=2, required=True)
    human.add_argument("--output", type=Path)
    source = sub.add_parser("source")
    source.add_argument("--packet", type=Path, required=True)
    source.add_argument("--output", type=Path)
    args = parser.parse_args()
    result: dict
    try:
        if args.command == "templates":
            result = templates(args.directory)
            exit_code = 0
        elif args.command == "annotations":
            manifest = AnnotationManifest.model_validate_json(args.manifest.read_bytes())
            files = [read_annotation_csv(p) for p in args.annotators]
            result = asdict(annotation_intake(manifest, files))
            result["input_SHA256"] = {
                "manifest": ledger.file_sha256(args.manifest),
                **{f"annotator_file_{i}": ledger.file_sha256(p)
                   for i, p in enumerate(args.annotators, 1)},
            }
            exit_code = 2 if result["status"] == "blocked" else 0
        else:
            packet = SourcePacket.model_validate_json(args.packet.read_bytes())
            panel = json.loads(PANEL.read_bytes())
            result = asdict(source_intake(
                packet, case_actions={c["case_id"]: c["action_type"] for c in panel["cases"]},
                required_fields=panel["required_future_sample_fields"],
                panel_digest=ledger.file_sha256(PANEL)))
            result["input_SHA256"] = {
                "packet": ledger.file_sha256(args.packet), "panel": ledger.file_sha256(PANEL)}
            exit_code = 2 if result["status"] == "blocked" else 0
        output = getattr(args, "output", None)
        if output:
            write_json(output, result)
    except ValidationError as exc:
        result = {"status": "blocked", "scientific_acceptance": False,
                  "input_errors": [{"location": e["loc"], "type": e["type"]}
                                   for e in exc.errors(include_input=False, include_url=False)]}
        exit_code = 2
    except (OSError, ValueError) as exc:
        result = {"status": "blocked", "scientific_acceptance": False,
                  "input_error": str(exc)}
        exit_code = 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
