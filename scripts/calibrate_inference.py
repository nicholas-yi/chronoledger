"""Batch A's fixed synthetic calibration, with hard replicate/CPU/resident-memory ceilings."""

from __future__ import annotations

import ctypes
import json
import math
import os
import sys
import time
import warnings
from collections import Counter
from datetime import UTC, datetime

SEED = 2026111322
MAX_REPLICATES, MAX_CPU_SECONDS, MAX_RSS = 2000, 900, 1 << 30


def resident_bytes() -> int:
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]

        values = Counters()
        values.cb = ctypes.sizeof(values)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(values), values.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(values.PeakWorkingSetSize)
    import resource

    scale = 1 if sys.platform == "darwin" else 1024
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale)


def main() -> None:
    if any(os.environ.get(k) != "1" for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")):
        raise RuntimeError("Set OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1 before launching")
    started_cpu, started_wall = time.process_time(), time.monotonic()
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    from scipy.stats import norm

    from asof import ledger
    from asof.config import PROJECT_ROOT
    from asof.events import FACTORS
    from asof.inference import nw_alpha

    cases = [
        {"kind": "monthly_null", "dgp": dgp, "T": t, "effect_sd": 0.0, "requested": 150}
        for dgp in ("iid", "ar03", "t3", "factor_exposure") for t in (18, 28)
    ] + [
        {"kind": "monthly_power", "dgp": "iid", "T": t, "effect_sd": effect, "requested": 100}
        for t in (18, 28) for effect in (0.5, 1.0)
    ] + [
        {"kind": "panel_null", "dgp": dgp, "T": 7, "effect_sd": 0.0, "requested": 200}
        for dgp in ("no_year_shock", "year_shock")
    ]
    assert sum(c["requested"] for c in cases) == MAX_REPLICATES
    streams = np.random.SeedSequence(SEED).spawn(len(cases))
    thresholds = (2.0, 3.0, 3.2)
    completed = 0
    peak_rss = 0
    stop_reason = None
    results = []

    def ceiling() -> str | None:
        nonlocal peak_rss
        peak_rss = max(peak_rss, resident_bytes())
        if time.process_time() - started_cpu >= MAX_CPU_SECONDS:
            return "CPU_ceiling"
        if peak_rss >= MAX_RSS:
            return "resident_memory_ceiling"
        return None

    def statistic(case, rng) -> float:
        if case["kind"].startswith("monthly"):
            t = case["T"]
            f = pd.DataFrame(rng.normal(0, 0.02, (t, 6)), columns=FACTORS)
            e = rng.standard_t(3, t) / np.sqrt(3) if case["dgp"] == "t3" else rng.normal(size=t)
            if case["dgp"] == "ar03":
                for i in range(1, t):
                    e[i] = 0.3 * e[i - 1] + np.sqrt(1 - 0.3**2) * e[i]
            r = 0.03 * (e + case["effect_sd"])
            if case["dgp"] == "factor_exposure":
                r += f.to_numpy() @ np.array([0.8, 0.4, -0.2, 0.3, 0.1, 0.2])
            return nw_alpha(pd.Series(r), f, lags=6).t_stat
        firms, years = np.repeat(np.arange(40), 7), np.tile(np.arange(7), 40)
        industry = (firms % 4).astype(str)
        x = rng.normal(size=(len(firms), 4))
        y = x[:, 1:] @ np.array([0.2, -0.1, 0.3])
        y += rng.normal(size=40)[firms] + rng.normal(size=len(firms))
        if case["dgp"] == "year_shock":
            y += (0.6 + 0.3 * rng.normal(size=40)[firms]) * rng.normal(size=7)[years]
        controls = pd.DataFrame(x, columns=["signal", "c1", "c2", "c3"])
        fe = pd.get_dummies(pd.DataFrame({"industry": industry, "year": years.astype(str)}),
                            drop_first=True, dtype=float)
        design = sm.add_constant(pd.concat([controls, fe], axis=1))
        groups = np.column_stack([firms, years])
        fit = sm.OLS(y, design).fit(cov_type="cluster", cov_kwds={"groups": groups})
        return float(fit.tvalues["signal"])

    for case, stream in zip(cases, streams, strict=True):
        rng = np.random.default_rng(stream)
        valid = attempted = 0
        rejected = {str(t): 0 for t in thresholds}
        invalid: Counter[str] = Counter()
        warning_counts: Counter[str] = Counter()
        for _ in range(case["requested"]):
            stop_reason = ceiling()
            if stop_reason or completed >= MAX_REPLICATES:
                break
            failure_reason = None
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    value = statistic(case, rng)
                except np.linalg.LinAlgError as exc:
                    value = float("nan")
                    failure_reason = f"LinAlgError:{exc}"
            for warning in caught:
                warning_counts[f"{warning.category.__name__}:{warning.message}"] += 1
            attempted += 1
            completed += 1
            if math.isfinite(value):
                valid += 1
                for threshold in thresholds:
                    rejected[str(threshold)] += abs(value) >= threshold
            else:
                invalid[failure_reason or "nonfinite_statistic"] += 1
            stop_reason = ceiling()
            if stop_reason:
                break
        summaries = {}
        for threshold in thresholds:
            rate = rejected[str(threshold)] / valid if valid else None
            summaries[str(threshold)] = {
                "rejections": rejected[str(threshold)], "valid_denominator": valid,
                "rate": rate, "monte_carlo_se": None if rate is None
                else math.sqrt(rate * (1 - rate) / valid),
                "normal_two_sided_nominal": float(2 * norm.sf(threshold)),
            }
        results.append({
            **case, "spawn_key": list(stream.spawn_key), "attempted": attempted, "valid": valid,
            "invalid_estimates": attempted - valid, "invalid_reasons": dict(invalid),
            "warnings": dict(warning_counts), "thresholds": summaries,
        })
        print(f"{case['kind']} {case['dgp']} T{case['T']} effect{case['effect_sd']}: "
              f"{attempted}/{case['requested']}, {attempted-valid} invalid",
              file=sys.stderr, flush=True)
        if stop_reason:
            break
    output = {
        "label": "SYNTHETIC ONLY; not project inference, scientific acceptance or ledger trials",
        "design_version": "BatchA-v0.3", "seed": SEED, "generated_utc": datetime.now(UTC).isoformat(),
        "status": "complete" if completed == MAX_REPLICATES and not stop_reason else "incomplete",
        "stop_reason": stop_reason, "requested_replicates": MAX_REPLICATES,
        "attempted_replicates": completed, "CPU_seconds": time.process_time() - started_cpu,
        "wall_seconds": time.monotonic() - started_wall, "peak_sampled_resident_bytes": peak_rss,
        "ceilings": {"replicates": MAX_REPLICATES, "CPU_seconds": MAX_CPU_SECONDS, "RAM_bytes": MAX_RSS},
        "budget_check": "before and after each small fit; stop at first observed ceiling",
        "invalid_policy": "retained, not redrawn or counted as non-rejections",
        "allocation": cases, "case_results": results, "lineage": ledger.lineage(),
    }
    path = PROJECT_ROOT / "results" / "synthetic_inference_calibration.json"
    path.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(f"{output['status']}: {completed} attempts, {output['CPU_seconds']:.2f} CPU seconds, "
          f"{peak_rss / 2**20:.1f} MiB sampled RSS", file=sys.stderr)


if __name__ == "__main__":
    main()
