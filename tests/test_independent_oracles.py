"""Applicable synthetic cases from CL-ORACLES-20261113-R1, not empirical gold."""

import json

import pytest

from asof import ledger, trial_manifest


@pytest.mark.parametrize(
    ("monthly", "directed_event", "scenario", "tfidf", "expected"),
    [
        (3.3, -0.1, 1.0, 2.1, "not_supported"),  # P3-D01
        (3.1, 3.1, 1.0, 2.1, "not_supported"),  # D02
        (3.3, 0.4, -1.0, 2.1, "not_supported"),  # D03
        (3.3, 0.4, 1.0, None, "unavailable"),  # D04: undetermined
        (2.9, 3.3, 1.0, 2.1, "not_supported"),  # D05
        (3.2, 0.1, 1.0, 2.1, "supported"),  # D06: predicate only
        (3.3, 0.4, -1.0, None, "not_supported"),  # D07
        (3.3, 0.0, 1.0, 2.1, "not_supported"),  # D08
        (3.1, 3.3, 1.0, 2.1, "supported"),  # D09
        (3.3, 0.4, 1.0, 2.1, "supported"),  # D10: Holm supplementary
    ],
)
def test_p3_d01_d10(monthly, directed_event, scenario, tfidf, expected) -> None:
    result = trial_manifest.registered_co_primary_decision(
        "H1", monthly_t=monthly, event_change_t=-directed_event,
        delisting_effects={0.0: 1.0, -0.3: 1.0, -1.0: scenario},
        referee_passed=True, requires_tfidf=True, tfidf_t=tfidf,
    )
    assert result.status == expected


def _entry(digest, **config):
    return {"hypothesis": "H0", "period": "development", "config_hash": digest,
            "config": config, "metrics": {}, "logged_at": "synthetic"}


def test_p3_m03_missing_purpose_is_unresolved_not_inferred_scientific() -> None:
    result = trial_manifest.build_manifest([_entry("A"), _entry("B", purpose="scientific")])
    assert result["registered_N_per_hypothesis"]["H0"] == 2
    assert result["attempts"][0]["purpose"] == "unknown"


def test_p3_m04_preserves_vintages_without_equivalence_or_latest_selection() -> None:
    first = {**_entry("A", purpose="scientific"), "lineage": {"git_commit": "c1", "inputs": {"x": "d1"}}}
    second = {**_entry("A", purpose="scientific"), "lineage": {"git_commit": "c2", "inputs": {"x": "d2"}}}
    result = trial_manifest.build_manifest([first, second])
    assert result["registered_N_per_hypothesis"]["H0"] == 1
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["lineage"] != result["attempts"][1]["lineage"]
    assert all(r["matrix_eligibility"] == "unavailable" for r in result["attempts"])


def test_p3_m09_rejects_reduced_history_without_overwriting_registered_n(
    tmp_path, monkeypatch,
) -> None:
    results = tmp_path / "results"
    results.mkdir()
    existing = results / "trial_manifest.json"
    existing.write_text(json.dumps({"registered_N_per_hypothesis": {"H0": 3}, "attempts": []}))
    before = existing.read_bytes()
    fake_ledger = results / "trial_ledger.jsonl"
    fake_ledger.write_text("synthetic: read via stub")
    monkeypatch.setattr(ledger, "LEDGER_PATH", fake_ledger)
    monkeypatch.setattr(ledger, "read_ledger", lambda: [_entry("A"), _entry("B")])
    monkeypatch.setattr(trial_manifest, "PROJECT_ROOT", tmp_path)
    with pytest.raises(ValueError, match="registered"):
        trial_manifest.main()
    assert existing.read_bytes() == before


