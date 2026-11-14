import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest


def _script(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("plan_p0_assignments", scripts / "plan_p0_assignments.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frame():
    return pd.DataFrame({
        "cik_pair": [1, 1], "accession": ["A", "B"], "form_pair": ["10-Q", "10-Q"],
        "knowledge_time_pair": pd.to_datetime(["2024-06-12T15:00:00Z", "2024-06-12T16:00:00Z"]),
        "cik_bulk": [1, 1],
        "knowledge_time_bulk": pd.to_datetime(["2024-06-12T15:00:00Z", "2024-06-12T16:00:00Z"]),
    })


def test_agreement_does_not_exempt_joint_latest_context_and_no_score_is_read(monkeypatch):
    script = _script(monkeypatch)
    monkeypatch.setattr(script, "resident_bytes", lambda: 0)
    closes = [datetime(2024, 6, 12, 20, tzinfo=UTC), datetime(2024, 6, 13, 20, tzinfo=UTC),
              datetime(2024, 6, 28, 20, tzinfo=UTC)]
    source = _frame()
    before = source.copy(deep=True)
    summary, queue = script.summarize(source, closes, [closes[-1]], script.Budget())
    pd.testing.assert_frame_equal(source, before)
    assert summary["sensitive_internally_agreeing_accessions"] == 2
    assert summary["formation_instances"]["latest_signal_firm_month_instances"] == 1
    assert all("joint_latest_signal_context" in flags for flags in queue["sensitivity_reasons"])
    assert summary["incomplete_future365_metadata_envelopes"] == 2
    assert not any(name.startswith(("cos_", "return", "price")) for name in queue)


def test_sidecar_mismatch_and_duplicates_fail_before_any_screen(monkeypatch, tmp_path):
    script = _script(monkeypatch)
    monkeypatch.setattr(script, "DATA_DIR", tmp_path)
    frame = _frame()
    frame.to_parquet(tmp_path / "p0_pair_metadata_comparison.parquet", index=False)
    original = frame[["cik_pair", "accession", "form_pair", "knowledge_time_pair"]].copy()
    original.columns = ["cik", "accession", "form", "knowledge_time"]
    original.to_parquet(tmp_path / "h0_signals.parquet", index=False)
    loaded, paths = script.metadata_inputs()
    assert len(loaded) == 2 and len(paths) == 2
    original.loc[0, "knowledge_time"] += pd.Timedelta(seconds=1)
    original.to_parquet(tmp_path / "h0_signals.parquet", index=False)
    with pytest.raises(ValueError, match="no longer matches"):
        script.metadata_inputs()


def test_resource_stop_preserves_incomplete_report_and_cannot_claim_old_queue(monkeypatch, tmp_path):
    script = _script(monkeypatch)
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        monkeypatch.setenv(key, "1")
    monkeypatch.setattr(script, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(script, "metadata_inputs", lambda: (_frame(), []))
    monkeypatch.setattr(script, "factor_calendar", lambda: [datetime(2024, 6, 28).date()])
    monkeypatch.setattr(script, "resident_bytes", lambda: script.MAX_RSS)
    with pytest.raises(script.CeilingReached, match="resident_memory"):
        script.main()
    import json

    result = json.loads((tmp_path / "report.json").read_text())
    assert result["status"] == "incomplete"
    assert result["stop_reason"] == "resident_memory_ceiling"
    assert "queue_sha256" not in result
