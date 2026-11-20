import json

import pytest
from pydantic import ValidationError

from asof.reader_ai_review import opinion_schema
from asof.reader_ai_review_v2 import (
    ABSTENTION_VERDICT,
    Disclosure,
    account_attempts,
    disclosure_schema,
    messages,
    probes,
    record,
    schema,
    summarize,
)


def _ideal(probe) -> str:
    """Synthetic perfect reviewer output, used only to test accounting, never as a model result."""
    first = next(iter(json.loads(messages(probe.task)[1]["content"])["source"]))
    if probe.task.candidate.abstain:
        return json.dumps({"answer": "not_stated" if probe.task.expected_verdict == "supported" else "stated",
                           "citations": [] if probe.task.expected_verdict == "supported" else [first]})
    if probe.task.expected_verdict == "supported":
        return json.dumps({"verdict": "supported", "issues": [], "citations": [first]})
    return json.dumps({"verdict": "unsupported", "issues": ["value"], "citations": [first]})


def test_probe_set_is_balanced_unique_and_separates_fresh_from_exposed():
    rows = probes()
    assert len(rows) == 18 and len({probe.task.case.id for probe in rows}) == 18
    fresh = [probe for probe in rows if probe.origin == "fresh_unseen_by_reviewer_design"]
    assert len(fresh) == 6 and sum(probe.task.expected_verdict == "supported" for probe in fresh) == 3
    assert sum(probe.task.candidate.abstain for probe in fresh) == 2


def test_prompts_carry_no_authored_verdict_expected_tuple_or_duplicated_evidence():
    for probe in probes():
        payload = json.loads(messages(probe.task)[1]["content"])
        text = json.dumps(messages(probe.task))
        assert "expected" not in text and probe.task.expected_verdict not in payload.values()
        assert "evidence" not in json.dumps(payload.get("candidate", {}))
        assert ("candidate" in payload) is not probe.task.candidate.abstain
        assert schema(probe.task) == (disclosure_schema() if probe.task.candidate.abstain else opinion_schema())


def test_abstention_mapping_is_fixed_code_and_requires_citations_for_stated_amounts():
    probe = next(probe for probe in probes() if probe.task.candidate.abstain)
    assert ABSTENTION_VERDICT == {"stated": "unsupported", "not_stated": "supported",
                                  "conflicting": "supported", "cannot_tell": "uncertain"}
    for raw in ({"answer": "stated", "citations": []}, {"answer": "conflicting", "citations": []},
                {"answer": "not_stated", "citations": [], "confidence": 1},
                {"answer": "stated", "citations": ["E1", "E1"]}):
        with pytest.raises(ValidationError):
            Disclosure.model_validate(raw)
        assert not record(probe.task, json.dumps(raw))["valid"]
    assert not record(probe.task, json.dumps({"answer": "stated", "citations": ["E99"]}))["valid"]
    row = record(probe.task, json.dumps({"answer": "cannot_tell", "citations": []}))
    assert row["valid"] and row["verdict"] == "uncertain" and row["verdict_mapping"] == "fixed_code_table_not_model"


def test_summary_and_missing_attempts_keep_denominators_and_never_create_gold():
    rows = probes()
    perfect = {probe.task.case.id: {"ai_review_v2": record(probe.task, _ideal(probe))} for probe in rows}
    summary = summarize(perfect)
    assert summary["correct_verdicts"] == summary["planned"] == 18
    assert summary["by_origin"]["fresh_unseen_by_reviewer_design"]["correct_verdicts"] == 6
    assert summary["human_gold_labels"] == 0 and not summary["promote"]
    for probe in rows:
        assert not perfect[probe.task.case.id]["ai_review_v2"]["candidate_changed"]
    partial = account_attempts({}, [{"call_id": 1, "case_id": rows[0].task.case.id, "status": "started",
                                     "wire_contract": "decomposed_review"}])
    assert summarize(partial)["invalid_or_missing"] == 18 and summarize(partial)["recorded"] == 1
