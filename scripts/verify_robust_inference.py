"""Prespecified Batch E significance-test verification; no empirical input or ledger trials."""

from __future__ import annotations

import json
import math
import os
import time
import warnings
from collections import Counter
from datetime import UTC, datetime

from calibrate_inference import resident_bytes

SEED = 2026111401
MAX_CHARGES, MAX_CPU_SECONDS, MAX_RSS = 250000, 2700, 2 << 30
BOOTSTRAP_DRAWS = 399
LEVELS = (0.05, 0.01, 0.0027)


def allocation() -> list[dict]:
    return [
        {"kind": "harness", "dgp": "iid", "T": t, "effect_sd": 0.0, "requested": n}
        for t, n in ((17, 1334), (18, 1333), (28, 1333))
    ] + [
        {"kind": "monthly_null", "dgp": dgp, "T": t, "effect_sd": 0.0, "requested": 2000}
        for dgp in ("iid", "ar03", "t3", "factor_exposure") for t in (17, 18, 28)
    ] + [
        {"kind": "monthly_power", "dgp": "iid", "T": t, "effect_sd": effect, "requested": 500}
        for t in (17, 18, 28) for effect in (0.25, 0.5, 0.75, 1.0)
    ] + [
        {"kind": "panel_null", "dgp": dgp, "T": 7, "effect_sd": 0.0, "requested": 250}
        for dgp in ("no_year_shock", "year_shock")
    ] + [
        {"kind": "panel_power", "dgp": "no_year_shock", "T": 7,
         "effect_sd": effect, "requested": 10}
        for effect in (0.25, 0.5, 0.75, 1.0)
    ]


def planned_charges(cases: list[dict]) -> int:
    return sum(c["requested"] * (1 + BOOTSTRAP_DRAWS if c["kind"].startswith("panel") else 1)
               for c in cases)


class Budget:
    def __init__(self) -> None:
        self.started_cpu = time.process_time()
        self.started_wall = time.monotonic()
        self.data_replicates = 0
        self.bootstrap_draws = 0
        self.peak_rss = 0

    def ceiling(self, reserve: int = 0) -> str | None:
        self.peak_rss = max(self.peak_rss, resident_bytes())
        if time.process_time() - self.started_cpu >= MAX_CPU_SECONDS:
            return "CPU_ceiling"
        if self.peak_rss >= MAX_RSS:
            return "resident_memory_ceiling"
        if self.data_replicates + self.bootstrap_draws + reserve > MAX_CHARGES:
            return "replicate_charge_ceiling"
        return None


def binomial_summary(rejections: int, valid: int, unavailable: int, requested: int) -> dict:
    from scipy import stats

    def interval(k: int, n: int) -> list[float] | None:
        if not n:
            return None
        return [0.0 if not k else float(stats.beta.ppf(0.025, k, n - k + 1)),
                1.0 if k == n else float(stats.beta.ppf(0.975, k + 1, n - k))]

    rate = rejections / valid if valid else None
    worst = interval(rejections + unavailable, valid + unavailable)
    return {
        "rejections": rejections, "valid_denominator": valid, "unavailable": unavailable,
        "rate": rate, "MC_SE": None if rate is None else math.sqrt(rate * (1 - rate) / valid),
        "CP_95_interval": interval(rejections, valid),
        "worst_case_95_upper": None if worst is None else worst[1],
        "worst_case_policy": "unavailable draws are possible rejections for adoption only, not observed ones",
        "requested_data_replicates": requested,
    }


def reference_criticals(method: str, df: float | None, published: dict[float, float]) -> dict:
    from scipy import stats

    if method == "NW_fixed_b":
        return {str(a): published.get(a) for a in LEVELS}
    if method == "WCR" or (method in ("classical_OLS", "EWC", "IM") and df is None):
        return {str(a): None for a in LEVELS}
    return {str(a): float(stats.t.isf(a / 2, df) if df is not None
                          else stats.norm.isf(a / 2)) for a in LEVELS}


