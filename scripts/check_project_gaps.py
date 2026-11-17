"""Bounded, explicitly authorized clock-document and local-runtime checks only."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
import run_full_timestamps as common
from reader_real1_memory import OwnedMemory
from run_reader_positive_control import WindowsCPU

from asof import ledger
from asof.config import DATA_DIR, PROJECT_ROOT, user_agent
from asof.filing_timestamp_a1 import BorrowedMeasuredTransport, QpcLimiter
from asof.filing_timestamp_audit import AuditGuard
from asof.local_model_runtime import RuntimePolicy, verify_runtime_receipt
from asof.reader_real2_guards import SustainedCPU
from asof.sec_documentation import DocumentationStop, StrictSecDocumentation

PRIVATE = DATA_DIR / "project_closure"
ROOT_URLS = [
    "https://www.sec.gov/search-filings/public-dissemination-service-system-contact",
    "https://www.sec.gov/submit-filings/filer-support-resources",
]
CACHED = DATA_DIR / "sec_stage1_refetch" / "request_48.bin"
HISTORICAL_MANUAL = "https://www.sec.gov/files/edgar/filermanual/archive/efmvol2-v60.pdf"
MODEL = "qwen3.5:4b"
DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"
OPTIONS = {"num_ctx": 16384, "num_predict": 64, "num_thread": 4, "num_batch": 128,
           "num_gpu": 0, "temperature": 0, "seed": 2026111411}
PROMPTS = [
    "Invented runtime smoke test only. Reply with the word READY.",
    ("Invented runtime smoke test only. A fictitious box has 12 red tokens and 8 blue tokens. "
     "Reply with their total as a single number."),
    "Invented runtime smoke test only. Reply with the word FINISHED.",
]


def official_url(url: str) -> bool:
    value = urlsplit(url)
    return (value.scheme == "https" and value.netloc == "www.sec.gov"
            and not value.query and not value.fragment
            and not value.path.lower().startswith("/archives/"))


def official_links(raw: bytes, source: str) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    return sorted({urljoin(source, h) for h in re.findall(r'href=["\']([^"\']+)', text)
                   if official_url(urljoin(source, h))})


def freeze(args) -> None:
    if args.config.exists():
        raise RuntimeError("closure check already frozen")
    if args.check == "smoke":
        value = {"check": "smoke", "policy": RuntimePolicy().manifest(), "model": MODEL,
                 "digest": DIGEST, "options": OPTIONS, "prompts": PROMPTS,
                 "max_calls": 3, "wall_from_owned_server_start_seconds": 540,
                 "per_call_timeout_seconds": 120, "memory_bytes": 10 << 30,
                 "limits": "Invented inputs only; no training/QA score or long-report efficacy "
                           "claim. Keep one minute of the approved10min for owned-tree cleanup."}
    else:
        if getattr(args, "large_manual", False) and not args.from_report:
            raise ValueError("large-manual amendment requires its stopped retrieval receipt")
        budget = json.loads(common.BUDGET.read_bytes())
        used = budget["actual_HTTP_attempts"] - 3246
        if not 0 <= used < 10 or budget["ceiling"] != 34402:
            raise ValueError("closure documentation budget changed or exhausted")
        if args.from_report:
            previous = json.loads(args.from_report.read_bytes())
            large = getattr(args, "large_manual", False)
            if large:
                if (previous["status"] != "stopped_final"
                        or previous.get("stop_reason") != "declared_body_at_read_cap"
                        or previous["last_receipt"]["url"] != HISTORICAL_MANUAL
                        or args.url != [HISTORICAL_MANUAL]):
                    raise ValueError("explicit cap amendment applies only to the same historical manual")
                known = {HISTORICAL_MANUAL}
            elif previous["status"] != "retrieved_requires_review":
                raise ValueError("documentation audit stopped; no implicit continuation")
            else:
                known = {u for r in previous["documents"] for u in r["official_links"]}
            urls = args.url or []
            if not urls or any(u not in known for u in urls):
                raise ValueError("follow-up URLs must be observed links in complete official pages")
            provenance = common.pin([args.from_report.resolve()])
        else:
            urls = ROOT_URLS
            known = official_links(CACHED.read_bytes(),
                "https://www.sec.gov/search-filings/edgar-application-programming-interfaces")
            if any(u not in known for u in urls):
                raise ValueError("root links do not reproduce from cached official navigation")
            provenance = common.pin([CACHED])
        if len(set(urls)) != len(urls) or len(urls) > 10-used or not all(map(official_url, urls)):
            raise ValueError("exact official documentation allowlist or max10 budget violated")
        value = {"check": "clock", "URLs": urls, "budget_start": budget["actual_HTTP_attempts"],
                 "ceiling": 34402, "closure_max_new_requests": 10, "source_provenance": provenance,
                 "UA_SHA256": hashlib.sha256(user_agent().encode()).hexdigest(),
                 "protocol": "QPC>=0.667s,serial,30stotal,4MiBbody,no retries/redirects; "
                             "any error/cap stops. Official docs only,no Archives/filings.",
                 "clock_certification": "No automatic qualification; review field-specific text "
                                        "and historical applicability separately."}
        value["read_cap_bytes"] = (32 if getattr(args, "large_manual", False) else 4) << 20
        if getattr(args, "large_manual", False):
            value["protocol"] = value["protocol"].replace("4MiBbody", "32MiBbody")
            value["explicit_cap_approval"] = (
                "User historical_manual=true after seeing declared23159215bytes; one amended "
                "GET under existing ten-request quota, no redirect or retry.")
    value["source_SHA256"] = common.pin([
        Path(__file__), PROJECT_ROOT / "src" / "asof" / "local_model_runtime.py",
        PROJECT_ROOT / "src" / "asof" / "sec_documentation.py"])
    value["authorization"] = "User whole-project closure approval via ask_user,2026-11-17."
    common.atomic_json(args.config, value)
    print(json.dumps({"frozen": str(args.config), "check": args.check}))


class OneDocument(StrictSecDocumentation):
    max_attempts = 1
    historical_ceiling = 34402
    authorized_total_ceiling = 34402
    supported_read_caps = (65536, 4 << 20, 32 << 20)

    def __init__(self, urls, *args, **kwargs):
        if kwargs.get("read_cap_bytes") == 32 << 20 and urls != (HISTORICAL_MANUAL,):
            raise ValueError("32MiB cap is restricted to the explicitly approved manual")
        super().__init__(urls, *args, **kwargs)


async def clock_check(config: dict, directory: Path) -> dict:
    if json.loads(common.BUDGET.read_bytes()) != {
        "actual_HTTP_attempts": config["budget_start"], "ceiling": 34402
    } or hashlib.sha256(user_agent().encode()).hexdigest() != config["UA_SHA256"]:
        raise ValueError("documentation baseline/User-Agent changed")
    common.verify(config["source_provenance"])
    guard = AuditGuard(common.suspend_clocks, lambda: 0, wall_seconds=600)
    limiter = QpcLimiter()
    result = {"check": "clock", "status": "in_progress", "documents": [],
              "new_requests": 0, "historical_clock_qualified": False}
    async with httpx.AsyncHTTPTransport(retries=0) as inner:
        try:
            for url in config["URLs"]:
                guard.check()
                expected = config["budget_start"] + result["new_requests"] + 1
                measured = BorrowedMeasuredTransport(inner, limiter, guard, url, expected)
                async with OneDocument((url,), common.BUDGET,
                    directory / f"request_{expected}.jsonl", directory,
                    transport=measured, read_cap_bytes=config.get("read_cap_bytes", 4 << 20)) as client:
                    measured.emit = client.append
                    try:
                        raw = await client.fetch(url)
                        guard.check()
                    finally:
                        if client.last_record and client.last_record["attempted"]:
                            result["new_requests"] += 1
                            result["last_receipt"] = client.last_record
                links = official_links(raw, url) if b"%PDF" != raw[:4] else []
                result["documents"].append({
                    "URL": url, "bytes": len(raw), "SHA256": hashlib.sha256(raw).hexdigest(),
                    "content_type": client.last_record["content_type"], "official_links": links,
                    "cache_file": client.last_record["cache_file"],
                    "review": "Requires field-specific/manual version review,not automatic UTC authority."})
            result["status"] = "retrieved_requires_review"
        except (DocumentationStop, OSError, ValueError) as exc:
            result.update(status="stopped_final", stop_reason=str(exc))
    result["counter"] = json.loads(common.BUDGET.read_bytes())
    return result


async def stop_owned(records: list[dict]) -> None:
    parents = {r["pid"]: r["parent_pid"] for r in records}

    def depth(pid: int) -> int:
        seen = set()
        while pid in parents and pid not in seen:
            seen.add(pid)
            pid = parents[pid]
        return len(seen)

    for record in sorted(records, key=lambda r: depth(r["pid"]), reverse=True):
        pid, created = record["pid"], record["creation_filetime"]
        command = (
            f"$p=Get-Process -ErrorAction Stop | Where-Object {{$_.Id -eq {pid}}};"
            f"if($p){{if($p.StartTime.ToUniversalTime().ToFileTimeUtc() -ne {created})"
            "{throw 'owned_PID_reused'};"
            f"Stop-Process -Id {pid} -Force -ErrorAction Stop}}")
        process = await asyncio.create_subprocess_exec(
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, error = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"owned cleanup failed:{error.decode(errors='replace')}")


async def smoke_check(config: dict, directory: Path, pid: int, receipt: Path) -> dict:
    verify_runtime_receipt(receipt, pid, config["policy"])
    context = {"phase": "runtime_smoke", "call_id": "readiness"}
    memory = OwnedMemory(pid, telemetry_path=directory / "per_PID_memory.jsonl", context=context)
    memory.sample()
    records = list(memory.telemetry.previous.values())
    created = next(r["created_UTC"] for r in records if r["pid"] == pid)
    started = datetime.fromisoformat(created)
    cpu, sustained = WindowsCPU(), SustainedCPU()
    sustained.activate()
    guard = AuditGuard(common.suspend_clocks, lambda: 0, wall_seconds=540)
    result = {"check": "smoke", "status": "in_progress", "calls_started": 0,
              "calls_complete": 0, "policy": config["policy"], "owned_server_PID": pid}

    async def watch() -> None:
        nonlocal records
        previous = time.perf_counter()
        while True:
            await asyncio.sleep(1)
            guard.check()
            if (datetime.now(UTC) - started).total_seconds() >= 540:
                raise RuntimeError("owned_model_smoke_wall_cap")
            if memory.sample() >= 10 << 30:
                raise RuntimeError("owned_model_smoke10GiB_cap")
            records = list(memory.telemetry.previous.values())
            now = time.perf_counter()
            if sustained.add(previous, now, cpu.percent(), datetime.now(UTC).isoformat()):
                raise RuntimeError("sustained_host_CPU_stop")
            previous = now

    watcher = asyncio.create_task(watch())
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11435",
                                    trust_env=False, follow_redirects=False) as client:
            response = await client.get("/api/tags", timeout=10)
            response.raise_for_status()
            if not any(r.get("name") == MODEL and r.get("digest") == DIGEST
                       for r in response.json()["models"]):
                raise RuntimeError("existing_model_digest_missing_no_pull")
            for index, prompt in enumerate(config["prompts"]):
                if result["calls_started"] >= 3:
                    raise RuntimeError("smoke_call_cap")
                context["call_id"] = str(index+1)
                result["calls_started"] += 1
                request = asyncio.create_task(client.post("/api/chat", json={
                    "model": MODEL, "messages": [{"role": "user", "content": prompt}],
                    "stream": False, "think": False, "keep_alive": "5m", "options": OPTIONS,
                }, timeout=120))
                try:
                    done, _ = await asyncio.wait((request, watcher), return_when=asyncio.FIRST_COMPLETED)
                    if watcher in done:
                        await watcher
                    response = await request
                    response.raise_for_status()
                    raw = response.json()
                    if raw.get("done") is not True:
                        raise RuntimeError("incomplete_smoke_response")
                    if memory.sample() >= 10 << 30:
                        raise RuntimeError("owned_model_smoke10GiB_cap")
                    records = list(memory.telemetry.previous.values())
                    result["calls_complete"] += 1
                finally:
                    if not request.done():
                        request.cancel()
                        try:
                            await request
                        except asyncio.CancelledError:
                            pass
        result["status"] = "three_invented_calls_complete_requires_native_log_review"
    except (RuntimeError, ValueError, OSError, httpx.HTTPError) as exc:
        result.update(status="stopped_final", stop_reason=str(exc))
    finally:
        if not watcher.done():
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass
        elif not watcher.cancelled():
            watcher.exception()
        result.update(peak_owned_RSS=memory.peak, sleep_interruptions=guard.interruptions,
                      CPU=sustained.summary(), elapsed_since_server_start_seconds=(
                          datetime.now(UTC)-started).total_seconds())
        await stop_owned(records)
    return result


async def run(args) -> None:
    config = json.loads(args.config.read_bytes())
    common.verify(config["source_SHA256"])
    if ledger.lineage()["git_dirty"]:
        raise RuntimeError("commit bounded check config/source before execution")
    relative = args.config.resolve().relative_to(PROJECT_ROOT).as_posix()
    process = await asyncio.create_subprocess_exec(
        "git", "show", f"HEAD:{relative}", cwd=PROJECT_ROOT,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    committed, error = await process.communicate()
    if process.returncode or committed != args.config.read_bytes():
        raise RuntimeError(f"uncommitted check configuration:{error.decode(errors='replace')}")
    name = args.config.stem
    directory = PRIVATE / name
    directory.mkdir(parents=True, exist_ok=False)
    status = PROJECT_ROOT / "results" / f"{name}_report.json"
    result = {"status": "interrupted_final", "check": config["check"]}
    try:
        if config["check"] == "clock":
            result = await clock_check(config, directory)
        else:
            if args.pid is None or args.receipt is None:
                raise ValueError("explicit owned server PID/receipt required")
            result = await smoke_check(config, directory, args.pid, args.receipt)
    except (RuntimeError, ValueError, OSError, httpx.HTTPError) as exc:
        result.update(status="stopped_final", stop_reason=str(exc))
    finally:
        error = sys.exception()
        if error is not None:
            result["unhandled_error"] = f"{type(error).__name__}:{error}"
        result.update(config_SHA256=ledger.file_sha256(args.config),
                      source_revision=ledger.lineage()["git_commit"],
                      private_directory=str(directory.relative_to(PROJECT_ROOT)))
        common.atomic_json(status, result)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    parser.add_argument("--check", choices=("clock", "smoke"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--from-report", type=Path)
    parser.add_argument("--url", action="append")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--large-manual", action="store_true")
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze(args)
    else:
        asyncio.run(run(args))
