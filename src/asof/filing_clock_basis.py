"""Declared EDGAR header clock-basis test and per-accession acceptance-time qualification.

Regulation S-T Rule 13(a)(2) (17 CFR 232.13(a)(2)) deems a direct transmission commencing on or
before 5:30 p.m. "Eastern Standard Time or Eastern Daylight Saving Time, whichever is currently
in effect" filed that business day, and a later one filed the next business day. If the header
ACCEPTANCE-DATETIME is that legally defined Eastern civil clock, FILING-DATE rolls at 17:30 wall
time in both seasons. A fixed-EST reading (the PDS field label) predicts a 16:30 roll during
daylight time; a UTC reading predicts a roll near 21:30/22:30. The test compares those
predictions on retrieved headers. It does not certify EDGAR's synchronization to UTC.
"""

from __future__ import annotations

import html
import re
from bisect import bisect_right
from collections import Counter
from datetime import date, datetime, time, timedelta

from asof.filing_header_pilot import parse_header
from asof.timeutil import ET, et_wall_instants

CUTOFF = time(17, 30)
# Rule 13(a)(3)-(4) give these forms a 22:00 cutoff; they are outside the declared population.
EXEMPT_FORMS = re.compile(r"^(3|4|5|144|SC 13D|SC 13G|SC 14N|SCHEDULE 13D|SCHEDULE 13G)(/A)?$|MEF$")
S1_WINDOW = (time(16, 30), time(17, 30))
S2_WINDOW = (time(17, 35), time(21, 30))
EARLY_MORNING = (time(6, 0), time(10, 0))
OPERATING = (time(6, 0), time(22, 0))
RULE = {
    "S1_fixed_EST_rejection": "Daylight-season weekday headers with wall in [16:30,17:30): "
                              "n>=30 and same-day FILING-DATE share >=0.99.",
    "S2_UTC_rejection": "Weekday headers with wall in [17:35,21:30): n>=20 and later "
                        "FILING-DATE share >=0.95. If n<20, S3 decides: >=20 walls in "
                        "[06:00,10:00) and operating-window violations <=0.1%.",
    "integrity": "Weekday walls <=17:30 whose FILING-DATE rolled forward <=0.5%, and walls "
                 "outside [06:00,22:00] <=0.1% of the evaluated population.",
    "passed": "S1 AND UTC rejection AND integrity.",
    "population": "Readable headers with one acceptance wall, one filing date and a unique "
                  "Eastern conversion; Rule 13(a)(3)-(4) 22:00-cutoff forms excluded.",
}


def parse_header_dates(raw: bytes, accession: str) -> dict:
    """Acceptance wall, filing date and submission type from one retrieved header resource."""
    header = parse_header(raw, accession)
    if "unknown" in header:
        return {"unknown": header["unknown"]}
    text = html.unescape(raw.decode("latin-1"))
    filing = set(re.findall(r"<FILING-DATE>\s*(\d{8})\b", text)) | set(
        re.findall(r"FILED\s+AS\s+OF\s+DATE:\s*(\d{8})\b", text, re.IGNORECASE))
    forms = {f.upper() for f in re.findall(
        r"CONFORMED\s+SUBMISSION\s+TYPE:[ \t]*([^\r\n]+?)[ \t]*$", text,
        re.IGNORECASE | re.MULTILINE)}
    if len(filing) != 1:
        return {"unknown": "missing_or_nonunique_filing_date", "wall": header["header_wall"]}
    if len(forms) != 1:
        return {"unknown": "missing_or_nonunique_submission_type", "wall": header["header_wall"]}
    return {"wall": header["header_wall"], "filing_date": next(iter(filing)),
            "form": next(iter(forms)), "UTC_assuming_Eastern": header["UTC_assuming_Eastern"]}