def main() -> None:
    if any(os.environ.get(k) != "1"
           for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        raise RuntimeError("set OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS to 1")
    budget = Budget()
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    from scipy import stats

    from asof import ledger
    from asof.config import PROJECT_ROOT
    from asof.events import FACTORS
    from asof.inference import nw_alpha
    from asof.robust_inference import (
        RobustTest,
        ewc_test,
        im_group_test,
        nw_fixed_b_test,
        significance,
        wild_cluster_restricted,
    )

    cases = allocation()
    if planned_charges(cases) != MAX_CHARGES:
        raise RuntimeError("allocation does not reconcile including nested bootstrap draws")
    streams = np.random.SeedSequence(SEED).spawn(len(cases))
    results = []
    stop_reason = None
    harness_passed = False
    complete = False

    def registered_test(method: str, estimate: float, t: float, n: int) -> RobustTest:
        if not math.isfinite(t) or not math.isfinite(estimate):
            return RobustTest(method, "not_estimable", None, None, n,
                              reasons=("nonfinite_registered_statistic",))
        return RobustTest(method, "available", estimate, t, n,
                          p_value=float(2 * stats.norm.sf(abs(t))))

    def monthly(case, rng, harness=False):
        n = case["T"]
        factors = rng.normal(0, 0.02, (n, 6))
        e = rng.standard_t(3, n) / np.sqrt(3) if case["dgp"] == "t3" else rng.normal(size=n)
        if case["dgp"] == "ar03":
            for i in range(1, n):
                e[i] = 0.3 * e[i - 1] + np.sqrt(1 - 0.3**2) * e[i]
        y = 0.03 * (e + case["effect_sd"])
        if case["dgp"] == "factor_exposure":
            y += factors @ np.array([0.8, 0.4, -0.2, 0.3, 0.1, 0.2])
        x = np.column_stack([np.ones(n), factors])
        if harness:
            fit = sm.OLS(y, x).fit()
            t = float(fit.tvalues[0])
            return {"classical_OLS": RobustTest(
                "classical_OLS", "available", float(fit.params[0]), t, n,
                p_value=float(2 * stats.t.sf(abs(t), n - x.shape[1])),
                df=n - x.shape[1])}
        registered = nw_alpha(pd.Series(y), pd.DataFrame(factors, columns=FACTORS), lags=6)
        return {
            "registered_NW6": registered_test(
                "registered_NW6", registered.alpha, registered.t_stat, n),
            "EWC": ewc_test(y, x), "NW_fixed_b": nw_fixed_b_test(y, x),
        }

    def panel(case, rng, bootstrap_seed):
        firms, years = np.repeat(np.arange(40), 7), np.tile(np.arange(7), 40)
        controls = rng.normal(size=(len(firms), 4))
        y = controls[:, 1:] @ np.array([0.2, -0.1, 0.3])
        y += rng.normal(size=40)[firms] + rng.normal(size=len(firms))
        if case["dgp"] == "year_shock":
            y += (0.6 + 0.3 * rng.normal(size=40)[firms]) * rng.normal(size=7)[years]
        y += case["effect_sd"] * controls[:, 0]
        frame = pd.DataFrame(controls, columns=["signal", "c1", "c2", "c3"])
        fe = pd.get_dummies(pd.DataFrame({"industry": (firms % 4).astype(str),
                                         "year": years.astype(str)}),
                            drop_first=True, dtype=float)
        design = sm.add_constant(pd.concat([frame, fe], axis=1))
        fit = sm.OLS(y, design).fit(cov_type="cluster",
                                   cov_kwds={"groups": np.column_stack([firms, years])})
        x = design.to_numpy()
        return {
            "registered_two_way": registered_test(
                "registered_two_way", float(fit.params["signal"]),
                float(fit.tvalues["signal"]), len(y)),
            "IM": im_group_test(
                y, x[:, 1], np.delete(x, 1, axis=1), years,
                expected_groups=tuple(range(7)), group_axis="year"),
            "WCR": wild_cluster_restricted(
                y, x, years, 1, seed=bootstrap_seed, draws=BOOTSTRAP_DRAWS,
                weights="webb", cluster_axis="year"),
        }

    try:
        for case_index, (case, stream) in enumerate(zip(cases, streams, strict=True)):
            if case_index == 3:
                harness_checks = []
                # Six comparisons: three geometries, 5%/1%; familywise 99% exact-binomial check.
                for row in results:
                    for level in (0.05, 0.01):
                        summary = row["procedures"]["classical_OLS"]["levels"][str(level)]
                        n, k = summary["valid_denominator"], summary["rejections"]
                        lower = stats.binom.ppf(0.01 / 12, n, level)
                        upper = stats.binom.ppf(1 - 0.01 / 12, n, level)
                        harness_checks.append(summary["unavailable"] == 0 and lower <= k <= upper)
                harness_passed = all(harness_checks)
                if not harness_passed:
                    stop_reason = "classical_t_harness_failed"
                    break
            data_stream, bootstrap_stream = stream.spawn(2)
            rng = np.random.default_rng(data_stream)
            boot_rng = np.random.default_rng(bootstrap_stream)
            row = {**case, "spawn_key": list(stream.spawn_key), "attempted": 0,
                   "procedures": {}, "warnings": {}}
            results.append(row)
            warning_counts: Counter[str] = Counter()
            counters = {}
            for _ in range(case["requested"]):
                reserve = 1 + BOOTSTRAP_DRAWS if case["kind"].startswith("panel") else 1
                stop_reason = budget.ceiling(reserve)
                if stop_reason:
                    break
                seed = int(boot_rng.integers(0, 2**63))
                budget.data_replicates += 1
                row["attempted"] += 1
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        tests = (panel(case, rng, seed) if case["kind"].startswith("panel")
                                 else monthly(case, rng, case["kind"] == "harness"))
                    except np.linalg.LinAlgError as exc:
                        methods = ("registered_two_way", "IM", "WCR") if reserve > 1 else (
                            ("classical_OLS",) if case["kind"] == "harness"
                            else ("registered_NW6", "EWC", "NW_fixed_b"))
                        n_obs = 40 * case["T"] if reserve > 1 else case["T"]
                        tests = {m: RobustTest(m, "not_estimable", None, None, n_obs,
                                              reasons=(f"LinAlgError:{exc}",)) for m in methods}
                warning_counts.update(f"{w.category.__name__}:{w.message}" for w in caught)
                budget.bootstrap_draws += sum(t.details.get("bootstrap_draws", 0)
                                               for t in tests.values())
                for name, test in tests.items():
                    if name not in counters:
                        criticals = reference_criticals(
                            test.method, test.df, dict(test.critical_values))
                        counters[name] = {
                            "invalid": Counter(), "minimum_p": test.minimum_p_value,
                            "reference_df": test.df, "reference_critical_values": criticals,
                            "levels": {str(a): {"k": 0, "valid": 0, "unavailable": Counter()}
                                       for a in LEVELS}}
                    c = counters[name]
                    c["minimum_p"] = max(c["minimum_p"], test.minimum_p_value)
                    if test.status != "available":
                        c["invalid"].update(test.reasons)
                    for a in LEVELS:
                        check = significance(test, a, 1 if "power" in case["kind"] else None)
                        item = c["levels"][str(a)]
                        if check.rejected is None:
                            item["unavailable"][check.reason] += 1
                        else:
                            item["valid"] += 1
                            item["k"] += int(check.rejected)
                stop_reason = budget.ceiling()
                if stop_reason:
                    break
            for name, c in counters.items():
                row["procedures"][name] = {
                    "invalid_estimate_reasons": dict(c["invalid"]),
                    "minimum_p_value": c["minimum_p"],
                    "reference_df": c["reference_df"],
                    "reference_critical_values": c["reference_critical_values"],
                    "levels": {a: {
                        **binomial_summary(v["k"], v["valid"], sum(v["unavailable"].values()),
                                           case["requested"]),
                        "unavailable_reasons": dict(v["unavailable"]),
                    } for a, v in c["levels"].items()},
                }
            row["warnings"] = dict(warning_counts)
            print(f"{case['kind']} {case['dgp']} T{case['T']} effect{case['effect_sd']}: "
                  f"{row['attempted']}/{case['requested']}", flush=True)
            if stop_reason:
                break
        complete = (len(results) == len(cases)
                    and all(r["attempted"] == r["requested"] for r in results)
                    and harness_passed and not stop_reason)
    finally:
        reliability = {}
        for geometry in ("monthly_T17", "monthly_T18", "monthly_T28", "panel_G7"):
            nulls = [r for r in results if r["kind"] in ("monthly_null", "panel_null")
                     and (geometry == f"monthly_T{r['T']}" if r["kind"] == "monthly_null"
                          else geometry == "panel_G7")]
            expected = 2 if geometry == "panel_G7" else 4
            methods = ("registered_two_way", "IM", "WCR") if geometry == "panel_G7" else (
                "registered_NW6", "EWC", "NW_fixed_b")
            reliability[geometry] = {}
            for method in methods:
                bounds = [r["procedures"][method]["levels"]["0.05"]["worst_case_95_upper"]
                          for r in nulls if method in r["procedures"]]
                evaluable = (len(bounds) == expected and all(b is not None for b in bounds)
                             and all(r["attempted"] == r["requested"] for r in nulls))
                reliability[geometry][method] = {
                    "status": ("reliable_at_this_geometry"
                               if evaluable and max(bounds) <= 0.075
                               else "unreliable_at_this_geometry" if evaluable else "not_evaluated"),
                    "worst_95_upper_5percent": max(bounds) if evaluable else None,
                }
        output = {
            "label": "SYNTHETIC ONLY; not project inference, scientific acceptance or ledger trials",
            "design_version": "BatchE-v0.5", "seed": SEED,
            "generated_utc": datetime.now(UTC).isoformat(),
            "status": "complete" if complete else "incomplete",
            "stop_reason": stop_reason if stop_reason else None if complete else "interrupted_or_failed",
            "harness_passed": harness_passed,
            "harness_rule": "5%/1% exact t(T-7) tails; six exact-binomial familywise99% checks; no invalids",
            "allocation": cases, "planned_charges": planned_charges(cases),
            "data_replicates": budget.data_replicates, "bootstrap_draws": budget.bootstrap_draws,
            "actual_charges": budget.data_replicates + budget.bootstrap_draws,
            "ceilings": {"charges": MAX_CHARGES, "CPU_seconds": MAX_CPU_SECONDS, "RAM_bytes": MAX_RSS},
            "CPU_seconds": time.process_time() - budget.started_cpu,
            "wall_seconds": time.monotonic() - budget.started_wall,
            "peak_resident_bytes": budget.peak_rss,
            "invalid_policy": "retained, no redraw; not counted as non-rejection; worst-case adoption upper",
            "critical_value_policy": "KV2005 Table I, interpolate b only. Two-sided5% supported; "
                                     "1%/0.27% lack published percentiles and are unavailable, not extrapolated.",
            "panel_WCR": "one-way year CV1; does not claim to preserve firm dependence across years",
            "power_direction": "positive planted synthetic effect; panel10replicates/effect is low precision",
            "adoption_rule": "upper endpoint of two-sided95%CP 5% null rejection <=7.5% across all fixed DGPs",
            "reliability_scope": "synthetic geometry and5% only; not rare-tail or real-data validity",
            "case_results": results, "reliability": reliability, "lineage": ledger.lineage(),
        }
        path = PROJECT_ROOT / "results" / "robust_inference_calibration.json"
        path.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
        print(f"{output['status']}: {output['actual_charges']} charges; "
              f"{output['CPU_seconds']:.2f} CPU sec", flush=True)
    if not complete:
        raise RuntimeError(f"verification incomplete: {output['stop_reason']}; evidence preserved")


if __name__ == "__main__":
    main()
