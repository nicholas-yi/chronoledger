import csv
import importlib.util
import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from asof import ledger
from asof.config import PROJECT_ROOT
from asof.research_intake import (
    ANNOTATION_FIELDS,
    RIGHTS,
    AnnotationManifest,
    AnnotationPair,
    FieldReceipt,
    RightsReceipt,
    SourceCaseReceipt,
    SourcePacket,
    annotation_intake,
    read_annotation_csv,
    source_intake,
)


def human_fixture():
    pair = AnnotationPair(
        pair_id="fictional_pair", issuer_id="fictional_issuer", issuer_pseudonym="Issuer A",
        split="calibration", form="10-K", earlier_accession="earlier", current_accession="current",
        earlier_accepted_at=datetime(2022, 2, 1, tzinfo=UTC),
        current_accepted_at=datetime(2023, 2, 1, tzinfo=UTC),
        earlier_fiscal_period="FY2021", current_fiscal_period="FY2022",
        earlier_source_SHA256="a"*64, current_source_SHA256="b"*64,
    )
    manifest = AnnotationManifest(
        status="APPROVED_FOR_INTAKE", authorization_ref="synthetic:authorization",
        data_handling_ref="synthetic:handling", eligibility_approved=True,
        calibration_end=datetime(2023, 7, 1, tzinfo=UTC),
        development_end=datetime(2024, 1, 1, tzinfo=UTC),
        audit_end=datetime(2024, 7, 1, tzinfo=UTC), pairs=[pair])
    row = dict.fromkeys(ANNOTATION_FIELDS, "")
    for key in ("pair_id", "issuer_pseudonym", "split", "form", "earlier_accession",
                "current_accession", "earlier_fiscal_period", "current_fiscal_period",
                "earlier_source_SHA256", "current_source_SHA256"):
        row[key] = getattr(pair, key)
    row.update(
        earlier_accepted_at=pair.earlier_accepted_at.isoformat(),
        current_accepted_at=pair.current_accepted_at.isoformat(),
        section_id="MD&A", block_id="fictional_block", new_claim_id="claim1",
        new_evidence_span_or_cells="synthetic:offset10-30",
        entity="Invented entity", predicate="invented predicate", primary_change="NEW",
        matching_status="unmatched", coverage_complete="true",
        guide_version=manifest.guide_version, rationale="Invented fixture, not a filing assertion.",
        AI_suggestion_seen="false")
    return manifest, [[{**row, "annotator_id": "fictional_a"}],
                      [{**row, "annotator_id": "fictional_b"}]]


def test_complete_blind_intake_is_review_ready_not_gold_or_a_measurement_score():
    manifest, files = human_fixture()
    report = annotation_intake(manifest, files)
    assert report.status == "ready_for_human_review" and report.records == 2
    assert not report.scientific_acceptance and not report.creates_gold_or_fetches_data
    files[1][0].update(primary_change="UNKNOWN/UNMATCHABLE", matching_status="unknown")
    disagreement = annotation_intake(manifest, files)
    assert disagreement.status == "ready_for_human_review"
    assert any("adjudication" in note for note in disagreement.notes)


@pytest.mark.parametrize("change", ["same_annotator", "AI_seen", "missing_evidence",
                                   "duplicate_relation", "changed_source_hash", "incomplete"])
def test_bad_human_receipts_cannot_be_review_ready(change):
    manifest, files = human_fixture()
    if change == "same_annotator":
        files[1][0]["annotator_id"] = "fictional_a"
    elif change == "AI_seen":
        files[0][0]["AI_suggestion_seen"] = "true"
    elif change == "missing_evidence":
        files[0][0]["new_evidence_span_or_cells"] = ""
    elif change == "duplicate_relation":
        files[0].append(dict(files[0][0]))
    elif change == "changed_source_hash":
        files[0][0]["current_source_SHA256"] = "c"*64
    else:
        files[0][0]["coverage_complete"] = "false"
    report = annotation_intake(manifest, files)
    assert report.status == "blocked" and report.issues and not report.scientific_acceptance


def test_empty_template_and_cross_company_time_leaks_do_not_pass():
    assert annotation_intake(AnnotationManifest(), [[], []]).status == "blocked"
    manifest, files = human_fixture()
    other = manifest.pairs[0].model_copy(update={
        "pair_id": "second", "split": "audit", "current_accepted_at": datetime(2024, 3, 1, tzinfo=UTC)})
    manifest.pairs.append(other)
    report = annotation_intake(manifest, files)
    assert "issuer_or_time_split_contract_failed" in report.issues
    with pytest.raises(ValidationError):
        AnnotationManifest(eligibility_approved="true")


