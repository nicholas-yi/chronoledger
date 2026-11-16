"""Practice first, then one fresh invented control with explicit system abstentions."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Literal

import httpx
from pydantic import ValidationError
from reader_real1_memory import OwnedMemory
from run_reader_contract import native_score, native_scorer
from run_reader_positive_control import DIGEST, ENDPOINT, MODEL, ResourceStop, guarded_request
from run_reader_real2 import CPURecorder, wait_for_launch
from run_reader_real2_completion import SleepAwareCPU

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT
from asof.reader_contract import Control, Report, passed
from asof.reader_modes import Mode, ModeChoice
from asof.reader_presence import ADAPTER, answer_body, mode_body, resolve_answer
from asof.reader_real2_guards import SustainedCPU, input_fit, truncation_reason

ROOT = PROJECT_ROOT
Profile = Literal["presence", "roles", "columns"]
InterfaceMode = Mode | Literal["text_span"]
OPTIONS = {"temperature": 0, "seed": 2026111605, "num_predict": 768, "num_ctx": 8192,
           "num_thread": 4, "num_gpu": 0, "num_batch": 128}
SOURCES = [Path(__file__), ROOT / "src" / "asof" / "reader_presence.py",
           ROOT / "src" / "asof" / "reader_modes.py", ROOT / "src" / "asof" / "reader_contract.py",
           ROOT / "src" / "asof" / "reader_real2_guards.py",
           *[ROOT / "scripts" / p for p in ("reader_real1_memory.py", "run_reader_real2.py",
               "run_reader_real2_completion.py", "run_reader_positive_control.py",
               "run_reader_contract.py")]]


def paths(practice: bool, iteration: int, profile: Profile = "presence"):
    label = f"practice_{iteration}" if practice else "scored"
    private = DATA_DIR / f"reader_{profile}"
    return (ROOT / "results" / f"reader_{profile}_{label}_config.json",
            ROOT / "results" / f"reader_{profile}_{label}_status.json", private / label)


def history(profile: Profile = "presence"):
    return [json.loads(p.read_text()) for p in sorted(
        (ROOT / "results").glob(f"reader_{profile}_practice_*_status.json"))]


def prior_practice_calls(iteration: int, profile: Profile = "presence") -> int:
    return sum(r["calls"] for r in history(profile) if r["iteration"] < iteration)


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_report(profile: Profile, value: dict) -> Report:
    if profile == "columns":
        from asof.reader_columns import ColumnReport
        return ColumnReport.model_validate(value)
    return Report.model_validate(value)


def scored_case(value: dict) -> Control:
    # The scorer uses expectation metadata, not report evidence.
    report = {key: value["report"][key] for key in ("question", "monetary_banner", "rows")}
    return Control.model_validate({**value, "report": report})


def build_mode(profile: Profile, report: Report, model: str, options: dict) -> dict:
    if profile == "columns":
        from asof.reader_columns import ColumnReport
        from asof.reader_columns import mode_body as column_mode
        if not isinstance(report, ColumnReport):
            raise TypeError("column profile needs paragraph-aware report")
        return column_mode(report, model, options)
    return mode_body(report, model, options)


def choose_mode(profile: Profile, content: str) -> InterfaceMode:
    if profile == "columns":
        from asof.reader_columns import ModeChoice as ColumnChoice
        return ColumnChoice.model_validate_json(content).mode
    return ModeChoice.model_validate_json(content).mode


def build_answer(
    profile: Profile, report: Report, mode: InterfaceMode, model: str, options: dict,
) -> dict:
    if profile == "columns":
        from asof.reader_columns import ColumnReport
        from asof.reader_columns import answer_body as column_body
        if not isinstance(report, ColumnReport):
            raise TypeError("column profile needs paragraph-aware report")
        return column_body(report, mode, model, options)
    if mode == "text_span":
        raise ValueError("text_span requires column profile")
    if profile == "roles":
        from asof.reader_roles import answer_body as role_body
        return role_body(report, mode, model, options)
    return answer_body(report, mode, model, options)


def freeze(practice: bool, iteration: int, change: str, profile: Profile = "presence") -> None:
    config_path, status_path, _ = paths(practice, iteration, profile)
    if config_path.exists() or status_path.exists():
        raise RuntimeError("phase already frozen/attempted")
    fixture = ROOT / "tests" / "fixtures" / (
        f"reader_{profile}_practice.json" if practice else f"reader_{profile}_scored.json")
    items = json.loads(fixture.read_text())
    previous = history(profile)
    if practice:
        if not 1 <= iteration <= 3 or len(previous) != iteration - 1 or len(items) > 12:
            raise ValueError("practice limit/sequence")
        if sum(r["calls"] for r in previous) + 2 * len(items) > 40:
            raise ValueError("practice40call cap")
        if (fixture.parent / f"reader_{profile}_scored.json").exists() or any(
            "expected" in r for r in items
        ):
            raise ValueError("practice first and never accuracy labels")
    else:
        if not previous or not previous[-1]["format_and_resource_gate"]:
            raise ValueError("practice format/resource gate required before fresh scored freeze")
        if Counter(r["category"] for r in items) != {
            "multi_value": 6, "arithmetic": 8, "lookup": 4, "unit_trap": 3, "unanswerable": 3,
        }:
            raise ValueError("scored composition")
        for r in items:
            scored_case(r)
        exposed = []
        for candidate in fixture.parent.glob("reader_*.json"):
            if candidate != fixture:
                exposed.extend(json.loads(candidate.read_text()))
        if {r["report"]["question"] for r in items} & {r["report"]["question"] for r in exposed}:
            raise ValueError("fresh scored questions required")
    if len({r["id"] for r in items}) != len(items):
        raise ValueError("duplicate IDs")
    requests = {}
    for r in items:
        report = read_report(profile, r["report"])
        modes: tuple[InterfaceMode, ...] = ("lookup", "multi_value", "arithmetic", "abstain")
        if profile == "columns":
            modes = (*modes, "text_span")
        requests[r["id"]] = {
            "mode": fingerprint(build_mode(profile, report, MODEL, OPTIONS)),
            **{m: fingerprint(build_answer(profile, report, m, MODEL, OPTIONS))
               for m in modes}}
    sources = SOURCES + ([ROOT / "src" / "asof" / "reader_roles.py"]
                        if profile in ("roles", "columns") else [])
    if profile == "columns":
        sources.append(ROOT / "src" / "asof" / "reader_columns.py")
    non_year = []
    if profile == "columns":
        non_year = [r["id"] for r in items if r["report"]["rows"] and all(
            re.fullmatch(r"(?:19|20)\d{2}", label) is None
            for row in r["report"]["rows"] for label in row["values"])]
        if not practice and len(non_year) < 6:
            raise ValueError("at least6scored non-year-column reports required")
    value = {"kind": "PRACTICE NEVER ACCURACY" if practice else "FRESH INVENTED CONTROL",
        "iteration": iteration if practice else None, "change": change, "items": items,
        "profile": profile,
        "non_year_column_ids": non_year,
        "column_contract": ("Source field column_label is an actual dictionary column header,"
            "not a temporal classification. Internal compatibility adapter only renames it for "
            "the existing checked calculator. text_span has paragraph_id+verbatim substring,"
            "no row/column dependency. No inference-time expected labels."
            if profile == "columns" else None),
        "options": OPTIONS, "digest": DIGEST, "server": "0.40.16",
        "request_SHA256": requests,
        "source_SHA256": {str(p.relative_to(ROOT)): ledger.file_sha256(p) for p in sources},
        "schema_policy": "Two-stage,mode first; source fields includeNOT_PRESENT. Source-only "
                         "vocabularies and unit-derived dimension domain; code validates cells "
                         "and derives arithmetic/scale. No answer label in model input.",
        "decline_policy": "Model abstain and explicit SYSTEM declines on NOT_PRESENT,missing "
                          "operands,zero denominator,incompatible dimension/unit all count as "
                          "abstentions; report model/system separately. Others remain failures.",
        "pass": "All24attempted;>=20/21fullyright nativeEM+scale+dimension+operation AND3/3"
                "model-or-system abstentions. Answerable abstention is a miss. No retries/rerun.",
        "limits": "Entire invented-control part30min from first practice start;4threads,10GiB,240s percall,"
                  "sustainedREAL2CPU,sleepstop,continue single timeout/stop3consecutive.",
        "scope": "Invented only,no real benchmark data,no ledger row,pull,training or paid call.",
        "SEC_receipt_SHA256": ledger.file_sha256(DATA_DIR / "p0_SEC_request_receipt.json"),
        "named_role_contract": ("difference=end-start;fractionalchange=(end-start)/abs(start),"
            "displaypercent=100*fraction;ratio=numerator/denominator;average=mean(values). "
            "Allroles retain row/period/unit/value;code-derived scale,source checks unchanged. "
            "Mixed real/NOT_PRESENT lists rejected as SYSTEM decline. List capacity is bounded "
            "by source-cell count (not target labels),max6." if profile in ("roles", "columns") else None),
        "practice_SHA256": [ledger.file_sha256(paths(True, r["iteration"], profile)[1])
                           for r in previous]}
    config_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"config_SHA256": ledger.file_sha256(config_path), "items": len(items)}))


async def run(practice: bool, iteration: int, pid: int, profile: Profile = "presence") -> None:
    cp, sp, private = paths(practice, iteration, profile)
    if sp.exists():
        raise RuntimeError("already attempted")
    cfg = json.loads(cp.read_text())
    if ledger.lineage()["git_dirty"] or any(
        ledger.file_sha256(ROOT / p) != h for p, h in cfg["source_SHA256"].items()
    ):
        raise ValueError("commit source/config before calls")
    private.mkdir(parents=True, exist_ok=True)
    private_root = DATA_DIR / f"reader_{profile}"
    server_log = private_root / "isolated-server.log"
    deadline_path = private_root / "part1_deadline.json" if profile in ("roles", "columns") else (
        private_root / "part2a_deadline.json")
    if not deadline_path.exists():
        deadline_path.write_text(json.dumps({"monotonic_deadline": time.monotonic() + 1800}),
                            encoding="utf-8")
    deadline = json.loads(deadline_path.read_text())["monotonic_deadline"]
    wall_reason = "entire_invented_control30minwall"
    start, cpu_start = time.monotonic(), time.process_time()
    cpu, memory, policy = SleepAwareCPU(), OwnedMemory(pid), SustainedCPU()
    rows = [{"id": r["id"], "calls": [], "outcome": "not_attempted",
             **({} if practice else {"correct": False})} for r in cfg["items"]]
    output = {"kind": cfg["kind"], "iteration": cfg["iteration"], "items": rows,
              "config_SHA256": ledger.file_sha256(cp), "lineage": ledger.lineage(),
              "CPU_trace": policy.trace, "sleep_interruptions": cpu.interruptions}

    def persist():
        sp.write_text(json.dumps(output, indent=2), encoding="utf-8")

    async def watch_loop(recorder):
        while True:
            if await recorder.sample():
                raise ResourceStop("sustained_CPU")
            if memory.sample() > 10 << 30:
                raise ResourceStop("owned_RSS10GiB")
            if time.monotonic() >= deadline:
                raise ResourceStop(wall_reason)

    consecutive = 0

    async def ask(client, body, row, stage, watch):
        nonlocal consecutive
        if fingerprint(body) != cfg["request_SHA256"][row["id"]][stage]:
            raise ResourceStop("frozen_request_changed")
        if not input_fit(json.dumps(body).encode(), cfg["options"])[2]:
            raise ValueError("input_fit")
        cpu.check_suspend()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResourceStop(wall_reason)
        if practice and prior_practice_calls(iteration, profile) + sum(
            len(r["calls"]) for r in rows) >= 40:
            raise ResourceStop("practice40callcap")
        call = {"stage": stage, "outcome": "started"}
        row["calls"].append(call)
        row["outcome"] = "attempt_started"
        persist()
        offset, started = server_log.stat().st_size, time.monotonic()
        try:
            response = await guarded_request(client, body, watch, min(240, remaining))
            consecutive = 0
            cpu.check_suspend()
            response.raise_for_status()
            raw = response.json()
            path = private / f"{row['id']}_{stage}.json"
            path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            call["raw_SHA256"] = ledger.file_sha256(path)
            call["metrics"] = {k: raw.get(k) for k in ("prompt_eval_count", "eval_count",
                                                      "total_duration", "load_duration")}
            with server_log.open("rb") as stream:
                stream.seek(offset)
                log = stream.read(262145)
            if len(log) > 262144:
                raise ValueError("log_verification_bound")
            cut = bool(re.search(r"truncat\w*\s+input\s+prompt|input\s+prompt.{0,100}truncat",
                                 log.decode("utf-8", errors="replace"), re.IGNORECASE))
            invalid = truncation_reason(raw, body["options"], cut)
            if invalid or raw.get("done") is not True or raw.get("done_reason") != "stop":
                raise ValueError(invalid or "incomplete_generation")
            call["outcome"] = "complete"
            return raw["message"]["content"]
        except (TimeoutError, httpx.TimeoutException) as exc:
            consecutive += 1
            call.update(outcome="failed", reason="timeout")
            if consecutive >= 3:
                raise ResourceStop("three_consecutive_timeouts") from exc
            raise ValueError("timeout") from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            consecutive = 0
            call.update(outcome="failed", reason=str(exc))
            raise
        finally:
            call["wall_seconds"] = time.monotonic() - started
            persist()

    persist()
    complete, stop, watch = False, "unexpected_interruption", None
    with (private / "CPU_trace.jsonl").open("x", encoding="utf-8") as trace:
        try:
            recorder = CPURecorder(start, cpu, policy, trace)
            output["launch_CPU_mean"] = await wait_for_launch(recorder, start)
            watch = asyncio.create_task(watch_loop(recorder))
            scorer = None if practice else native_scorer()
            async with httpx.AsyncClient(base_url=ENDPOINT, timeout=5) as client:
                tags, version = await client.get("/api/tags"), await client.get("/api/version")
                tags.raise_for_status()
                version.raise_for_status()
                matches = [m for m in tags.json()["models"] if m["name"] == MODEL]
                if len(matches) != 1 or matches[0]["digest"] != DIGEST or (
                    version.json()["version"] != cfg["server"]
                ):
                    raise ResourceStop("model_or_server_pin")
                for item, row in zip(cfg["items"], rows, strict=True):
                    report = read_report(profile, item["report"])
                    try:
                        content = await ask(client, build_mode(profile, report, MODEL, cfg["options"]),
                                            row, "mode", watch)
                        selected_mode = choose_mode(profile, content)
                        if selected_mode != "abstain":
                            content = await ask(client, build_answer(
                                profile, report, selected_mode, MODEL, cfg["options"]),
                                row, selected_mode, watch)
                        if profile == "columns":
                            from asof.reader_columns import ColumnReport
                            from asof.reader_columns import resolve_content as column_resolve
                            if not isinstance(report, ColumnReport):
                                raise TypeError("column profile needs paragraph-aware report")
                            parsed_mode, result = column_resolve(content, report)
                        elif profile == "roles":
                            from asof.reader_roles import resolve_content
                            parsed_mode, result = resolve_content(content, report)
                        else:
                            parsed = ADAPTER.validate_json(content)
                            parsed_mode, result = parsed.mode, resolve_answer(parsed, report)
                        if parsed_mode != selected_mode:
                            raise ValueError("answer mode differs from selected mode")
                        row.update(outcome="practice_path" if practice else "answered",
                            mode=parsed_mode, values=result.values, scale=result.scale,
                            dimension=result.dimension, operation=result.operation,
                            abstention_source=result.abstention_source,
                            decline_reason=result.decline_reason, computed_by_code=result.computed_by_code)
                        if not practice:
                            case = scored_case(item)
                            if case.expected:
                                row.update(native_score(case, result.values, result.scale, scorer))
                                correct = (result.abstention_source is None and row["native_EM"] == 1
                                    and row["scale_correct"] and result.dimension == case.expected_dimension
                                    and result.operation == case.expected_operation)
                            else:
                                correct = result.abstention_source in ("model", "system")
                            row.update(correct=correct, outcome=(
                                "correct_abstention" if correct and not case.expected
                                else "correct" if correct else "abstain" if result.abstention_source
                                else "wrong"))
                    except (httpx.HTTPError, ValidationError, ValueError, KeyError) as exc:
                        row.update(outcome="failed", reason=str(exc))
                    persist()
            complete, stop = True, None
        except (ResourceStop, httpx.HTTPError, ValueError, OSError, RuntimeError) as exc:
            stop = str(exc)
        finally:
            if watch:
                watch.cancel()
                await asyncio.gather(watch, return_exceptions=True)
            for row in rows:
                if row["outcome"] in ("not_attempted", "attempt_started"):
                    row.update(outcome="failed" if row["calls"] else "not_attempted", reason=stop)
                for call in row["calls"]:
                    if call["outcome"] == "started":
                        call.update(outcome="failed", reason=stop)
            unchanged = ledger.file_sha256(cp) == output["config_SHA256"] and all(
                ledger.file_sha256(ROOT / p) == h for p, h in cfg["source_SHA256"].items())
            output.update(status="complete" if complete and unchanged else "partial",
                stop_reason=stop, calls=sum(len(r["calls"]) for r in rows),
                source_and_config_unchanged=unchanged,
                outcomes=dict(Counter(r["outcome"] for r in rows)),
                abstentions=dict(Counter(r["abstention_source"] for r in rows
                                         if r.get("abstention_source"))),
                CPU_summary=policy.summary(),
                resources={"wall_seconds": time.monotonic() - start,
                           "Python_CPU_seconds": time.process_time() - cpu_start,
                           "owned_RSS_peak_sample_bytes": memory.peak})
            if practice:
                output["format_and_resource_gate"] = (complete and unchanged and all(
                    r["outcome"] == "practice_path" for r in rows))
                output["warning"] = "Practice only; no accuracy or native scoring."
            else:
                a = sum(r["correct"] for r, i in zip(rows, cfg["items"], strict=True) if i["expected"])
                u = sum(r["correct"] for r, i in zip(rows, cfg["items"], strict=True) if not i["expected"])
                output["summary"] = {"answerable_correct": a, "answerable_total": 21,
                    "correct_abstentions": u, "unanswerable_total": 3,
                    "arithmetic_computed_by_code": sum(
                        r.get("computed_by_code", False) for r, i in zip(rows, cfg["items"], strict=True)
                        if i["category"] == "arithmetic"),
                    "pass": complete and unchanged and passed(a, u, sum(bool(r["calls"]) for r in rows))}
            persist()
            print(json.dumps({k: output.get(k) for k in (
                "status", "calls", "outcomes", "abstentions", "format_and_resource_gate",
                "summary", "resources")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("practice-freeze", "practice", "freeze", "run"))
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--change", default="NOT_PRESENT plus predeclared model/system abstentions.")
    parser.add_argument("--server-pid", type=int)
    parser.add_argument("--profile", choices=("presence", "roles", "columns"), default="presence")
    args = parser.parse_args()
    if args.phase in ("practice-freeze", "freeze"):
        freeze(args.phase == "practice-freeze", args.iteration, args.change, args.profile)
    else:
        if args.server_pid is None:
            parser.error("--server-pid required")
        asyncio.run(run(args.phase == "practice", args.iteration, args.server_pid, args.profile))
