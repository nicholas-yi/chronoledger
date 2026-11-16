"""Source-only TAT-QA serialization into the unchanged column-label reader interface."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal

from asof.benchmark_baseline import NUMBER, SCALE, TableInput
from asof.reader_columns import ColumnReport, Mode, answer_body, mode_body
from asof.reader_contract import Row, Unit

BANNER = re.compile(r"\bin\s+(thousand|million|billion)s?\b", re.IGNORECASE)
SCALE_UNITS: dict[str, Unit] = {
    "thousand": "thousand", "million": "million", "billion": "billion", "percent": "percent",
}


class MappingError(ValueError):
    pass


@dataclass(frozen=True)
class MappedInput:
    report: ColumnReport
    raw: TableInput
    summary: dict


def numeric_cell(text: str) -> tuple[str, str] | None:
    clean = text.strip().replace(",", "").replace("$", "").strip()
    inline = SCALE.search(clean)
    scale = inline.group(1).lower() if inline else ""
    if inline:
        clean = SCALE.sub("", clean).strip()
    if clean.endswith("%"):
        if scale:
            return None
        scale, clean = "percent", clean[:-1].strip()
    negative = clean.startswith("(") and clean.endswith(")")
    if negative:
        clean = clean[1:-1].strip()
    if NUMBER.fullmatch(clean) is None:
        return None
    value = Decimal(clean) * (-1 if negative else 1)
    if not value.is_finite():
        raise MappingError("nonfinite_source_number")
    return format(value, "f"), scale


def map_input(item: TableInput) -> MappedInput:
    if any(not isinstance(c, str) for row in item.table for c in row) or any(
        not isinstance(p, str) for p in item.paragraphs
    ):
        raise MappingError("source_cells_and_paragraphs_must_be_strings")
    banner_candidates = {m.lower() for row in item.table for c in row for m in BANNER.findall(c)}
    for paragraph in item.paragraphs:
        banner_candidates.update(m.lower() for m in BANNER.findall(paragraph))
    if len(banner_candidates) > 1:
        raise MappingError("conflicting_explicit_scale_banners")
    banner = next(iter(banner_candidates), "")
    first = item.table[0] if item.table else ()
    width = max((len(row) for row in item.table), default=0)
    labels = [f"c{j} | {first[j] if j < len(first) and first[j].strip() else '[blank source header]'}"
              for j in range(width)]
    rows = []
    counts = {"source_rows": len(item.table), "source_cells": sum(map(len, item.table)),
              "blank_cells": 0, "canonical_numeric_cells": 0, "text_cells": 0,
              "unmarked_numeric_unscaled_assumptions": 0,
              "scaled_count_prototype_limit_cells": 0}
    for i, original in enumerate(item.table):
        source_label = original[0] if original and original[0].strip() else "[blank source row label]"
        year_header = i < 3 and (
            not original[0].strip() or BANNER.search(original[0]) is not None
            or re.search(r"\byears?\b|\bfiscal\b|\bas of\b", original[0], re.IGNORECASE) is not None
        ) if original else False
        groups: dict[Unit, dict[str, str]] = {}
        for j, text in enumerate(original):
            if not text.strip():
                counts["blank_cells"] += 1
                continue
            parsed = numeric_cell(text)
            if parsed is None or (year_header and re.fullmatch(r"(?:19|20)\d{2}", text.strip())):
                unit, value = "text", text
                counts["text_cells"] += 1
            else:
                value, inline = parsed
                counts["canonical_numeric_cells"] += 1
                if inline == "percent" or re.search(r"\bpercent(?:age)?\b|%", source_label, re.IGNORECASE):
                    unit = "percent"
                elif re.search(r"\bper[\s-]+(?:common[\s-]+)?share\b|\beps\b", source_label, re.IGNORECASE):
                    unit = "USD"
                elif inline:
                    unit = SCALE_UNITS[inline]
                elif banner:
                    unit = SCALE_UNITS[banner]
                    if re.search(r"\bnumber\b|\bemployees\b|\bheadcount\b|\bshares\b", source_label, re.IGNORECASE):
                        counts["scaled_count_prototype_limit_cells"] += 1
                elif re.search(r"\byears\b|\bduration\b", source_label, re.IGNORECASE):
                    unit = "years"
                elif re.search(r"\bnumber\b|\bemployees\b|\bheadcount\b|\bshares\b", source_label, re.IGNORECASE):
                    unit = "count"
                elif re.search(r"\bratio\b", source_label, re.IGNORECASE):
                    unit = "ratio"
                else:
                    unit = "USD"
                    counts["unmarked_numeric_unscaled_assumptions"] += 1
                if unit not in ("USD", "thousand", "million", "billion", "percent",
                                "count", "years", "ratio"):
                    raise MappingError("unsupported_serialized_unit")
            groups.setdefault(unit, {})[labels[j]] = value
        for unit, values in groups.items():
            rows.append(Row(label=f"r{i}/{unit} | {source_label}", unit=unit, values=values))
    report = ColumnReport(
        question=item.question,
        monetary_banner=f"Source explicit in-units banner: {banner or 'none; unmarked numbers unscaled'}.",
        rows=rows, paragraphs=list(item.paragraphs))
    return MappedInput(report, item, {
        **counts, "mapped_typed_rows": len(rows), "banner_scale": banner,
        "limits": "Unmarked numerics explicitly assumed unscaled USD for prototype units; "
                  "scaled counts use scale unit and may fail dimension checks. Not unit authority."})


def user_payload(mapped: MappedInput) -> str:
    return json.dumps({
        **mapped.report.model_dump(),
        "original_table": mapped.raw.table,
        "serialization_note": (
            "The complete original table is included, unchanged. Rows above are typed groups "
            "of its source cells, not new facts. rN/unit labels locate original row N; cN labels "
            "locate original column N and retain its first-row header (blank explicitly marked). "
            "Multiple typed groups can share an original row. Accounting parentheses, commas, "
            "currency and percent marks are serialized as canonical decimal strings; raw cells "
            "remain in original_table. Explicit in-thousands/millions/billions banners supply "
            "numeric scale. Unmarked numerics are explicitly assumed unscaled USD for prototype "
            "units, not certified currency facts. Blank cells are not selectable facts. Paragraphs are unchanged. "
            "Use the supplied full locator labels exactly; do not infer a date from them."),
    }, ensure_ascii=True)


def mapped_mode_body(mapped: MappedInput, model: str, options: dict) -> dict:
    body = mode_body(mapped.report, model, options)
    body["messages"][1]["content"] = user_payload(mapped)
    return body


def mapped_answer_body(mapped: MappedInput, mode: Mode, model: str, options: dict) -> dict:
    body = answer_body(mapped.report, mode, model, options)
    body["messages"][1]["content"] = user_payload(mapped)
    return body
