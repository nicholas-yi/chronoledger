import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def _script():
    spec = importlib.util.spec_from_file_location(
        "development_diagnostics", Path(__file__).resolve().parents[1] / "scripts" /
        "development_diagnostics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_comparison_is_exact_not_tolerance_and_allows_only_new_fields() -> None:
    script = _script()
    assert script.differences({"mean": 0.1}, {"mean": 0.1, "series": []}) == []
    assert script.differences({"mean": 0.1}, {"mean": np.nextafter(0.1, 1.0)})


def test_diagnostic_preserves_registered_count_and_declines_short_pbo() -> None:
    script = _script()
    matrix = pd.DataFrame(np.random.default_rng(4).normal(size=(17, 3)),
                          index=pd.period_range("2023-03", periods=17, freq="M"),
                          columns=["a", "b", "c"])
    larger_n = script.current_family_diagnostic(matrix, 10)
    smaller_n = script.current_family_diagnostic(matrix, 3)
    assert larger_n["registered_N"] == 10 and larger_n["current_columns"] == 3
    assert larger_n["PBO"]["status"] == "not_estimable"
    assert larger_n["full_historical_family_DSR"]["status"] == "unavailable"
    assert larger_n["SR_benchmark"] > smaller_n["SR_benchmark"]
