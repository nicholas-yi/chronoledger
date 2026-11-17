"""Bounded anonymous HTTPS intake for the explicitly selected benchmark files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx
from check_finqa_years import QUARANTINE, check_quarantine

from asof.config import DATA_DIR
from asof.document_scope import DocumentDates, require_eligible_documents

MAX_BYTES = 50_000_000
ROOT = DATA_DIR / "bench_1"
TATQA = "870accc41953dcde885aabeb963d94aabdc0fbc3"
FINQA = "0f16e2867befa6840783e58be38c9efb9229d742"

ASSETS = {
    "tatqa": [
        ("dataset_raw/tatqa_dataset_dev.json", Path("tatqa") / "dev.json", "48075c812af3fe6698b1d5cb50d9dbf358d52784"),
        ("tatqa_eval.py", Path("tatqa") / "tatqa_eval.py", "5d40665e0a52630ba078aefa0a31144bc7cba8bc"),
        ("tatqa_metric.py", Path("tatqa") / "tatqa_metric.py", "80f45360fd5303110b9e31ad1b54ad6dfd3f9d18"),
        ("tatqa_utils.py", Path("tatqa") / "tatqa_utils.py", "2c7c7246a73330af3bd290bf746ca9014ef73ebb"),
        ("LICENSE", Path("tatqa") / "LICENSE", "7855a66ee0e672eda63b018d8b0d37f848b4015a"),
        ("README.md", Path("tatqa") / "README.md", "13718343e75798a4708851c54af99e1daf7b4397"),
    ],
    "finqa_quarantine": [
        ("dataset/dev.json", Path("quarantine") / "finqa_dev.json", "970f239f591c782b17df420c0d343b780737f3da"),
    ],
    "finqa_scorer": [
        ("code/evaluate/evaluate.py", Path("finqa") / "evaluate.py", "4829a4ca58a5725fb3f7a46b3b23b7f7e848a512"),
        ("code/utils/general_utils.py", Path("finqa") / "general_utils.py", "bcd54fab833ae6dbcecd0dc562014fff59a96e15"),
        ("LICENSE", Path("finqa") / "LICENSE", "fb3b513238ba5ec7e0799cb1190ff30c759a5bdf"),
        ("README.md", Path("finqa") / "README.md", "8fc89f8402714c39385a80c3d7d5e947ae27fcab"),
    ],
}


def file_identity(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob_sha1": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()}


def fetch(
    client: httpx.Client, url: str, path: Path, expected: str, *,
    documents: tuple[DocumentDates, ...] | None = None,
) -> dict:
    require_eligible_documents(documents)
    if path.exists():
        existing = file_identity(path)
        if existing["git_blob_sha1"] != expected:
            raise ValueError("existing scoped file differs from pin; do not overwrite silently")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    count = 0
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if response.is_redirect or "text/html" in response.headers.get("content-type", ""):
                raise ValueError("redirect/login/HTML is not an allowed benchmark download")
            if int(response.headers.get("content-length", "0")) > MAX_BYTES:
                raise ValueError("benchmark file exceeds 50 MB")
            with partial.open("wb") as out:
                for chunk in response.iter_bytes():
                    count += len(chunk)
                    if count > MAX_BYTES:
                        raise ValueError("benchmark file exceeds 50 MB")
                    out.write(chunk)
        identity = file_identity(partial)
        if identity["git_blob_sha1"] != expected:
            raise ValueError("downloaded Git blob differs from the pin; no parse permitted")
        partial.replace(path)
        return identity
    except (httpx.HTTPError, OSError, ValueError):
        partial.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=tuple(ASSETS))
    phase = parser.parse_args().phase
    if phase == "finqa_scorer":
        _, safe = check_quarantine(QUARANTINE)
        if not safe:
            raise ValueError("FinQA identity check rejected the quarantine; skip it")
    repository = "NExTplusplus/TAT-QA" if phase == "tatqa" else "czyssrs/FinQA"
    revision = TATQA if phase == "tatqa" else FINQA
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "intake.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": []}
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        for source, target, expected in ASSETS[phase]:
            url = f"https://raw.githubusercontent.com/{repository}/{revision}/{source}"
            identity = fetch(client, url, ROOT / target, expected)
            entry = {"path": str(target), "url": url, "expected_git_blob_sha1": expected, **identity}
            manifest["files"] = [r for r in manifest["files"] if r["path"] != str(target)]
            manifest["files"].append(entry)
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(json.dumps({"path": str(target), **identity}), flush=True)


if __name__ == "__main__":
    main()
