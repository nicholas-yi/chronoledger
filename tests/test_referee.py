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
