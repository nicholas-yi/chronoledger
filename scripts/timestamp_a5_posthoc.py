"""POST-HOC sensitivity for A5 (labelled; not qualification and not a rule change).

Written after the A5 report: its frozen CB1 replication failed only the integrity sub-check,
because two of 152 older headers were accepted 12 and 44 seconds after 22:00 ET (both with
correctly rolled filing dates). This asks the practical question under the Eastern reading the
replication otherwise supported (39/39, 22/22, 0/124): would any H6a development indicator,
year, window or H4 10-K order change? Header+index pairs use the header time; the 110 accessions
whose older header page is missing use the index ``Accepted`` time alone.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

import pandas as pd
import run_timestamp_a5 as a5

from asof.config import PROJECT_ROOT
from asof.runtime import frozen_receipt, write_receipt
from asof.timeutil import parse_header_acceptance_et

RECEIPT = PROJECT_ROOT / "results" / "timestamp_a5_posthoc_sensitivity.json"


def main() -> None:
    if RECEIPT.exists():
        raise RuntimeError("already recorded")
    freeze = frozen_receipt(PROJECT_ROOT, ("scripts/timestamp_a5_posthoc.py", "scripts/run_timestamp_a5.py"))
    rows: dict[str, dict] = {}
    for row in a5.base.load_lines(a5.OUTCOMES):
        rows.setdefault(row["accession"], {})[row["kind"]] = row
    times, sources, offsets = {}, Counter(), Counter()
    for accession, pair in rows.items():
        header, index = pair.get("header"), pair.get("index")
        stored = datetime.fromisoformat((header or index)["stored_time"])
        wall, source = None, None
        if header and "unknown" not in header["parsed"]:
            wall, source = header["parsed"]["header_wall"], "header"
            if index and "unknown" not in index["parsed"] and index["parsed"]["index_wall"] != wall:
                sources["header_index_conflict"] += 1
                continue
        elif index and "unknown" not in index["parsed"]:
            wall, source = index["parsed"]["index_wall"], "index_only"
        if wall is None:
            sources["unread"] += 1
            continue
        try:
            moment = parse_header_acceptance_et(wall)
        except ValueError:
            sources["ambiguous_or_nonexistent_eastern_wall"] += 1
            continue
        sources[source] += 1
        offsets[str((stored - moment).total_seconds() / 3600)] += 1
        times[accession] = pd.Timestamp(moment)
    filings = a5.load_filings()
    sample = set(pd.read_parquet(a5.SAMPLE)["cik"])
    f = filings[filings["cik"].isin(sample)]
    subset = f[f["cik"].isin(set(f.loc[f["accession"].isin(times), "cik"]))]
    before, after = a5.h6a_state(subset, {}), a5.h6a_state(subset, times)
    dev = before["in_dev"] | after["in_dev"]
    changed = {c: int(((before[c] != after[c]) & dev).sum()) for c in before.columns}
    write_receipt(RECEIPT, {
        "label": "POST-HOC sensitivity, written after the A5 report; not qualification", **freeze,
        "rationale": __doc__.strip(), "time_sources": dict(sources),
        "stored_minus_eastern_hours": dict(offsets),
        "H6a_development_changes_if_eastern": changed,
        "H6a_development_rows_changed_if_eastern": int(((before != after).any(axis=1) & dev).sum()),
    })
    print(RECEIPT.read_text())


if __name__ == "__main__":
    main()
