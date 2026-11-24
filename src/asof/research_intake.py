"""Offline evidence-intake contracts, never human adjudication or source clearance."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from asof.measurement import MeasurementCase, validate_measurement_splits
from asof.periods import DEV_RETURN_CUTOFF

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
ANNOTATION_FIELDS = (
    "pair_id", "split", "issuer_pseudonym", "form", "earlier_accession", "current_accession",
    "earlier_accepted_at", "current_accepted_at", "earlier_fiscal_period", "current_fiscal_period",
    "section_id", "block_id", "earlier_source_SHA256", "current_source_SHA256", "old_claim_id",
    "old_evidence_span_or_cells", "new_claim_id", "new_evidence_span_or_cells", "entity", "predicate",
    "normalized_value", "currency", "unit", "scale", "period_role", "scope", "modality", "polarity",
    "matching_status", "primary_change", "secondary_flags", "coverage_complete", "exclusion_reason",
    "annotator_id", "guide_version", "confidence", "rationale", "AI_suggestion_seen",
)
CHANGES = {
    "NEW", "REMOVED", "MODIFIED_NUMERIC", "MODIFIED_QUALITATIVE", "UNCHANGED",
    "UNKNOWN/UNMATCHABLE", "EXCLUDED_BOILERPLATE/FORMAT",
}
RIGHTS = (
    "personal_research_use", "evaluation_publication", "nonreconstructive_outputs",
    "independent_review", "retention_and_deletion", "identifiers_and_reproducibility",
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AnnotationPair(ContractModel):
    pair_id: str
    issuer_id: str
    issuer_pseudonym: str
    split: Literal["calibration", "development", "audit"]
    form: Literal["10-K", "10-Q"]
    earlier_accession: str
    current_accession: str
    earlier_accepted_at: AwareDatetime
    current_accepted_at: AwareDatetime
    earlier_fiscal_period: str
    current_fiscal_period: str
    earlier_source_SHA256: Hash
    current_source_SHA256: Hash


class AnnotationManifest(ContractModel):
    status: Literal["DRAFT", "APPROVED_FOR_INTAKE"] = "DRAFT"
    authorization_ref: str | None = None
    data_handling_ref: str | None = None
    eligibility_approved: StrictBool = False
    guide_version: str = "H1-CLAIM-GUIDE-DRAFT-01"
    scope: Literal["full_target_sections", "block_scoped"] = "block_scoped"
    calibration_end: AwareDatetime | None = None
    development_end: AwareDatetime | None = None
    audit_end: AwareDatetime | None = None
    pairs: list[AnnotationPair] = Field(default_factory=list)


@dataclass(frozen=True)
class IntakeReport:
    status: Literal["blocked", "ready_for_human_review", "ready_for_independent_source_review"]
    scope: str
    records: int
    issues: tuple[str, ...]
    notes: tuple[str, ...]
    scientific_acceptance: bool = False
    creates_gold_or_fetches_data: bool = False


def _present(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def read_annotation_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if (reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames))
                or set(reader.fieldnames) != set(ANNOTATION_FIELDS)):
            raise ValueError("first-pass CSV must have exactly the declared unique38headers")
        rows = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("CSV row width differs from its declared headers")
            rows.append({k: v.strip() for k, v in row.items()})
    return rows


def annotation_intake(
    manifest: AnnotationManifest, submissions: Sequence[Sequence[Mapping[str, str]]],
) -> IntakeReport:
    issues = []
    if (manifest.status != "APPROVED_FOR_INTAKE" or not manifest.eligibility_approved
            or not _present(manifest.authorization_ref) or not _present(manifest.data_handling_ref)):
        issues.append("approved_roster_and_handling_receipts_missing")
    if not manifest.pairs:
        issues.append("pair_roster_empty")
    if not _present(manifest.guide_version):
        issues.append("guide_version_missing")
    if len({p.pair_id for p in manifest.pairs}) != len(manifest.pairs):
        issues.append("duplicate_manifest_pair")
    if len(submissions) != 2:
        issues.append("exactly_two_independent_first_pass_files_required")
    pairs = {p.pair_id: p for p in manifest.pairs}
    issuer_names, name_issuers = {}, {}
    for pair in manifest.pairs:
        if any(not _present(getattr(pair, k)) for k in (
            "pair_id", "issuer_id", "issuer_pseudonym", "earlier_accession", "current_accession",
            "earlier_fiscal_period", "current_fiscal_period",
        )):
            issues.append("manifest_pair_identity_or_period_missing")
        if (issuer_names.setdefault(pair.issuer_id, pair.issuer_pseudonym) != pair.issuer_pseudonym
                or name_issuers.setdefault(pair.issuer_pseudonym, pair.issuer_id) != pair.issuer_id):
            issues.append("issuer_pseudonym_mapping_inconsistent")
        current = pair.current_accepted_at.astimezone(UTC)
        if (not pair.earlier_accepted_at < pair.current_accepted_at
                or not date(2023, 1, 1) <= current.date() <= date(2024, 6, 30)
                or pair.earlier_accession == pair.current_accession):
            issues.append("pair_time_comparator_or_development_scope_invalid")
    calibration_end, development_end, audit_end = (
        manifest.calibration_end, manifest.development_end, manifest.audit_end)
    if calibration_end is None or development_end is None or audit_end is None:
        issues.append("frozen_chronological_split_bounds_missing")
    else:
        split: dict[str, Literal["train", "validation", "test"]] = {
            "calibration": "train", "development": "validation", "audit": "test"}
        cases = [MeasurementCase(
            p.pair_id, p.issuer_id, split[p.split], p.current_accepted_at, None, None,
            gold_reason="unadjudicated_intake", abstention_reason="no_model_in_intake",
        ) for p in manifest.pairs]
        try:
            validate_measurement_splits(cases, train_end=calibration_end,
                                       validation_end=development_end, test_end=audit_end)
        except ValueError:
            issues.append("issuer_or_time_split_contract_failed")
    annotators = []
    signatures = []
    records = 0
    for file_index, rows in enumerate(submissions, 1):
        prefix = f"file{file_index}"
        if not rows:
            issues.append(f"{prefix}:no_annotations")
        ids = {r.get("annotator_id", "") for r in rows}
        if len(ids) != 1 or not all(_present(v) for v in ids):
            issues.append(f"{prefix}:one_named_annotator_required")
        annotators.extend(ids)
        covered, seen, signature = set(), set(), set()
        for number, row in enumerate(rows, 2):
            records += 1
            at = f"{prefix}:row{number}"
            if set(row) != set(ANNOTATION_FIELDS):
                issues.append(f"{at}:field_set_changed")
                continue
            pair = pairs.get(row["pair_id"])
            if pair is None:
                issues.append(f"{at}:pair_outside_frozen_roster")
                continue
            covered.add(pair.pair_id)
            for key in ("split", "issuer_pseudonym", "form", "earlier_accession",
                        "current_accession", "earlier_fiscal_period", "current_fiscal_period",
                        "earlier_source_SHA256", "current_source_SHA256"):
                if row[key] != getattr(pair, key):
                    issues.append(f"{at}:frozen_pair_metadata_differs:{key}")
            for key in ("earlier_accepted_at", "current_accepted_at"):
                try:
                    from datetime import datetime
                    stamp = datetime.fromisoformat(row[key])
                    matches = stamp.tzinfo is not None and stamp == getattr(pair, key)
                except ValueError:
                    matches = False
                if not matches:
                    issues.append(f"{at}:frozen_pair_time_differs:{key}")
            if row["guide_version"] != manifest.guide_version:
                issues.append(f"{at}:guide_version_differs")
            if not _present(row["section_id"]) or (manifest.scope == "block_scoped" and not _present(
                row["block_id"]
            )):
                issues.append(f"{at}:section_or_block_identity_missing")
            if row["AI_suggestion_seen"].lower() != "false":
                issues.append(f"{at}:blind_first_pass_not_declared")
            if row["coverage_complete"].lower() not in ("true", "false"):
                issues.append(f"{at}:explicit_coverage_boolean_required")
            elif row["coverage_complete"].lower() != "true":
                issues.append(f"{at}:coverage_incomplete_not_gold")
            change = row["primary_change"]
            if change not in CHANGES:
                issues.append(f"{at}:unknown_change_class")
            expected_match = ("unmatched" if change in ("NEW", "REMOVED") else
                              "matched" if change in (
                                  "UNCHANGED", "MODIFIED_NUMERIC", "MODIFIED_QUALITATIVE") else
                              "unknown" if change == "UNKNOWN/UNMATCHABLE" else "excluded")
            if row["matching_status"] != expected_match:
                issues.append(f"{at}:matching_status_inconsistent_with_change")
            sides = (("new",) if change == "NEW" else ("old",) if change == "REMOVED"
                     else ("old", "new") if change in (
                         "UNCHANGED", "MODIFIED_NUMERIC", "MODIFIED_QUALITATIVE") else ())
            for side in sides:
                if not _present(row[f"{side}_claim_id"]) or not _present(
                    row[f"{side}_evidence_span_or_cells"]
                ):
                    issues.append(f"{at}:claim_and_source_evidence_required:{side}")
            if sides and (not _present(row["entity"]) or not _present(row["predicate"])):
                issues.append(f"{at}:entity_and_predicate_required")
            if (not _present(row["rationale"]) or (change == "EXCLUDED_BOILERPLATE/FORMAT"
                    and not _present(row["exclusion_reason"]))):
                issues.append(f"{at}:rationale_or_exclusion_reason_missing")
            unit: tuple[str, ...] = (pair.pair_id, row["section_id"], row["block_id"],
                                     row["old_claim_id"], row["new_claim_id"])
            if not row["old_claim_id"] and not row["new_claim_id"]:
                unit = (*unit, row["old_evidence_span_or_cells"], row["new_evidence_span_or_cells"])
            if unit in seen:
                issues.append(f"{at}:duplicate_claim_relation")
            seen.add(unit)
            signature.add((*unit, change, row["secondary_flags"]))
        if covered != set(pairs):
            issues.append(f"{prefix}:roster_pairs_not_all_covered")
        signatures.append(signature)
    if len(annotators) != 2 or len(set(annotators)) != 2:
        issues.append("two_distinct_annotators_required")
    notes = [
        "Declared CSV/manifest contract only: no authentication of people, blind conduct or source truth.",
        "No gold labels or measurement score created; matching IDs and coverage claims need human review.",
        "Block-scoped intake cannot establish whole-filing recall or permit a return test.",
    ]
    if len(signatures) == 2 and signatures[0] != signatures[1]:
        notes.append("First-pass IDs, units or labels differ: preserve both for alignment/adjudication review.")
    return IntakeReport("blocked" if issues else "ready_for_human_review", manifest.scope,
                        records, tuple(dict.fromkeys(issues)), tuple(notes))


class FieldReceipt(ContractModel):
    status: Literal["unknown", "documented", "unavailable", "not_applicable"] = "unknown"
    evidence_ref: str | None = None
    reason: str | None = None


class RightsReceipt(ContractModel):
    status: Literal["unknown", "granted", "denied"] = "unknown"
    evidence_ref: str | None = None


class SourceCaseReceipt(ContractModel):
    case_id: str
    fields: dict[str, FieldReceipt] = Field(default_factory=dict)
    identity_reconciled: StrictBool = False
    payoff_reconciled: StrictBool = False
    adjustments_not_double_counted: StrictBool = False
    reconciliation_ref: str | None = None


class SourcePacket(ContractModel):
    status: Literal["DRAFT", "APPROVED_FOR_INTAKE"] = "DRAFT"
    provider: str = "UNSELECTED"
    product_and_channel: str | None = None
    access_authorization_ref: str | None = None
    panel_SHA256: Hash
    requested_use: Literal["complete_returns", "price_component_only"] = "complete_returns"
    sample_start: date | None = None
    sample_end: date | None = None
    rights: dict[str, RightsReceipt] = Field(default_factory=dict)
    cases: list[SourceCaseReceipt] = Field(default_factory=list)


def source_intake(
    packet: SourcePacket, *, case_actions: Mapping[str, str],
    required_fields: Sequence[str], panel_digest: str,
) -> IntakeReport:
    issues = []
    if (packet.status != "APPROVED_FOR_INTAKE" or not _present(packet.provider)
            or not _present(packet.product_and_channel)
            or not _present(packet.access_authorization_ref) or packet.provider == "UNSELECTED"):
        issues.append("approved_product_channel_and_access_receipts_missing")
    if packet.panel_SHA256 != panel_digest:
        issues.append("frozen_panel_digest_differs")
    if (packet.sample_start is None or packet.sample_end is None
            or packet.sample_start > packet.sample_end
            or packet.sample_end > DEV_RETURN_CUTOFF):
        issues.append("explicit_pre_cutoff_sample_window_required")
    if set(packet.rights) != set(RIGHTS):
        issues.append("exact_rights_receipt_categories_required")
    for name in RIGHTS:
        right = packet.rights.get(name)
        if right is None or right.status != "granted" or not _present(right.evidence_ref):
            issues.append(f"rights_not_evidenced:{name}")
    ids = [r.case_id for r in packet.cases]
    if len(set(ids)) != len(ids) or set(ids) != set(case_actions):
        issues.append("exact_unique_case_panel_required")
    for case in packet.cases:
        if case.case_id not in case_actions:
            issues.append("case_outside_frozen_panel")
            continue
        prefix = case.case_id
        if set(case.fields) != set(required_fields):
            issues.append(f"{prefix}:exact_field_receipts_required")
        for name in required_fields:
            field = case.fields.get(name)
            if field is None or field.status == "unknown":
                issues.append(f"{prefix}:unknown_field:{name}")
            elif field.status == "documented" and not _present(field.evidence_ref):
                issues.append(f"{prefix}:evidence_ref_missing:{name}")
            elif field.status in ("unavailable", "not_applicable") and not _present(field.reason):
                issues.append(f"{prefix}:explicit_missing_or_inapplicable_reason_required:{name}")
        essential = {"issuer_id_or_CIK", "share_class", "raw_price", "raw_price_date",
                     "raw_price_type", "currency", "observation_date", "available_or_revision_vintage",
                     "ticker_valid_from", "ticker_valid_to", "venue_valid_from", "venue_valid_to",
                     "adjustment_basis", "source_provenance"}
        if packet.requested_use == "complete_returns":
            essential.update(("provider_security_id", "action_id", "action_type",
                              "effective_date", "terminal_status"))
            action = case_actions[case.case_id]
            if action != "spin_off":
                essential.add("terminal_amount")
            if "cash" in action:
                essential.update(("cash_amount", "currency", "payment_date"))
            if "stock" in action or action == "spin_off":
                essential.update(("stock_ratio", "successor_security_id"))
            if "reorganization" in action:
                essential.update(("stock_ratio", "successor_security_id", "warrant_status"))
        for name in essential:
            if case.fields.get(name) is None or case.fields[name].status != "documented":
                issues.append(f"{prefix}:required_evidence_unavailable:{name}")
        if (not case.identity_reconciled or not case.adjustments_not_double_counted
                or (packet.requested_use == "complete_returns" and not case.payoff_reconciled)
                or not _present(case.reconciliation_ref)):
            issues.append(f"{prefix}:independent_reconciliation_receipt_missing")
    return IntakeReport(
        "blocked" if issues else "ready_for_independent_source_review", packet.requested_use,
        len(packet.cases), tuple(dict.fromkeys(issues)), (
            "Declared receipts only, not legal advice, authenticated permissions or actual vendor-value verification.",
            "No raw prices or returns parsed/computed, no fetch, account, key or purchase.",
            "Even a complete12-case packet is a spot check, not all-US/PIT coverage or CVR qualification.",
            "Price-component scope never qualifies complete shareholder terminal returns.",
        ))
