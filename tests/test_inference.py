import numpy as np
import pandas as pd
import pytest

from asof import ledger
from asof.inference import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    nw_alpha,
    pbo_cscv,
    probabilistic_sharpe_ratio,
)


def test_nw_alpha_recovers_planted_alpha() -> None:
    rng = np.random.default_rng(0)
    n = 600
    f = pd.DataFrame({"mkt": rng.normal(0.006, 0.04, n)})
    r = pd.Series(0.004 + 0.5 * f["mkt"] + rng.normal(0, 0.01, n))
    res = nw_alpha(r, f)
    assert res.alpha == pytest.approx(0.004, abs=0.0015)
    assert res.t_stat > 3
    assert res.betas["mkt"] == pytest.approx(0.5, abs=0.05)


def test_psr_half_at_benchmark() -> None:
    assert probabilistic_sharpe_ratio(0.1, 100, 0.0, 3.0, 0.1) == pytest.approx(0.5)


def test_expected_max_sharpe_grows_with_trials() -> None:
    assert expected_max_sharpe(1000, 0.01) > expected_max_sharpe(10, 0.01) > 0


def test_dsr_penalizes_search_over_noise() -> None:
    rng = np.random.default_rng(1)
    trials = rng.normal(0, 0.05, size=(240, 500))
    srs = trials.mean(0) / trials.std(0, ddof=1)
    best = trials[:, int(np.argmax(srs))]
    # The naive PSR of the best noise strategy looks significant; the DSR does not clear the
    # conventional 0.95 bar. (For the max of N noise trials, DSR sits near 0.5 by construction.)
    naive = probabilistic_sharpe_ratio(srs.max(), 240, 0.0, 3.0)
    assert naive > 0.95
    assert deflated_sharpe_ratio(best, srs) < 0.95


def test_dsr_accepts_real_edge_among_noise() -> None:
    rng = np.random.default_rng(3)
    trials = rng.normal(0, 0.05, size=(240, 100))
    trials[:, 0] += 0.025  # per-period Sharpe ~0.5, far beyond the noise maximum
    srs = trials.mean(0) / trials.std(0, ddof=1)
    assert deflated_sharpe_ratio(trials[:, 0], srs) > 0.95


def test_pbo_high_for_noise_low_for_real_edge() -> None:
    rng = np.random.default_rng(2)
    noise = rng.normal(0, 0.02, size=(320, 40))
    assert 0.3 < pbo_cscv(noise, n_blocks=8) < 0.7
    edge = noise.copy()
    edge[:, 0] += 0.01
    assert pbo_cscv(edge, n_blocks=8) < 0.1


def test_pbo_refuses_a_missing_configuration_instead_of_scoring_it_zero() -> None:
    perf = np.array([[-0.01, np.nan], [-0.02, np.nan], [-0.01, np.nan], [-0.02, np.nan]])
    with pytest.raises(ValueError, match="finite"):
        pbo_cscv(perf, n_blocks=2)


def test_ledger_counts_trials_and_seals_holdout(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger.log_trial("H1", {"q": 5}, "development", {"t": 1.0}, path)
    ledger.log_trial("H1", {"q": 5}, "development", {"t": 1.1}, path)
    ledger.log_trial("H1", {"q": 10}, "development", {"t": 2.0}, path)
    assert ledger.n_trials("H1", path) == 2
    ledger.log_trial("H1", {"q": 5}, "holdout", {"t": 0.5}, path)
    with pytest.raises(PermissionError):
        ledger.log_trial("H1", {"q": 10}, "holdout", {"t": 3.5}, path)
    with pytest.raises(ValueError):
        ledger.log_trial("H1", {"q": 5}, "in-sample-peek", {}, path)


def test_ledger_records_lineage(tmp_path) -> None:
    import json

    data = tmp_path / "input.parquet"
    data.write_bytes(b"abc")
    path = tmp_path / "ledger.jsonl"
    ledger.log_trial("H9", {"x": 1}, "development", {}, path, inputs=[data])
    entry = json.loads(path.read_text().splitlines()[0])
    lin = entry["lineage"]
    assert len(lin["git_commit"]) == 40
    assert lin["inputs"][ledger.input_key(data)] == ledger.file_sha256(data)
    assert isinstance(lin["git_dirty"], bool)


def test_failed_development_execution_keeps_partial_metrics_and_prior_entries(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    data = tmp_path / "input.bin"
    data.write_bytes(b"synthetic-input")
    with ledger.development_trial("HX", {"variant": "complete"}, path=path) as metrics:
        metrics["n"] = 10
    prefix = path.read_bytes()
    with pytest.raises(RuntimeError, match="event fit failed"), ledger.development_trial(
        "HX", {"variant": "failure"}, inputs=[data], path=path,
    ) as metrics:
        metrics.update(phase="event_panel", m_months=18)
        raise RuntimeError("event fit failed")
    assert path.read_bytes().startswith(prefix)
    entries = ledger.read_ledger(path)
    assert [e["metrics"]["execution_status"] for e in entries] == ["completed", "failed"]
    assert entries[1]["period"] == "development"
    assert entries[1]["metrics"]["m_months"] == 18
    assert entries[1]["metrics"]["phase"] == "event_panel"
    assert entries[1]["lineage"]["inputs"][ledger.input_key(data)] == ledger.file_sha256(data)