def _wall(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d%H%M%S")


def _within(moment: time, window: tuple[time, time]) -> bool:
    return window[0] <= moment < window[1]


def cutoff_consistency(wall: str, filing_date: str) -> str:
    """Classify one header against the 17:30 Eastern civil cutoff.

    Acceptance follows commencement, so acceptance at or before 17:30 implies a same-day
    deemed filing date on a business day. A same-day date after 17:30 is allowed because
    transmission may have commenced before the cutoff.
    """
    moment, filed = _wall(wall), datetime.strptime(filing_date, "%Y%m%d").date()
    accepted = moment.date()
    if filed < accepted:
        return "adjusted_earlier_filing_date"
    if moment.weekday() >= 5:
        return "consistent" if filed > accepted else "inconsistent_weekend_same_day"
    if moment.time() <= CUTOFF:
        return "consistent" if filed == accepted else "inconsistent_early_roll"
    return "consistent" if filed > accepted else "consistent_commencement_lag_possible"


def clock_basis_test(observations: list[dict]) -> dict:
    """Pre-declared CB1 statistics and decision over parsed header observations."""
    excluded = Counter()
    rows = []
    for obs in observations:
        if "unknown" in obs:
            excluded[f"unreadable:{obs['unknown']}"] += 1
            continue
        if EXEMPT_FORMS.search(obs["form"]):
            excluded["22:00_cutoff_form"] += 1
            continue
        moment = _wall(obs["wall"])
        instants = et_wall_instants(moment)
        if len(instants) != 1:
            excluded["DST_gap_or_fold"] += 1
            continue
        offset = instants[0].astimezone(ET).utcoffset().total_seconds() / 3600
        filed = datetime.strptime(obs["filing_date"], "%Y%m%d").date()
        rows.append({"moment": moment, "season": "daylight" if offset == -4 else "standard",
                     "weekday": moment.weekday() < 5, "filed": filed,
                     "same_day": filed == moment.date(), "rolled": filed > moment.date(),
                     "earlier": filed < moment.date()})

    def share(part: list[dict], key: str) -> dict:
        k = sum(r[key] for r in part)
        return {"n": len(part), "k": k, "share": k / len(part) if part else None}

    weekday = [r for r in rows if r["weekday"]]
    s1 = share([r for r in weekday if r["season"] == "daylight"
                and _within(r["moment"].time(), S1_WINDOW)], "same_day")
    s1_control = share([r for r in weekday if r["season"] == "standard"
                        and _within(r["moment"].time(), S1_WINDOW)], "same_day")
    s2 = share([r for r in weekday if _within(r["moment"].time(), S2_WINDOW)], "rolled")
    early = sum(_within(r["moment"].time(), EARLY_MORNING) for r in rows)
    outside = sum(not OPERATING[0] <= r["moment"].time() <= OPERATING[1] for r in rows)
    before = [r for r in weekday if r["moment"].time() <= CUTOFF]
    early_roll = share(before, "rolled")
    brackets = {}
    for season in ("daylight", "standard"):
        part = [r for r in weekday if r["season"] == season and r["moment"].time() >= time(12)]
        same = [r["moment"].time() for r in part if r["same_day"]]
        rolled = [r["moment"].time() for r in part if r["rolled"]]
        brackets[season] = {
            "latest_same_day_wall": max(same).isoformat() if same else None,
            "earliest_rolled_wall_after_noon": min(rolled).isoformat() if rolled else None,
            "same_day_after_17_30": sum(t > CUTOFF for t in same),
            "rolled_at_or_before_17_30": sum(t <= CUTOFF for t in rolled)}
    s1_pass = s1["n"] >= 30 and s1["share"] >= 0.99
    if s2["n"] >= 20:
        utc_rejected, utc_route = s2["share"] >= 0.95, "S2"
    else:
        utc_rejected = early >= 20 and outside <= 0.001 * len(rows)
        utc_route = "S3_fallback"
    integrity = bool(rows) and (early_roll["share"] or 0) <= 0.005 and outside <= 0.001 * len(rows)
    return {
        "declared_rule": RULE, "evaluated_headers": len(rows), "excluded": dict(excluded),
        "S1_daylight_16_30_to_17_30_same_day": s1,
        "S1_control_standard_16_30_to_17_30_same_day": s1_control,
        "S2_17_35_to_21_30_rolled": s2,
        "S3_walls_06_00_to_10_00": early, "S3_walls_outside_06_00_to_22_00": outside,
        "weekday_at_or_before_17_30_rolled": early_roll,
        "filing_date_earlier_than_acceptance": sum(r["earlier"] for r in rows),
        "weekend_acceptances": sum(not r["weekday"] for r in rows),
        "descriptive_cutoff_brackets": brackets,
        "fixed_EST_rejected": s1_pass, "UTC_rejected": utc_rejected, "UTC_route": utc_route,
        "integrity_passed": integrity, "passed": bool(s1_pass and utc_rejected and integrity),
        "interpretation_if_passed": "Header walls behave as the Rule 13(a)(2) Eastern civil "
                                    "clock (EST or EDT in effect). This rejects fixed-EST and "
                                    "UTC readings; it does not verify EDGAR's synchronization "
                                    "to UTC or correctness of any JSON timestamp.",
    }


def possible_early_close(day: date) -> bool:
    """Conservative superset of scheduled 13:00 ET equity closes, without a venue list."""
    thanksgiving = date(day.year, 11, 1) + timedelta(days=(3 - date(day.year, 11, 1).weekday()) % 7 + 21)
    return (day.month, day.day) in {(7, 2), (7, 3), (12, 23), (12, 24)} or (
        day == thanksgiving + timedelta(days=1))


def qualify(row: dict, headers: list[dict], basis_passed: bool) -> dict:
    """Apply the declared per-accession rule to an ``accession_result`` row.

    ``headers`` holds :func:`parse_header_dates` output for every archive-path header
    resource of the accession. Issuer/security identity is reported separately (F7);
    it is not an acceptance-time property of the accession.
    """
    reasons = []
    if not basis_passed:
        reasons.append("declared_clock_basis_test_not_passed")
    conditional = row["conditional_UTC_assuming_Eastern"]
    if not conditional:
        reasons.append("missing_unread_or_conflicting_header_index_pair")
    if row["outside_frozen_candidate_envelope"]:
        reasons.append("header_time_outside_frozen_candidate_envelope")
    consistency = None
    if not headers or any("unknown" in h for h in headers):
        reasons.append("filing_date_unread_or_nonunique")
    elif len({(h["wall"], h["filing_date"]) for h in headers}) != 1:
        reasons.append("header_paths_disagree_on_wall_or_filing_date")
    else:
        consistency = cutoff_consistency(headers[0]["wall"], headers[0]["filing_date"])
        if consistency.startswith("inconsistent"):
            reasons.append("filing_date_inconsistent_with_declared_clock")
    qualified = None if reasons else conditional
    close_status = None
    if qualified:
        local = datetime.fromisoformat(qualified).astimezone(ET)
        close_status = ("possible_early_close_unresolved"
                        if possible_early_close(local.date()) and time(13) <= local.time() < time(16)
                        else "nominal_16_00_assignment_qualified")
    return {"accession": row["accession"], "qualified_UTC": qualified,
            "unresolved_reasons": reasons, "filing_date_consistency": consistency,
            "first_close_status": close_status}


def identity_class(row: dict) -> str:
    """Observed header CIK roles versus the two stored CIKs; not issuer adjudication."""
    observed = set()
    for note in row["CIK_role_notes"]:
        if note.get("unknown"):
            return "header_unread"
        for ciks in note["observed_roles"].values():
            observed |= {int(c) for c in ciks}
    if not observed:
        return "header_unread"
    pair, bulk = row["cik_pair"] in observed, row["cik_bulk"] in observed
    if row["cik_pair"] == row["cik_bulk"]:
        return "agreeing_CIK_in_header" if pair else "agreeing_CIK_absent_from_header"
    return {(True, True): "both_CIKs_in_header_co_registrant_evidence",
            (True, False): "pair_CIK_only", (False, True): "bulk_CIK_only",
            (False, False): "neither_CIK_in_header"}[(pair, bulk)]


def first_close_direction(universe: list[dict], qualified: dict[str, str],
                          closes: list[datetime]) -> dict:
    """Stored-versus-qualified first registered close, by direction.

    An earlier stored close than the qualified one means the stored time could trade a
    filing before it was public (look-ahead); a later one only delays it.
    """
    output = {}
    for source in ("pair", "bulk"):
        counts = Counter()
        for row in universe:
            stamp = qualified.get(row["accession"])
            if stamp is None:
                counts["unqualified_rows"] += 1
                continue
            stored = bisect_right(closes, datetime.fromisoformat(row[f"{source}_time"]))
            truth = bisect_right(closes, datetime.fromisoformat(stamp))
            if stored == len(closes) or truth == len(closes):
                counts["beyond_registered_calendar"] += 1
            else:
                counts["same_first_close" if stored == truth else
                       "stored_earlier_lookahead_risk" if stored < truth else
                       "stored_later_delay_only"] += 1
            counts["stored_time_equals_qualified"] += (
                datetime.fromisoformat(row[f"{source}_time"]) == datetime.fromisoformat(stamp))
        output[f"stored_{source}"] = dict(counts)
    return output
