from itertools import product

import numpy as np
import pytest
import statsmodels.api as sm
from scipy import stats

from asof.robust_inference import (
    RobustTest,
    bartlett_variance,
    ewc_test,
    future_robust_gate,
    im_group_test,
    nw_fixed_b_test,
    significance,
    wild_cluster_restricted,
)


def test_ewc_type_ii_mean_projection_and_student_reference() -> None:
    t = np.arange(8) + 0.5
    y = 3 + 2 * np.cos(np.pi * t / 8) + 3 * np.cos(2 * np.pi * t / 8)
    result = ewc_test(y, np.ones((8, 1)))
    assert result.df == 1
    assert result.estimate == pytest.approx(3)
    assert result.standard_error == pytest.approx(np.sqrt(2))
    assert result.p_value == pytest.approx(2 * stats.t.sf(3 / np.sqrt(2), 1))


@pytest.mark.parametrize(("n", "nu", "critical"), [
    (17, 2, 3.043),
    (18, 2, 2.976),
    (28, 3, 2.707),
])
def test_monthly_factor_score_and_published_fixed_b_values(n, nu, critical) -> None:
    rng = np.random.default_rng(n)
    x = np.column_stack([np.ones(n), rng.normal(size=(n, 6))])
    y = 0.2 + x[:, 1:] @ np.arange(6) + rng.normal(size=n)
    cosine = ewc_test(y, x)
    assert cosine.df == nu
    scaled = ewc_test(7 * y, x)
    assert scaled.t_stat == pytest.approx(cosine.t_stat)
    nw = nw_fixed_b_test(y, x)
    reference = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": nw.details["maxlags"]})
    assert nw.t_stat == pytest.approx(reference.tvalues[0], rel=1e-11)
    assert dict(nw.critical_values)[0.05] == pytest.approx(critical, rel=1e-14)
    assert significance(nw, 0.01).rejected is None
    assert significance(nw, 0.0027).rejected is None


def test_im_uses_unweighted_registered_groups_and_keeps_infeasible_groups() -> None:
    groups = np.repeat(np.arange(3), 3)
    signal = np.tile([-1.0, 0.0, 1.0], 3)
    y = signal * np.repeat([1.0, 2.0, 3.0], 3) + np.tile([1.0, -2.0, 1.0], 3)
    result = im_group_test(y, signal, np.zeros((9, 1)), groups,
                           expected_groups=[0, 1, 2], group_axis="year")
    assert result.estimate == pytest.approx(2)
    assert result.t_stat == pytest.approx(2 * np.sqrt(3))
    assert result.df == 2
    invalid = im_group_test(y, signal, signal[:, None], groups,
                            expected_groups=[0, 1, 2], group_axis="year")
    assert invalid.status == "not_estimable"
    assert len(invalid.details["groups"]) == 3
    missing = im_group_test(y, signal, np.zeros((9, 0)), groups,
                            expected_groups=[0, 1, 2, 3], group_axis="year")
    assert missing.details["groups"][-1]["status"] == "not_estimable"
    assert missing.df is None  # not opportunistically reduced to q=3


def _cluster_data(g=3):
    rng = np.random.default_rng(21)
    groups = np.repeat(np.arange(g), 5)
    x = np.column_stack([np.ones(len(groups)), rng.normal(size=len(groups))])
    y = 0.4 * x[:, 1] + rng.normal(size=len(groups)) + rng.normal(size=g)[groups]
    return x, y, groups


def test_wcr_compressed_algorithm_matches_full_refits_with_webb_enumeration() -> None:
    x, y, groups = _cluster_data()
    result = wild_cluster_restricted(y, x, groups, 1, seed=1, cluster_axis="month")
    observed = sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": groups})
    restricted = np.repeat(y.mean(), len(y))
    u_r = y - restricted
    support = [-np.sqrt(1.5), -1, -np.sqrt(0.5), np.sqrt(0.5), 1, np.sqrt(1.5)]
    ts = []
    for w in product(support, repeat=3):
        bootstrap = restricted + u_r * np.asarray(w)[groups]
        fit = sm.OLS(bootstrap, x).fit(cov_type="cluster", cov_kwds={"groups": groups})
        ts.append(fit.tvalues[1])
    expected = np.mean(np.abs(ts) >= abs(observed.tvalues[1]) * (1 - 1e-10) - 1e-12)
    assert result.t_stat == pytest.approx(observed.tvalues[1], rel=1e-12)
    assert result.p_value == pytest.approx(expected)
    assert result.details["enumerated"] and result.details["bootstrap_draws"] == 216
    assert result.minimum_p_value == pytest.approx(1 / 36)


