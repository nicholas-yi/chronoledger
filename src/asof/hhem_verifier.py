"""Pinned local HHEM advisory benchmark; no transport, training, human review or source retrieval."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import time
from pathlib import Path

MODEL_REVISION = "de9a5e6ba9ba49531a022dba17e35ffeb2a6fad8"
FOUNDATION_REVISION = "7bcac572ce56db69c1ea7c8af255c5d7c9672fc2"
THRESHOLD = 0.5


def fixture() -> tuple[dict, ...]:
    definitions = (
        ("value", "FictionPoppy reported revenue of 18 USD million for 2017.",
         "FictionPoppy reported revenue of 18 USD million for 2017.",
         "FictionPoppy reported revenue of 81 USD million for 2017."),
        ("year", ("Company: FictionQuartz.\n| Item | 2016 (USD million) | 2017 (EUR thousand) |\n"
                  "| Revenue | 63 | 28.5 |"),
         "FictionQuartz's 2017 revenue was 28.5 EUR thousand.",
         "FictionQuartz's 2017 revenue was 63 USD million."),
        ("currency", "FictionReed reported revenue of 21 EUR million for 2018.",
         "FictionReed reported revenue of 21 EUR million for 2018.",
         "FictionReed reported revenue of 21 USD million for 2018."),
        ("scale", "Company: FictionSpruce. Amounts in USD thousand.\n| Item | 2018 |\n| Revenue | 25 |",
         "FictionSpruce's 2018 revenue was 25 USD thousand.",
         "FictionSpruce's 2018 revenue was 25 USD million."),
        ("sign", ("FictionTamarack reported operating income of (14) USD million for 2017. "
                  "Parentheses denote a negative amount."),
         "FictionTamarack's 2017 operating income was negative 14 USD million.",
         "FictionTamarack's 2017 operating income was positive 14 USD million."),
        ("entity", ("FictionUmber reported revenue of 31 USD million for 2018. "
                    "Its customer FictionViolet reported revenue of 45 USD million for 2018."),
         "FictionUmber's 2018 revenue was 31 USD million.",
         "FictionUmber's 2018 revenue was 45 USD million."),
        ("definition", ("FictionWillow reported gross margin of 12 percent for 2017. "
                        "Its operating margin was 7 percent for 2017."),
         "FictionWillow's 2017 gross margin was 12 percent.",
         "FictionWillow's 2017 gross margin was 7 percent."),
        ("scope", ("FictionXylem reported consolidated revenue of 70 USD million for 2018. "
                   "Its north segment revenue was 20 USD million."),
         "FictionXylem's 2018 consolidated revenue was 70 USD million.",
         "FictionXylem's 2018 consolidated revenue was 20 USD million."),
        ("basis", ("For 2018, FictionYarrow reported GAAP operating income of 13 USD million "
                   "and non-GAAP operating income of 19 USD million."),
         "FictionYarrow's 2018 GAAP operating income was 13 USD million.",
         "FictionYarrow's 2018 GAAP operating income was 19 USD million."),
        ("denominator", ("FictionZircon reported diluted earnings per share of 1.25 USD per share "
                         "for 2018. Basic earnings per share was 1.40 USD per share."),
         "FictionZircon's 2018 diluted earnings per share was 1.25 USD per share.",
         "FictionZircon's 2018 diluted earnings per share was 1.40 USD per share."),
        ("footnote", ("Company: FictionAcorn, fiscal 2017. Default units: USD million.\n"
                      "| Revenue (b) | 33 |\n(b) Revenue alone is stated in EUR thousand."),
         "FictionAcorn's 2017 revenue was 33 EUR thousand.",
         "FictionAcorn's 2017 revenue was 33 USD million."),
        ("correction", ("Original: FictionBramble reported revenue of 40 EUR million for 2018. "
                        "Correction: FictionBramble reported revenue of 44 EUR million for 2018. "
                        "This correction supersedes the original amount."),
         "FictionBramble's corrected 2018 revenue was 44 EUR million.",
         "FictionBramble's corrected 2018 revenue was 40 EUR million."),
    )
    return tuple({
        "id": f"HHEM-{i:02d}-{member}", "category": category, "source": source, "claim": claim,
        "expected_supported": member == 0,
    } for i, (category, source, positive, negative) in enumerate(definitions, 1)
                 for member, claim in enumerate((positive, negative)))


def summarize(rows: list[dict]) -> dict:
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows) or not set(by_id) <= {case["id"] for case in fixture()}:
        raise ValueError("unexpected or duplicate verifier case identities")
    correct = false_support = false_rejection = invalid = 0
    for case in fixture():
        row = by_id.get(case["id"])
        if row is None:
            continue
        score = row.get("support_score")
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            invalid += 1
            continue
        predicted = score >= THRESHOLD
        correct += predicted == case["expected_supported"]
        false_support += predicted and not case["expected_supported"]
        false_rejection += not predicted and case["expected_supported"]
    return {
        "planned": len(fixture()), "recorded": len(rows), "correct": correct,
        "not_attempted": len(fixture())-len(rows), "invalid": invalid,
        "false_support": false_support, "false_rejection": false_rejection,
        "fixed_threshold": THRESHOLD, "threshold_tuned_on_results": False,
        "independent_gold": False, "promote": False,
        "abstention_answerability_evaluated": False,
        "refusal_policy": "No claim -> no entailment verdict; human/source coverage review required.",
    }


def verify_assets(root: Path) -> dict:
    receipt = json.loads((root / "results" / "hhem_assets.json").read_bytes())
    if receipt["model_revision"] != MODEL_REVISION or receipt["foundation_revision"] != FOUNDATION_REVISION:
        raise ValueError("unexpected verifier artifact revision")
    for row in receipt["artifacts"]:
        path = root / "data" / "hhem_assets_v1" / row["relative_path"]
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1 << 20):
                digest.update(chunk)
        if path.stat().st_size != row["size"] or digest.hexdigest() != row["sha256"]:
            raise ValueError(f"verifier artifact content changed: {row['relative_path']}")
    return receipt


def benchmark(root: Path, emit) -> dict:
    """Run only after the external worker's owned-Job gate; all model loads are local-only."""
    import torch
    from transformers import AutoConfig, AutoModelForSequenceClassification

    verify_assets(root)
    if importlib.metadata.version("transformers") != "4.57.6" or torch.__version__ != "2.9.1+cpu":
        raise ValueError("verifier dependency versions differ from fixed CPU allocation")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    started = time.monotonic()
    directory = root / "data" / "hhem_assets_v1"
    config = AutoConfig.from_pretrained(directory / "hhem", trust_remote_code=True,
                                       local_files_only=True)
    config.foundation = str(directory / "foundation")
    model = AutoModelForSequenceClassification.from_pretrained(
        directory / "hhem", config=config, trust_remote_code=True, use_safetensors=True,
        local_files_only=True).to("cpu").eval()
    load_seconds = time.monotonic()-started
    emit({"kind": "loaded", "load_seconds": load_seconds, "device": str(model.device),
          "torch_threads": torch.get_num_threads()})
    rows = []
    for case in fixture():
        before = time.monotonic()
        emit({"kind": "case_started", "id": case["id"]})
        text = model.prompt.format(text1=case["source"], text2=case["claim"])
        inputs = model.tokenzier(text, return_tensors="pt", truncation=False)
        count = inputs["input_ids"].shape[1]
        if count > 2048:
            raise ValueError("verifier input exceeds explicit2048tokencap; no truncation")
        with torch.inference_mode():
            score = torch.softmax(model(**inputs).logits, dim=-1)[0, 1].item()
        row = {"id": case["id"], "support_score": score, "input_tokens": count,
               "latency_seconds": time.monotonic()-before}
        rows.append(row)
        emit({"kind": "case", "row": row})
    return {
        "status": "complete_invented_entailment_benchmark", "rows": rows, "summary": summarize(rows),
        "load_seconds": load_seconds, "worker_seconds": time.monotonic()-started,
        "dependencies": {name: importlib.metadata.version(name)
                         for name in ("torch", "transformers", "safetensors", "tokenizers", "numpy")},
        "no_training": True, "no_human_gold": True,
    }
