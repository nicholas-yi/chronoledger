from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from asof import ledger
from asof.trial_manifest import build_manifest, co_primary_decision, inference_availability


def _entry(config, metrics=None):
    return {"hypothesis": "H0", "period": "development", "config": config,
            "config_hash": ledger.config_hash(config), "metrics": metrics,
            "logged_at": "synthetic", "lineage": {"git_commit": "synthetic"}}


def test_manifest_keeps_counts_repeats_unknown_and_failed_attempts() -> None:
    first = _entry({"variant": "v1", "purpose": "scientific"}, {"m_mean_net": 0.01})
    entries = [
        first, deepcopy(first),
        _entry({"purpose": "optimization_equivalence"}, {"equivalence_passed": True}),
        _entry({"purpose": "unrecognized"}, {"execution_status": "failed"}),
        _entry({"test": "h0_full_runtime"}, {"target_met": False}),
        _entry({"variant": "missing"}),
    ]
    before = deepcopy(entries)
    manifest = build_manifest(entries)
    assert entries == before
    assert manifest["registered_N_per_hypothesis"] == {"H0": 5}
    assert [a["purpose"] for a in manifest["attempts"]] == [
        "scientific", "repeat_vintage", "engineering", "unknown", "timing", "unknown"]
    assert manifest["attempts"][1]["previous_attempt_row"] == 1
    assert manifest["attempts"][3]["output_status"] == "failed"
    assert manifest["attempts"][-1]["output_status"] == "missing"
    assert all(a["matrix_eligibility"] == "unavailable" for a in manifest["attempts"])


def _decision(**overrides):
    args = {"monthly_t": 3.2, "event_change_t": -1.0,
            "delisting_effects": {0.0: 0.01, -0.3: 0.009, -1.0: 0.002},
            "referee_passed": True, "requires_tfidf": False, "tfidf_t": None}
    args.update(overrides)
    return co_primary_decision("H0", **args)


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({}, "supported"),
        ({"monthly_t": 2.5, "event_change_t": -1.0}, "not_supported"),
        ({"monthly_t": 1.99, "event_change_t": -4.0}, "not_supported"),
        ({"event_change_t": 4.0}, "not_supported"),
        ({"delisting_effects": {0.0: 0.01, -0.3: 0.0, -1.0: 0.01}}, "not_supported"),
        ({"referee_passed": False}, "not_supported"),
        ({"event_change_t": None}, "unavailable"),
    ],
)
def test_co_primary_is_conjunction_not_best_test_selection(overrides, status) -> None:
    decision = _decision(**overrides)
    assert decision.status == status
    if status == "supported":
        assert decision.supplementary_holm_p is not None
        assert decision.supplementary_holm_p[1] > 0.05  # supplementary, not the registered rule


def test_formal_h1_cannot_skip_tfidf_or_accept_h1n_alias() -> None:
    args = {"monthly_t": 3.2, "event_change_t": -1.0,
            "delisting_effects": {0.0: 1.0, -0.3: 1.0, -1.0: 1.0},
            "referee_passed": True, "requires_tfidf": True, "tfidf_t": 1.99}
    assert co_primary_decision("H1", **args).status == "not_supported"
    args["requires_tfidf"] = False
    with pytest.raises(ValueError, match="requires D3"):
        co_primary_decision("H1", **args)
    with pytest.raises(ValueError, match="H1n"):
        co_primary_decision("H1n", **args)


def test_inference_requires_persisted_comparable_complete_series_and_long_enough_pbo() -> None:
    frame = pd.DataFrame(np.random.default_rng(1).normal(size=(18, 2)), columns=["a", "b"])
    args = {"endpoint_kind": "monthly_net_returns", "persisted": True,
            "family_complete": True, "registered_count": 2}
    result = inference_availability(frame, **args)
    assert result["DSR"]["status"] == "available"
    assert result["PBO"]["status"] == "not_estimable"
    assert inference_availability(None, **args)["DSR"]["status"] == "unavailable"
    assert inference_availability(frame, **{**args, "endpoint_kind": "H4_regression"})[
        "DSR"]["reason"] == "incomparable_endpoint"
    assert inference_availability(frame, **{**args, "registered_count": 3})[
        "DSR"]["reason"] == "registered_family_incomplete"
    frame.loc[0, "a"] = np.nan
    assert inference_availability(frame, **args)["DSR"]["status"] == "unavailable"
