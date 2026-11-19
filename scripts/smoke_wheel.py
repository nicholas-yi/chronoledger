"""Build and smoke-test wheel contents outside the checkout; no data/network or new dependencies."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-python", type=Path, default=Path(sys.executable),
                        help="interpreter with the hash-locked build backend already installed")
    args = parser.parse_args(argv)
    lock = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
    backend = re.search(r"(?m)^uv-build==([^\s\\;]+)", lock)
    if backend is None:
        raise RuntimeError("hash-locked build backend missing from requirements-dev.lock")
    env = os.environ.copy()
    env["UV_OFFLINE"] = "1"
    env["UV_PYTHON_DOWNLOADS"] = "never"
    env.pop("ASOF_USER_AGENT", None)
    backend_version = subprocess.check_output(
        [str(args.build_python), "-I", "-c",
         "import importlib.metadata; print(importlib.metadata.version('uv-build'))"],
        env=env, text=True, timeout=30).strip()
    if backend_version != backend[1]:
        raise RuntimeError("installed build backend differs from the committed dependency lock")
    with tempfile.TemporaryDirectory(prefix="asof-wheel-smoke-") as directory:
        owned = Path(directory).resolve()
        wheels = owned / "wheel"
        subprocess.run([
            "uv", "build", "--wheel", "--offline", "--no-build-isolation",
            "--python", str(args.build_python),
            "--out-dir", str(wheels),
        ], cwd=ROOT, env=env, check=True, timeout=120)
        candidates = list(wheels.glob("asof-*.whl"))
        if len(candidates) != 1:
            raise RuntimeError("expected exactly one project wheel")
        installed = owned / "installed"
        subprocess.run([
            "uv", "pip", "install", "--offline", "--no-deps", "--no-index",
            "--python", sys.executable, "--target", str(installed), str(candidates[0]),
        ], cwd=owned, env=env, check=True, timeout=60)
        code = """
import contextlib, importlib.resources, io, json, pathlib, sys
target = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))
import asof
if not pathlib.Path(asof.__file__).resolve().is_relative_to(target):
    raise RuntimeError("source/editable package shadowed the installed wheel")
from asof.cli import main
from asof.research.control import robust_decay_plan
if not importlib.resources.files("asof").joinpath("nw_fixed_b_kv2005.csv").is_file():
    raise RuntimeError("required package reference CSV absent from wheel")
output = io.StringIO()
with contextlib.redirect_stdout(output):
    main(["demo"])
result = json.loads(output.getvalue())
if (result["evidence_kind"] != "invented_fixture_not_market_evidence"
        or result["accounting"]["status"] != "consistent"
        or result["order"]["first_area"] != -0.5):
    raise RuntimeError("wheel demo result differs from the invented contract")
print(json.dumps({"installed_wheel_imported": True, "reference_csv_present": True,
                  "invented_demo_passed": True, "source_checkout_used_for_package": False}))
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", code, str(installed)],
            cwd=owned, env=env, check=True, capture_output=True, text=True, timeout=60)
        print(result.stdout.strip())
        summary = json.loads(result.stdout)
        if not summary["installed_wheel_imported"] or not summary["invented_demo_passed"]:
            raise RuntimeError("invalid wheel smoke receipt")
    print("Owned temporary build/install removed; project environment unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
