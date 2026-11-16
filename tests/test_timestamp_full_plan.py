import importlib.util
from pathlib import Path


def module(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("full_timestamp_plan",scripts/"plan_full_timestamps.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_required_union_includes_monthly_competitors_not_label_only_windows(monkeypatch):
    m = module(monkeypatch)
    r = {"first_close_choices":["2023-01-03T21:00:00+00:00"],
         "candidate_times":["2023-01-03T20:00:00+00:00"],"sensitivity_reasons":["future_365d"]}
    assert not m.assignment_required(r)
    assert m.assignment_required({**r,"first_close_choices":[*r["first_close_choices"],None]})
    assert m.assignment_required({**r,"sensitivity_reasons":["joint_latest_signal_context"]})
    assert m.assignment_required({**r,"candidate_times":[
        "2023-01-31T23:00:00+00:00","2023-02-01T04:00:00+00:00"]})


def test_URLs_preserve_both_paths_without_duplicate_same_CIK(monkeypatch):
    m = module(monkeypatch)
    r = {"accession":"0000000123-23-000001","cik_pair":123,"cik_bulk":456}
    assert len({x["URL"] for x in m.urls_for_record(r)}) == 4
    assert len(m.urls_for_record({**r,"cik_bulk":123})) == 2
