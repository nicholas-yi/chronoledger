from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from asof.research.mechanisms import kernel_weights, project_on_twins
from asof.research.networks import (
    ExposureEdge,
    exposure_panel,
    leontief_total,
    one_hop,
    shared_counterparty_similarity,
)

T = datetime(2016, 1, 1, tzinfo=UTC)
PERIOD = date(2015, 12, 31)
NODES = ("INVENTED-A", "INVENTED-B", "INVENTED-HUB")


def edge(affected: str, fraction: float | None) -> ExposureEdge:
    return ExposureEdge(affected, NODES[2], "customer_revenue", fraction, PERIOD, T, "fiction")


def panel(edges, *, complete=frozenset(NODES), as_of=T):
    return exposure_panel(NODES, edges, as_of=as_of, period_end=PERIOD,
                          relation="customer_revenue", complete_rows=complete)


def test_economic_hub_exposure_is_directed_and_not_similarity_idf() -> None:
    p = panel([edge(NODES[0], 0.4), edge(NODES[1], 0.6)])
    np.testing.assert_allclose(one_hop(p, [0, 0, -1]), [-0.4, -0.6, 0])
    np.testing.assert_allclose(leontief_total(p, [0, 0, -1]), [-0.4, -0.6, -1])
    assert p.values[2, 0] == 0
    np.testing.assert_allclose(shared_counterparty_similarity([[1], [1]]), np.ones((2, 2)))
    # Computing a similarity operator does not downweight a ubiquitous economic exposure.
    assert p.values[0, 2] == 0.4 and p.values[1, 2] == 0.6


def test_unknown_future_and_inferred_edges_cannot_become_zero_or_historical_exposure() -> None:
    first = edge(NODES[0], 0.4)
    future = replace(first, fraction=0.9, known_at=T + timedelta(days=1), source_id="later")
    assert panel([first, future]).values[0, 2] == 0.4
    partial = panel([first], complete=frozenset())
    assert partial.unknown_pairs
    with pytest.raises(ValueError, match="unknown economic"):
        one_hop(partial, [0, 0, -1])
    with pytest.raises(ValueError, match="unknown economic"):
        one_hop(panel([edge(NODES[0], None)]), [0, 0, -1])
    with pytest.raises(ValueError, match="model-inferred"):
        panel([replace(first, explicitly_stated=False)])
    with pytest.raises(ValueError, match="conflicting"):
        panel([first, replace(first, source_id="other", fraction=0.5)])


def test_propagation_stability_and_similarity_support_are_not_silent_defaults() -> None:
    edges = [ExposureEdge("A", "B", "customer_revenue", 1, PERIOD, T, "one"),
             ExposureEdge("B", "A", "customer_revenue", 1, PERIOD, T, "two")]
    p = exposure_panel(("A", "B"), edges, as_of=T, period_end=PERIOD,
                       relation="customer_revenue", complete_rows=frozenset(("A", "B")))
    with pytest.raises(ValueError, match="not stable"):
        leontief_total(p, [1, 0])
    with pytest.raises(ValueError, match="empty"):
        shared_counterparty_similarity([[0, 0], [1, 0]])
    with pytest.raises(ValueError, match="binary"):
        shared_counterparty_similarity([[0.3, 1], [1, 0]])


def test_dual_ridge_weights_match_independent_primal_normal_equations() -> None:
    phi = np.array([[1, 2, 0], [0, 1, 1], [2, 0, 1], [1, 1, 1]], dtype=float)
    query = np.array([0.3, 0.7, -0.2])
    y = np.array([1.0, -2.0, 0.5, 1.5])
    weights = kernel_weights(phi, query, penalty=0.4)
    primal = np.linalg.solve(phi.T @ phi + 0.4 * np.eye(3), phi.T @ y)
    assert weights @ y == pytest.approx(query @ primal)
    with pytest.raises(ValueError, match="strictly positive"):
        kernel_weights(phi, query, penalty=0)


def test_mechanism_twin_recovers_known_linear_repackaging_without_inference() -> None:
    twin = np.array([-2, -1, 0, 1, 2], dtype=float)
    result = project_on_twins(3 + 2 * twin, twin[:, None])
    assert result.intercept == pytest.approx(3)
    np.testing.assert_allclose(result.coefficients, [2])
    assert result.residual_rms < 1e-12 and result.explained_fraction == pytest.approx(1)
    constant = project_on_twins(np.ones(5), twin[:, None])
    assert constant.explained_fraction is None
    with pytest.raises(ValueError, match="rank deficient"):
        project_on_twins(twin, np.column_stack((twin, twin)))
    with pytest.raises(ValueError, match="degrees of freedom"):
        project_on_twins([1, 2], [[1], [2]])
