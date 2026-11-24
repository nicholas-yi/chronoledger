"""Run the neologism leakage probe across ChronoBERT vintages bracketing each term's first use."""

from __future__ import annotations

import json
import sys

from asof.config import PROJECT_ROOT
from asof.leakprobe import run

V = "manelalab/chrono-bert-v1-{}1231"
VINTAGES = {
    "COVID": [V.format(y) for y in (2018, 2019, 2020)],
    "coronavirus": [V.format(y) for y in (2018, 2019, 2020)],
    "Omicron": [V.format(y) for y in (2019, 2020, 2021)],
    "ChatGPT": [V.format(y) for y in (2020, 2021, 2022)],
    "Brexit": [V.format(y) for y in (2010, 2011, 2016)],
    "Mounjaro": [V.format(y) for y in (2021, 2022)],
    "Kenvue": [V.format(y) for y in (2021, 2022)],
    "Solventum": [V.format(y) for y in (2022, 2023)],
    "Qnity": [V.format(y) for y in (2022, 2023, 2024)],
}


def main() -> None:
    results = run(VINTAGES)
    rows = [r.__dict__ for r in results]
    out = PROJECT_ROOT / "results" / "leakprobe_chronobert.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    for r in results:
        flag = "LEAK?" if r.before_first_use and r.context == "evoking" and r.first_rank <= 10 else ""
        print(f"{r.term:<12} {r.vintage} before={r.before_first_use!s:<5} {r.context:<8} "
              f"rank={r.first_rank:<6} mean_logp={r.mean_logprob:7.2f} {flag}", file=sys.stdout)


if __name__ == "__main__":
    main()
