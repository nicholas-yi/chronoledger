"""Print exposed invented regression matrix; no model, real-source or historical-result reads."""

import json
from pathlib import Path

from asof.reader_regression import regression_matrix


def main():
    matrix = regression_matrix(Path(__file__).resolve().parents[1])
    print(json.dumps(matrix, indent=2))
    return int(any(row["correct"] != row["planned"] for row in matrix["cohorts"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
