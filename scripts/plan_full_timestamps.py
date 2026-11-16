"""Offline exact population/URL/cache inventory for a future approval, never acquisition."""

from __future__ import annotations

import gzip
import json
import math
import time
from collections import Counter
from datetime import datetime

import pandas as pd

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, RAW_DIR
from asof.edgar import response_cache_path
from asof.filing_header_pilot import POOLS, parse_header, parse_index, pool_for, resource_urls

QUEUE = DATA_DIR / "p0_assignment_queue.parquet"
METADATA = DATA_DIR / "p0_pair_metadata_comparison.parquet"
PILOT = PROJECT_ROOT / "results" / "header_pilot_reconciled.json"
OUTPUT = PROJECT_ROOT / "results" / "timestamp_full_plan.json"
PRIVATE = DATA_DIR / "timestamp_full_plan"


def assignment_required(row: dict) -> bool:
    closes = set(row["first_close_choices"])
    months = {(datetime.fromisoformat(t).year, datetime.fromisoformat(t).month)
              for t in row["candidate_times"]}
    flags = set(row["sensitivity_reasons"])
    return (len(closes) > 1 or len(months) > 1
            or bool(flags & {"formation_eligibility", "joint_latest_signal_context"}))


def urls_for_record(row: dict) -> list[dict]:
    result = []
    for cik in sorted({int(row["cik_pair"]), int(row["cik_bulk"])}):
        for kind, url in resource_urls(cik, row["accession"]).items():
            result.append({"accession": row["accession"], "path_CIK": cik,
                           "kind": kind, "URL": url})
    return result


def pilot_cache() -> dict:
    result = {}
    for row in json.loads(PILOT.read_bytes())["items"]:
        for kind in ("header", "index"):
            resource = row[kind]
            provenance = resource["provenance"]
            if not provenance["cache_hit"] and provenance["request"]["body_complete"]:
                request = provenance["request"]
                result[resource["URL"]] = {
                    "path": DATA_DIR / "header_pilot" / request["cache_file"],
                    "SHA256": request["SHA256_observed_bytes"], "gzip": False}
    return result


def inspect_cache(resource: dict, pilot: dict) -> dict:
    url = resource["URL"]
    source = pilot.get(url)
    if source is None:
        path = response_cache_path(url, RAW_DIR / "sec")
        if not path.exists():
            return {"status": "missing"}
        source = {"path": path, "SHA256": ledger.file_sha256(path), "gzip": True}
    path = source["path"]
    if ledger.file_sha256(path) != source["SHA256"]:
        raise ValueError("pinned_pilot_cache_changed")
    try:
        if source["gzip"]:
            with gzip.open(path, "rb") as stream:
                body = stream.read(65536)
        else:
            with path.open("rb") as stream:
                body = stream.read(65536)
    except (OSError, EOFError) as exc:
        return {"status": "unusable", "reason": type(exc).__name__}
    if len(body) >= 65536:
        return {"status": "unusable", "reason": "at_or_above_64KiB"}
    try:
        parsed = (parse_header(body, resource["accession"]) if resource["kind"] == "header"
                  else parse_index(body))
    except ValueError as exc:
        return {"status": "unusable", "reason": str(exc)}
    if "unknown" in parsed:
        return {"status": "unusable", "reason": parsed["unknown"]}
    return {"status": "usable_bounded_metadata_not_clock_authority",
            "path": str(path.relative_to(DATA_DIR)), "file_SHA256": source["SHA256"],
            "body_bytes": len(body)}