def test_CSV_parser_rejects_duplicate_headers_and_wrong_row_width(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("pair_id,pair_id\nx,x\n")
    with pytest.raises(ValueError, match="unique38headers"):
        read_annotation_csv(path)
    with path.open("w", newline="") as stream:
        csv.writer(stream).writerow(ANNOTATION_FIELDS)
        csv.writer(stream).writerow(["short"])
    with pytest.raises(ValueError, match="row width"):
        read_annotation_csv(path)


def source_fixture():
    path = PROJECT_ROOT / "results" / "price_source_test_panel.json"
    panel = json.loads(path.read_bytes())
    fields = panel["required_future_sample_fields"]
    packet = SourcePacket(
        status="APPROVED_FOR_INTAKE", provider="FICTIONAL TEST, NOT ACTUAL COVERAGE",
        product_and_channel="synthetic product", access_authorization_ref="synthetic:access",
        panel_SHA256=ledger.file_sha256(path), sample_start=date(2013, 1, 1),
        sample_end=date(2024, 7, 31),
        rights={k: RightsReceipt(status="granted", evidence_ref="synthetic:rights") for k in RIGHTS},
        cases=[SourceCaseReceipt(
            case_id=c["case_id"],
            fields={k: FieldReceipt(status="documented", evidence_ref=f"synthetic:{k}") for k in fields},
            identity_reconciled=True, payoff_reconciled=True, adjustments_not_double_counted=True,
            reconciliation_ref="synthetic:independent_reconciliation") for c in panel["cases"]])
    kwargs = {"case_actions": {c["case_id"]: c["action_type"] for c in panel["cases"]},
              "required_fields": fields, "panel_digest": ledger.file_sha256(path)}
    return packet, kwargs


def test_complete_source_receipts_are_only_ready_for_independent_review():
    packet, kwargs = source_fixture()
    report = source_intake(packet, **kwargs)
    assert report.status == "ready_for_independent_source_review" and report.records == 12
    assert not report.scientific_acceptance and not report.creates_gold_or_fetches_data
    assert any("CVR" in note for note in report.notes)


@pytest.mark.parametrize("change", ["rights_unknown", "duplicate_case", "postcutoff",
                                   "missing_cash_leg", "missing_stock_leg", "double_counting",
                                   "missing_terminal"])
def test_source_gaps_never_become_complete_return_qualification(change):
    packet, kwargs = source_fixture()
    if change == "rights_unknown":
        packet.rights["evaluation_publication"] = RightsReceipt()
    elif change == "duplicate_case":
        packet.cases[-1] = packet.cases[0]
    elif change == "postcutoff":
        packet.sample_end = date(2024, 8, 1)
    elif change == "missing_cash_leg":
        packet.cases[0].fields["cash_amount"] = FieldReceipt(status="unavailable", reason="No sample.")
    elif change == "missing_stock_leg":
        packet.cases[3].fields["stock_ratio"] = FieldReceipt(status="unavailable", reason="No sample.")
    elif change == "double_counting":
        packet.cases[0].adjustments_not_double_counted = False
    else:
        packet.cases[0].fields["terminal_amount"] = FieldReceipt(status="unavailable", reason="No sample.")
    report = source_intake(packet, **kwargs)
    assert report.status == "blocked" and report.issues


def test_narrow_price_component_does_not_silently_clear_terminal_returns():
    packet, kwargs = source_fixture()
    packet.requested_use = "price_component_only"
    packet.cases[0].fields["terminal_amount"] = FieldReceipt(status="unavailable", reason="Not supplied.")
    packet.cases[0].payoff_reconciled = False
    report = source_intake(packet, **kwargs)
    assert report.status == "ready_for_independent_source_review"
    assert report.scope == "price_component_only" and not report.scientific_acceptance
    assert any("never qualifies complete" in note for note in report.notes)


def test_price_component_can_disclose_missing_action_feed_but_not_missing_dated_identity():
    packet, kwargs = source_fixture()
    packet.requested_use = "price_component_only"
    for key in ("provider_security_id", "action_id", "effective_date", "terminal_amount"):
        packet.cases[0].fields[key] = FieldReceipt(
            status="unavailable", reason="Narrow component with separately reviewed overlay.")
    packet.cases[0].payoff_reconciled = False
    assert source_intake(packet, **kwargs).status == "ready_for_independent_source_review"
    packet.cases[0].fields["ticker_valid_from"] = FieldReceipt(
        status="unavailable", reason="Dated identity bridge absent.")
    assert source_intake(packet, **kwargs).status == "blocked"


def test_generated_drafts_are_valid_packets_but_remain_blocked(tmp_path, monkeypatch):
    scripts = PROJECT_ROOT / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("research_intake_cli", scripts / "check_research_intake.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    directory = tmp_path / "draft"
    result = cli.templates(directory)
    assert result["annotation_rows"] == 0 and result["data_acquired"] is False
    manifest = AnnotationManifest.model_validate_json((directory / "annotation_manifest.json").read_bytes())
    files = [read_annotation_csv(directory / n) for n in ("annotator_a.csv", "annotator_b.csv")]
    assert annotation_intake(manifest, files).status == "blocked"
    packet = SourcePacket.model_validate_json((directory / "source_receipts.json").read_bytes())
    _, kwargs = source_fixture()
    assert source_intake(packet, **kwargs).status == "blocked"
    with pytest.raises(FileExistsError):
        cli.templates(directory)
    import sys
    output = tmp_path / "intake_report.json"
    monkeypatch.setattr(sys, "argv", [
        "check_research_intake.py", "annotations",
        "--manifest", str(directory / "annotation_manifest.json"),
        "--annotators", str(directory / "annotator_a.csv"), str(directory / "annotator_b.csv"),
        "--output", str(output)])
    assert cli.main() == 2
    saved = output.read_bytes()
    actual = json.loads(saved)
    assert actual["status"] == "blocked" and actual["records"] == 0
    assert actual["scientific_acceptance"] is False
    assert cli.main() == 2 and output.read_bytes() == saved
