from asof.referee import Check, Threat, evaluate, level, render


def test_levels() -> None:
    assert level([]) == 0
    assert level([("a", True, "", False)]) == 2
    assert level([("a", True, "", False), ("b", True, "", False)]) == 4
    assert level([("a", True, "", False), ("b", True, "", False), ("m", True, "", True)]) == 5
    assert level([("a", True, "", False), ("b", False, "", False)]) == 1
    # A mutation check alone does not count as independent evidence.
    assert level([("a", True, "", False), ("m", True, "", True)]) == 2


def test_crashing_check_fails_and_gate_blocks() -> None:
    def boom():
        raise RuntimeError("x")

    out = evaluate([Threat("t", "q?", [Check("ok", lambda: (True, "")), Check("boom", boom)])])
    assert out[0].level == 1
    assert "BLOCKED" in render(out)


def test_gate_passes_when_all_threats_at_four() -> None:
    ok = lambda: (True, "fine")  # noqa: E731
    out = evaluate([Threat("t", "q?", [Check("a", ok), Check("b", ok)])])
    assert "Gate: PASS" in render(out)


def test_empty_or_only_nongating_report_cannot_pass() -> None:
    assert "Gate: BLOCKED" in render([])
    ok = lambda: (True, "fine")
    out = evaluate([Threat("diagnostic", "q?", [Check("a", ok), Check("b", ok)], gating=False)])
    assert "Gate: BLOCKED" in render(out)


def test_known_bad_monthly_calibration_blocks_despite_a_passing_harness(tmp_path) -> None:
    import json

    from asof import referee

    path = tmp_path / "calibration.json"
    value = {"status": "complete", "harness_passed": True, "reliability": {
        f"monthly_T{t}": {"registered_NW6": {"status": "unreliable_at_this_geometry",
                                          "worst_95_upper_5percent": 0.25}}
        for t in (17, 18, 28)}}
    path.write_text(json.dumps(value))
    assert referee._calibration_harness(path)[0]
    assert not referee._monthly_calibration(path)[0]
    del value["reliability"]["monthly_T18"]
    path.write_text(json.dumps(value))
    assert not referee._monthly_calibration(path)[0]


def test_conditional_timestamp_coverage_is_not_historical_qualification(tmp_path) -> None:
    import json

    from asof import referee

    path = tmp_path / "timestamp.json"
    path.write_text(json.dumps({"qualified_UTC": 0, "unresolved_accessions": 16921,
                               "unique_conditional_UTC": 16921}))
    assert not referee._timestamp_qualification(path)[0]
    path.write_text(json.dumps({"qualified_UTC": 16921, "unresolved_accessions": 1}))
    assert not referee._timestamp_qualification(path)[0]
    assert not referee._timestamp_manifest(path)[0]


def test_timestamp_manifest_is_confined_to_its_own_audit_directory(tmp_path) -> None:
    import json

    from asof import referee

    path = tmp_path / "timestamp_full_a3_report.json"
    path.write_text(json.dumps({"private_hash_manifest": {
        "data/timestamp_full_a2/checkpoint.json": "0" * 64}}))
    ok, evidence = referee._timestamp_manifest(path)
    assert not ok and "outside" in evidence


def test_default_referee_includes_recorded_clock_and_calibration_gaps() -> None:
    from asof.referee import default_threats

    threats = {t.tid: t for t in default_threats()}
    assert threats["time_authority"].gating and threats["inference.calibration"].gating


def test_plausibility_rejects_an_incomplete_variant_output(tmp_path, monkeypatch) -> None:
    import json

    from asof import referee

    monkeypatch.setattr(referee, "PROJECT_ROOT", tmp_path)
    (tmp_path / "results").mkdir()
    output = {"results": [{"variant": "v1_10K_raw", "monthly": {"months": 18, "mean_net": 0.01}}]}
    (tmp_path / "results" / "returns_h0_development.json").write_text(json.dumps(output))
    ok, reason = referee._plausibility()
    assert not ok
    assert "four declared variants" in reason
