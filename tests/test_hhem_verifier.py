import importlib.util
import io
import math
from pathlib import Path

import pytest

from asof.hhem_verifier import fixture, summarize


def test_frozen_claim_benchmark_has_balanced_supported_and_corrupted_pairs():
    cases = fixture()
    assert len(cases) == len({row["id"] for row in cases}) == 24
    assert sum(row["expected_supported"] for row in cases) == 12
    assert len({row["category"] for row in cases}) == 12
    for positive, negative in zip(cases[::2], cases[1::2], strict=True):
        assert positive["source"] == negative["source"]
        assert positive["claim"] != negative["claim"]


def test_advisory_scoring_keeps_false_support_misses_and_invalids_in_denominators():
    cases = fixture()
    rows = [{"id": row["id"], "support_score": 0.9} for row in cases]
    score = summarize(rows)
    assert score["correct"] == 12 and score["false_support"] == 12
    assert score["false_rejection"] == 0 and not score["promote"]
    rows[0]["support_score"] = math.nan
    assert summarize(rows)["invalid"] == 1
    assert summarize([{"id": cases[0]["id"], "support_score": None}])["invalid"] == 1
    assert summarize([])["not_attempted"] == 24
    with pytest.raises(ValueError, match="duplicate"):
        summarize([rows[0], rows[0]])
    assert not summarize(rows)["abstention_answerability_evaluated"]


def test_new_profile_keeps_original_case_id_contract_and_scores_separate():
    from asof.claim_challenge import fixture as new_fixture

    cases = new_fixture()
    rows = [{"id": row["id"], "support_score": 0.9 if row["expected_supported"] else 0.1}
            for row in cases]
    with pytest.raises(ValueError, match="unexpected"):
        summarize(rows)
    assert summarize(rows, cases)["correct"] == 24


def test_model_worker_is_gated_and_existing_attempt_refuses_before_loading(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_hhem_benchmark.py"
    spec = importlib.util.spec_from_file_location("hhem_runner_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO("invalid gate\n"))
    monkeypatch.setattr(module, "benchmark", lambda *args: pytest.fail("no imports or model calls"))
    with pytest.raises(RuntimeError, match="handshake"):
        module.worker()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "hhem_benchmark.json").write_text("{}")
    with pytest.raises(FileExistsError, match="noautomaticretry"):
        module.run(Path("unused"))
    (tmp_path / "results" / "hhem_structured.json").write_text("{}")
    with pytest.raises(FileExistsError, match="noautomaticretry"):
        module.run(Path("unused"), "structured")
