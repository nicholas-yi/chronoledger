"""Calibrate the claim-match threshold on synthetic pairs (no returns involved).

Compares raw vs centered ChronoBERT embeddings by ROC AUC and best balanced accuracy, then saves
the centering mean and threshold. The centering mean is estimated on paragraphs held out from the
calibration pairs.
"""

from __future__ import annotations

import json
import random
import sys

import numpy as np

from asof import store
from asof.changes import calibrate_tau, calibration_pairs, center, paragraphs
from asof.chrono import embed
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.edgar import EdgarClient
from asof.sections import extract_sections, html_to_text

MODEL = "manelalab/chrono-bert-v1-20221231"


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos, neg = scores[labels == 1], scores[labels == 0]
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main(n_pairs: int = 200, n_mean: int = 400, seed: int = 0) -> None:
    con = store.connect(str(DATA_DIR / "pilot.duckdb"))
    client = EdgarClient()
    rows = con.execute(
        "SELECT cik, accession, primary_doc FROM filings WHERE form='10-K' "
        "AND knowledge_time BETWEEN '2012-01-01' AND '2022-12-31'"
    ).fetchall()
    by_firm: dict[int, list[str]] = {}
    for cik, acc, doc in rows:
        sec = extract_sections(html_to_text(client.filing_document(cik, acc, doc))).get("1A")
        if sec:
            by_firm.setdefault(cik, []).extend(paragraphs(sec.text))
    rng = random.Random(seed)
    pool = [p for ps in by_firm.values() for p in ps]
    rng.shuffle(pool)
    mean_paras = pool[:n_mean]
    held = set(mean_paras)
    calib_firms = {f: [p for p in ps if p not in held] for f, ps in by_firm.items()}

    pairs = calibration_pairs(calib_firms, n_pairs, seed=seed)
    a = embed([p[0] for p in pairs], MODEL)
    b = embed([p[1] for p in pairs], MODEL)
    labels = np.array([p[2] for p in pairs])
    mean = embed(mean_paras, MODEL).mean(axis=0)

    raw = (a * b).sum(1)
    cen = (center(a, mean) * center(b, mean)).sum(1)
    tau_raw, bal_raw = calibrate_tau(raw, labels)
    tau_cen, bal_cen = calibrate_tau(cen, labels)
    result = {
        "model": MODEL, "n_pairs": len(pairs), "n_mean": len(mean_paras), "firms": len(by_firm),
        "raw": {"auc": auc(raw, labels), "tau": tau_raw, "balanced_accuracy": bal_raw,
                "mean_sim_pos": float(raw[labels == 1].mean()), "mean_sim_neg": float(raw[labels == 0].mean())},
        "centered": {"auc": auc(cen, labels), "tau": tau_cen, "balanced_accuracy": bal_cen,
                     "mean_sim_pos": float(cen[labels == 1].mean()), "mean_sim_neg": float(cen[labels == 0].mean())},
    }
    out = PROJECT_ROOT / "results" / "change_calibration.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    np.save(DATA_DIR / "centering_mean_20221231.npy", mean)
    json.dump(result, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
