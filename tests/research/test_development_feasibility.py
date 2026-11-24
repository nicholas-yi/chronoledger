import json
from copy import deepcopy

import pytest

from asof.periods import HoldoutAccessError
from asof.research.feasibility import FAMILIES, diagnose_projection, project_cases


def fixture():
    refs = [{"accepted_at": f"{year}-02-01T10:00:00+00:00",
             "knowledge_time": f"{year}-02-01T10:00:00+00:00",
             "report_date": f"{year-1}-12-31", "accession": f"fiction-{year}"}
            for year in (2014, 2015, 2016)]
    manifest = {"cases": [{"case_id": "fiction", "cik": 123, "annual": refs, "context": []}]}
    row = {
        "case_id": "fiction", "cik": 123,
        "sources": [{"accession": ref["accession"],
                     "stored_knowledge_time_unqualified": ref["knowledge_time"],
                     "metadata_report_date": ref["report_date"]} for ref in refs],
        "source_statuses": [{"status": "available"} for _ in refs], "earlier_context": [],
        "public_history_complete": False,
        "metrics": {name: {"observations": [
            {"alias_mentions": k+1, "numeric_context_mentions": 1,
             "evidence": [{"context": "DO_NOT_COPY_THIS_EXCERPT"}]} for k in range(3)]}
                    for name in FAMILIES},
    }
    return manifest, [row]


def test_projection_strips_text_and_identifiers_and_reports_real_limits() -> None:
    manifest, cases = fixture()
    projected = project_cases(manifest, cases)
    encoded = json.dumps(projected)
    assert "DO_NOT_COPY" not in encoded and '"cik"' not in encoded and '"accession"' not in encoded
    result = diagnose_projection(projected)
    assert result["source_cases"] == result["complete_three_source_cases"] == 1
    assert result["numeric_proxy_state_updates"] == 16
    assert result["trajectory_diagnostics"]["coordinate_count"] == 91
    assert result["trajectory_diagnostics"]["maximum_ordered_lag_area_error"] < 1e-8
    assert result["independent_gold_cases"] == 0 and result["semantic_accuracy"] is None
    assert result["areas"]["G"]["status"] == "not_evaluable"


def test_scope_and_identity_fail_before_feature_construction() -> None:
    manifest, cases = fixture()
    reserved = deepcopy(manifest)
    reserved["cases"][0]["annual"][0]["knowledge_time"] = "2024-01-01T00:00:00Z"
    with pytest.raises(HoldoutAccessError):
        project_cases(reserved, cases)
    wrong = deepcopy(cases)
    wrong[0]["sources"][0]["accession"] = "wrong"
    with pytest.raises(ValueError, match="binding"):
        project_cases(manifest, wrong)
    wrong = deepcopy(cases)
    wrong[0]["metrics"]["backlog"]["observations"][0]["alias_mentions"] = True
    with pytest.raises(ValueError, match="nonnegative integers"):
        project_cases(manifest, wrong)


def test_unknown_sources_and_time_precision_are_not_filled_with_zero_or_fake_instants() -> None:
    manifest, cases = fixture()
    cases[0]["source_statuses"][0]["status"] = "unavailable"
    projected = project_cases(manifest, cases)
    assert projected[0]["alias_counts"] is None
    result = diagnose_projection(projected)
    assert result["trajectory_diagnostics"]["coordinate_count"] is None
    assert result["areas"]["C"]["status"] == "not_evaluable"
    manifest, cases = fixture()
    for ref, source in zip(manifest["cases"][0]["annual"], cases[0]["sources"], strict=True):
        ref["knowledge_time"] = ref["knowledge_time"][:10]
        source["stored_knowledge_time_unqualified"] = ref["knowledge_time"]
    result = diagnose_projection(project_cases(manifest, cases))
    assert result["temporal_unavailable"]["date_only_or_naive_declared_time"] == 1
    assert result["trajectory_diagnostics"]["ordered_trajectories"] == 0


