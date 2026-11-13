"""Download SEC nightly bulk archives (all XBRL company facts and all submissions) with resume."""

from __future__ import annotations

import sys

import httpx

from asof.config import RAW_DIR, user_agent

FILES = {
    "companyfacts.zip": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
    "submissions.zip": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
}


def download(name: str, url: str) -> None:
    out = RAW_DIR / "bulk" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".part")
    with httpx.Client(headers={"User-Agent": user_agent()}, timeout=120, follow_redirects=True) as c:
        total = int(c.head(url).headers["Content-Length"])
        if out.exists() and out.stat().st_size == total:
            print(f"{name}: already complete", file=sys.stderr)
            return
        start = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={start}-"} if start else {}
        with c.stream("GET", url, headers=headers) as r, part.open("ab" if start else "wb") as fh:
            r.raise_for_status()
            for i, chunk in enumerate(r.iter_bytes(1 << 20)):
                fh.write(chunk)
                if i % 200 == 0:
                    print(f"{name}: {(start + fh.tell()) / 1e9:.2f}/{total / 1e9:.2f} GB", file=sys.stderr, flush=True)
    if part.stat().st_size != total:
        raise RuntimeError(f"{name}: incomplete download")
    part.replace(out)
    print(f"{name}: done", file=sys.stderr)


if __name__ == "__main__":
    for n, u in FILES.items():
        download(n, u)
