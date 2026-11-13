"""Calibrate the TF-IDF (deviation D3) claim-match threshold on synthetic pairs; no returns involved."""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone

import numpy as np

from asof import store
from asof.changes import AsOfTfidf, calibrate_tau, calibration_pairs, paragraphs
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.edgar import EdgarClient
from asof.sections import extract_sections, html_to_text

AS_OF = datetime(2022, 12, 31, 23, 59, tzinfo=timezone.utc)


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos, neg = scores[labels == 1], scores[labels == 0]
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main(n_pairs: int = 200, seed: int = 0) -> None:
    con = store.connect(str(DATA_DIR / "pilot.duckdb"), read_only=True)
    client = EdgarClient()
    rows = con.execute(
        "SELECT cik, accession, primary_doc, knowledge_time FROM filings WHERE form='10-K' "
        "AND knowledge_time BETWEEN '2012-01-01' AND ?", [AS_OF]
    ).fetchall()
    by_firm: dict[int, list[str]] = {}
    docs: list[tuple[datetime, str]] = []
    for cik, acc, doc, kt in rows:
        sec = extract_sections(html_to_text(client.filing_document(cik, acc, doc))).get("1A")
        if sec:
            ps = paragraphs(sec.text)
            by_firm.setdefault(cik, []).extend(ps)
            docs += [(kt, p) for p in ps]
    vec = AsOfTfidf().fit(docs, AS_OF)
    pairs = calibration_pairs(by_firm, n_pairs, seed=seed)
    a = vec.transform([p[0] for p in pairs])
    b = vec.transform([p[1] for p in pairs])
    labels = np.array([p[2] for p in pairs])
    sims = (a * b).sum(1)
    tau, bal = calibrate_tau(sims, labels)
    result = {"representation": "tfidf_as_of", "as_of": AS_OF.isoformat(), "vocab": len(vec.vocab),
              "n_pairs": len(pairs), "auc": auc(sims, labels), "tau": tau, "balanced_accuracy": bal,
              "mean_sim_pos": float(sims[labels == 1].mean()), "mean_sim_neg": float(sims[labels == 0].mean())}
    out = PROJECT_ROOT / "results" / "change_calibration_tfidf.json"
    out.write_text(json.dumps(result, indent=2))
    json.dump(result, sys.stdout, indent=2)


if __name__ == "__main__":
    random.seed(0)
    main()
