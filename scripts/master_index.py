"""Rebuild the 2011-present EDGAR master index without retaining all quarters in memory."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from asof.config import DATA_DIR
from asof.edgar import EdgarClient
from asof.universe import master_index


def build(client: EdgarClient, output: Path, through: datetime) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    current_quarter = (through.month - 1) // 3 + 1
    writer = None
    try:
        for year in range(2011, through.year + 1):
            last_quarter = current_quarter if year == through.year else 4
            for quarter in range(1, last_quarter + 1):
                frame = master_index(client, year, quarter)
                table = pa.Table.from_pandas(frame, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary, table.schema)
                writer.write_table(table)
                print(f"master index: {year} Q{quarter}, {len(frame)} filings",
                      file=sys.stderr, flush=True)
    finally:
        if writer is not None:
            writer.close()
    temporary.replace(output)


def main() -> None:
    through = datetime.now(UTC)
    client = EdgarClient()
    try:
        build(client, DATA_DIR / f"master_index_2011_{through.year}.parquet", through)
    finally:
        client.close()


if __name__ == "__main__":
    main()