def main() -> None:
    started = time.monotonic()
    fields = ["accession", "pair_time", "bulk_time", "candidate_times", "first_close_choices",
              "clock_issues", "sensitivity_reasons", "CIKs_agree", "source_times_agree",
              "assignment_sensitive"]
    queue = pd.read_parquet(QUEUE, columns=fields, use_threads=False)
    meta = pd.read_parquet(METADATA, columns=["accession","cik_pair","cik_bulk"], use_threads=False)
    rows = queue.merge(meta, on="accession", validate="one_to_one").to_dict("records")
    if len(rows) != 21502:
        raise ValueError("metadata_universe_changed")
    base = {r["accession"] for r in rows if assignment_required(r)}
    disagreements = {r["accession"] for r in rows if pool_for(r) in (POOLS[2], POOLS[3])}
    if len(disagreements) != 108:
        raise ValueError("required108disagreement_definition_changed")
    required = base | disagreements
    records = sorted((r for r in rows if r["accession"] in required), key=lambda r:r["accession"])
    candidates = [u for row in records for u in urls_for_record(row)]
    if len({u["URL"] for u in candidates}) != len(candidates):
        raise ValueError("unexpected_duplicate_resource_URL")
    cached = pilot_cache()
    PRIVATE.mkdir(exist_ok=True)
    inventory = PRIVATE / "proposed_URL_inventory.jsonl"
    counts, reasons = Counter(), Counter()
    with inventory.open("w", encoding="utf-8") as stream:
        for resource in candidates:
            state = inspect_cache(resource, cached)
            counts[state["status"]] += 1
            if state.get("reason"):
                reasons[state["reason"]] += 1
            stream.write(json.dumps({**resource, "cache": state,
                "proposed_HTTP_needed": state["status"] != "usable_bounded_metadata_not_clock_authority"})
                + "\n")
    hits = counts["usable_bounded_metadata_not_clock_authority"]
    missing = len(candidates) - hits
    pilot_rows = json.loads(PILOT.read_bytes())["items"]
    outside_controls = [r["accession"] for r in pilot_rows if
        r["comparison"]["class"] == "neither_matches_assumption" and r["accession"] not in required]
    raw_disagreements = {r["accession"] for r in rows if not r["source_times_agree"]}
    body_bound = missing * 65536
    receipt_bound = missing * 4096
    filesystem_bound = missing * 4096
    report_bound = len(records) * 4096
    storage = body_bound + receipt_bound + filesystem_bound + report_bound
    value = {
        "kind": "PROPOSED FULL ASSIGNMENT-TIMESTAMP CHECK, NO REQUEST AUTHORIZATION",
        "new_requests": 0, "repairs": 0, "backtest_reruns": 0,
        "population": {
            "universe": "21502cached H0 metadata accessions,2022throughJune2024;not all EDGAR/history.",
            "universe_accessions": len(rows),
            "rule": "Union of differing candidate first-registered-close choices,UTCcalendar-month "
                    "choices,monthly formation-eligibility changes,and entire uncertain latest-signal "
                    "competitor contexts;plus the108exclusive winter/summer clock-disagreement pool.",
            "assignment_risk_accessions": len(base),
            "explicit_disagreement_accessions": len(disagreements),
            "overlap": len(base & disagreements), "additional_disagreement_accessions": len(disagreements-base),
            "required_unique_accessions": len(required),
            "first_registered_close_sensitive": sum(len(set(r["first_close_choices"]))>1 for r in rows),
            "UTC_month_sensitive": sum("UTC_month" in r["sensitivity_reasons"] for r in rows),
            "formation_eligibility_sensitive": sum("formation_eligibility" in r["sensitivity_reasons"] for r in rows),
            "latest_signal_context_accessions": sum("joint_latest_signal_context" in r["sensitivity_reasons"] for r in rows),
            "reason": "Joint monthly competitors are included,not just possible winners. "
                      "UTCmonth choices are conservatively retained even if the next close is same.",
            "not_in_scope": "Records sensitive only to prior120/future365label windows,not the "
                           "requested trading-day/month decisions,are not automatically included.",
            "all_raw_internal_clock_disagreements": len(raw_disagreements),
            "raw_disagreements_outside_required": len(raw_disagreements-required),
            "exclusion_warning": "The mandated108are the priority-exclusive37winter+71summer pools,"
                "not all165raw disagreements. Outside records are NOT certified; expanding scope "
                "requires an explicit amended population and budget.",
            "known_pilot_neither_controls_outside_required": outside_controls,
            "control_handling": "Retain these already-cached conditional counterexamples as controls,"
                "not population members or newly fetched cases;insensitivity is not clock authority.",
        },
        "URLs_and_cache": {
            "identity_policy": "Header and index for EACH distinct original pair/bulkCIK archive "
                               "path per accession;no firstCIK/accession-prefix remap. Content "
                               "identity/role conflicts remain unresolved,not cache-deduplicated away.",
            "CIK_disagreement_accessions": sum(r["cik_pair"]!=r["cik_bulk"] for r in records),
            "unique_metadata_URLs": len(candidates),
            "usable_cached_URLs_excluded_from_network": hits,
            "new_or_unusable_URLs_max_one_GET_each": missing,
            "cache_status_counts": dict(counts), "unusable_reasons": dict(reasons),
            "cache_definition": "Checksum-pinned,bounded<64KiB,parseable header/index metadata. "
                                "This is collection reuse,NOT clock or issuer certification.",
            "private_inventory": "data/timestamp_full_plan/proposed_URL_inventory.jsonl",
            "inventory_SHA256": ledger.file_sha256(inventory),
        },
        "proposed_approval": {
            "requires_NEW_explicit_user_budget": True,
            "used": 140, "current_ceiling": 150, "current_remaining_not_permission": 10,
            "field_clock_documentation_max_requests": 10,
            "metadata_max_requests": missing,
            "max_NEW_requests_proposed": missing + 10,
            "proposed_total_project_ceiling": 140 + missing + 10,
            "budget_contract": "Count all attempts before sending;cache hits0. Exact docs allowlist,"
                "population+URLinventory+sourcepins frozen before network;unused document budget "
                "does not transfer to extra filings. This proposal changes no ceiling or counter.",
        },
        "time": {
            "parallelism": 1, "maximum_starts_per_second": 2,
            "SEC_published_fair_access_ceiling_per_second": 10,
            "metadata_rate_limit_lower_bound_seconds": max(0, missing-1)/2,
            "metadata_rate_limit_lower_bound_hours": max(0, missing-1)/7200,
            "pilot_rate_extrapolated_hours_not_guaranteed": missing*(47.406/92)/3600,
            "serial30s_timeout_all_requests_hours_not_expected": missing*30/3600,
            "proposed_metadata_wall_cap_hours": 12,
            "proposed_docs_wall_cap_minutes": 30,
            "wall_note": "2starts/s is an upper rate,not assured throughput;serial latency and "
                         "fail-stop rules can prevent completion.12h is proposed approval,not "
                         "permission. Stop/checkpoint at wall,no automatic retry or scope expansion.",
            "rate_source": "Owner dispatch supplies published SEC ceiling10/s;existingproject "
                           "protocol also cites it. Not refreshed over network in this offline "
                           "plan;the proposedclient remains at2/s.",
        },
        "storage": {
            "per_resource_read_bound_bytes": 65536,
            "new_body_bytes_upper_bound": body_bound,
            "receipt_allowance_bytes": receipt_bound,
            "filesystem_allowance_bytes": filesystem_bound,
            "per_accession_report_allowance_bytes": report_bound,
            "logical_bytes_before_safety_margin": storage,
            "proposed_disk_budget_GiB": math.ceil(storage*1.25/(1<<30)),
            "policy": "Private ignored raw metadata+hashes+append-only receipts;never financial "
                      "bodies/quotes/identities in Git. Compression benefit not assumed. Cap/space "
                      "failure stops or leaves explicit unknown,no silent deletion/truncation.",
        },
        "prerequisites_and_stops": {
            "clock_authority": "Stage1 page did not define historical acceptance clocks. First "
                "qualify applicable header/index/API/bulk field definitions. If unsupported,stop "
                "with conditional Eastern candidates only;do not call them verifiedUTC.",
            "calendar": "Current risk flags use cached French dates/nominal16:00ET,not independently "
                "certified venue/early-close calendar. Qualify relevant calendar before claiming "
                "actual exchange-session assignment changes;otherwise label registered-calendar only.",
            "identity": "Role-aware filer/subject/transmitter/co-registrant evidence;multipleCIKs "
                "are not issuer/security mapping. Preserve original identities and uncertainty.",
            "sealed_data": "Only already-used acceptance/role/indexmetadata dates;no statement/"
                "XBRL,fundamental outcome,prices/returns or sealed observations. Stop scope uncertainty.",
            "http": "Existing declared User-Agent,ordinary publicHTTPS,<=2/s,serial,30stotal,"
                "no retries/redirects. Stop whole acquisition on403/429/5xx/transport/redirect/"
                "budget/scope/integrity/wall failure. No alternate identity/proxy/CIK bypass.",
            "unknowns": "Oversized/missing/malformed/ambiguous civil clock/role/conflict stays "
                "unknown,never agreement. Knownunusable cache is not proof another GET will help;"
                "freshfetchatmostonce onlyifapproved,stillbounded. Unresolved rows block certification.",
            "screen_violation": "If a qualified instant falls outside the frozen one-offset "
                "candidate envelope,stop certification and re-plan the population;do not assume "
                "excluded records remain assignment-insensitive or expand requests automatically.",
        },
        "done_output": {
            "per_accession": "Every required accession accounted for with original clocks/"
                "identities,resource/version/retrievalhashes,documented applicable clock basis,"
                "unique qualifiedUTC instant or explicit unresolved reason,and role/calendar status.",
            "assignment_reconciliation": "Using qualified times and the frozen rules,compare original"
                "vsverified first close,UTC/month buckets,monthly eligibility and latest-signal"
                "choice;report exact accession counts,record-month instances and firm-month changes."
                "No scores,prices,portfolio weights or P&L required.",
            "acceptance": "Verified means clock definition applicable,identityrole resolved,"
                "civil conversion unique,sourceconflicts addressed and calendar qualified. A list "
                "of conditional Eastern conversions alone is NOT done. Report verified/unresolved/"
                "unread/conflicting coverage with full reconciliation,not a blanket offset.",
            "separate_decisions": "No production timestamp/CIK repair,correction release,publication"
                "or backtest rerun without another decision,even after the audit is complete.",
            "limit": "This certifies only explicitly verified plan members,not the excluded cohort"
                "or allfilings;one-offset sensitivity screen is not a probability or global error bound.",
        },
        "provenance": {
            "input_SHA256": {str(p.relative_to(PROJECT_ROOT)): ledger.file_sha256(p)
                            for p in (QUEUE,METADATA,PILOT,PROJECT_ROOT/"results"/"timestamp_authority_plan.json")},
            "source_SHA256": ledger.file_sha256(__file__),
            "SEC_counter_unchanged": json.loads((DATA_DIR/"p0_SEC_request_receipt.json").read_bytes()),
            "plan_wall_seconds": time.monotonic()-started,
        },
    }
    OUTPUT.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"accessions":len(required),"URLs":len(candidates),"usable_cached":hits,
        "new_URLs":missing,"proposed_new_ceiling":value["proposed_approval"]["proposed_total_project_ceiling"],
        "min_hours_at2rps":value["time"]["metadata_rate_limit_lower_bound_hours"],
        "cache":dict(counts)},indent=2))


if __name__ == "__main__":
    main()
