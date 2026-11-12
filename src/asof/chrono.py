"""Chronologically consistent text representations with ChronoBERT (He, Lv, Manela & Wu 2025).

A filing accepted at time t is embedded with the latest ChronoBERT vintage whose training cutoff is
strictly before t's calendar date, so the representation contains no text written after the
filing became public. Vintages are year-end snapshots, 1999-12-31 through 2024-12-31 (MIT).
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

import numpy as np

FIRST_VINTAGE_YEAR = 1999
LAST_VINTAGE_YEAR = 2024


def vintage_for(knowledge_time: datetime) -> str:
    if knowledge_time.tzinfo is None:
        raise ValueError("knowledge_time must be timezone-aware")
    day = knowledge_time.date()
    year = day.year - 1  # the Dec-31 cutoff of the previous year is strictly before `day`
    if year < FIRST_VINTAGE_YEAR:
        raise ValueError(f"no ChronoBERT vintage before {day}")
    year = min(year, LAST_VINTAGE_YEAR)
    cutoff = date(year, 12, 31)
    assert cutoff < day
    return f"manelalab/chrono-bert-v1-{cutoff:%Y%m%d}"


@lru_cache(maxsize=3)
def _load(model_id: str):
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id, torch_dtype=torch.float32).eval()
    return tok, model


def embed(texts: list[str], model_id: str, max_tokens: int = 512, batch: int = 8) -> np.ndarray:
    """Mean-pooled, L2-normalized last-layer embeddings."""
    import torch

    tok, model = _load(model_id)
    out = []
    with torch.inference_mode():
        for i in range(0, len(texts), batch):
            enc = tok(texts[i:i + batch], padding=True, truncation=True,
                      max_length=max_tokens, return_tensors="pt")
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1.0)
            out.append(torch.nn.functional.normalize(pooled, dim=-1).numpy())
    return np.vstack(out) if out else np.zeros((0, 768))