def test_rademacher_seven_cluster_floor_and_monte_carlo_resolution() -> None:
    x, y, groups = _cluster_data(7)
    exact = wild_cluster_restricted(y, x, groups, 1, seed=1,
                                    weights="rademacher", cluster_axis="month")
    assert exact.details["bootstrap_draws"] == 128
    assert exact.minimum_p_value == 1 / 64
    assert significance(exact, 0.01).rejected is None
    monte = wild_cluster_restricted(y, x, groups, 1, seed=1,
                                    max_enumeration=1, cluster_axis="month")
    assert monte.minimum_p_value == 1 / 400
    assert significance(monte, float(2 * stats.norm.sf(3.2))).rejected is None
    repeat = wild_cluster_restricted(y, x, groups, 1, seed=1,
                                     max_enumeration=1, cluster_axis="month")
    assert monte == repeat


def test_robust_gate_requires_valid_assumptions_reliability_and_estimability() -> None:
    x, y, _ = _cluster_data(7)
    test = ewc_test(y, x)
    for test_input, assumptions, reliability in ((None, True, True), (test, None, True),
                                                (test, True, False)):
        gate = future_robust_gate("monthly", 2, 1, test_input,
                                  registered_passed=True, assumptions_met=assumptions,
                                  reliable_at_geometry=reliability)
        assert gate.status == "undetermined"
    x, y, groups = _cluster_data(7)
    bootstrap = wild_cluster_restricted(y, x, groups, 1, seed=1, cluster_axis="month")
    im = im_group_test(y, x[:, 1], x[:, :1], groups,
                       expected_groups=list(range(7)), group_axis="month")
    gate = future_robust_gate("event", 3.2, 1, bootstrap, assumptions_met=True,
                              registered_passed=True, reliable_at_geometry=True, crosscheck=im)
    assert gate.status == "undetermined"  # B=399 cannot attain the registered level


def test_nonfinite_inputs_are_not_dropped_and_zero_variance_is_unavailable() -> None:
    with pytest.raises(ValueError, match="finite"):
        ewc_test(np.array([1, np.nan, 2]), np.ones((3, 1)))
    assert ewc_test(np.ones(8), np.ones((8, 1))).status == "not_estimable"


def test_im_month_crosscheck_cannot_veto_or_rescue_the_wcr_decision() -> None:
    wcr = RobustTest("WCR", "available", 1.0, 10.0, 100,
                     p_value=0.001, minimum_p_value=0.001, details={"cluster_axis": "month"})
    im = RobustTest("IM", "available", 0.01, 0.1, 100, p_value=0.9, df=16,
                    details={"group_axis": "month", "registered_group_count": 17})
    gate = future_robust_gate("event", 3.2, 1, wcr, registered_passed=True,
                              assumptions_met=True, reliable_at_geometry=True, crosscheck=im)
    assert gate.status == "supported"
    rejected = RobustTest("WCR", "available", 0.01, 0.1, 100,
                          p_value=0.9, details={"cluster_axis": "month"})
    assert future_robust_gate(
        "event", 3.2, 1, rejected, registered_passed=True, assumptions_met=True,
        reliable_at_geometry=True, crosscheck=im).status == "not_supported"


def test_low_nu_rare_level_hold_is_not_mathematical_zero_power_or_a_registered_rescue() -> None:
    result = RobustTest("EWC", "available", 1.0, 100.0, 18, p_value=0.0001, df=2)
    assert significance(result, 0.0027).rejected
    assert future_robust_gate(
        "monthly", 3.0, 1, result, registered_passed=True, assumptions_met=True,
        reliable_at_geometry=True).status == "undetermined"
    assert future_robust_gate(
        "monthly", 2.0, 1, result, registered_passed=False, assumptions_met=None,
        reliable_at_geometry=None).status == "not_supported"


def test_research_o3_default_projection_cannot_manufacture_a_t_statistic() -> None:
    result = ewc_test(np.array([2.0, 0.0, 0.0, 2.0]), np.ones((4, 1)))
    assert result.status == "not_estimable"


@pytest.mark.parametrize(("bandwidth", "expected_variance"), [(2, 5 / 16), (3, 1 / 4), (4, 3 / 16)])
def test_research_o4_o5_o6_bandwidth_is_not_the_registered_maxlag(
    bandwidth, expected_variance,
) -> None:
    influence = (np.array([0.0, 0.0, 2.0, 2.0]) - 1) / 4
    assert bartlett_variance(influence, bandwidth) == pytest.approx(expected_variance)
