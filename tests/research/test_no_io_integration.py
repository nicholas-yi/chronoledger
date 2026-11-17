import builtins
import socket
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from asof import ledger
from asof.research.arrivals import CalendarRate, MarkedHawkes
from asof.research.control import robust_decay_plan
from asof.research.economic import MetricKey, Observation, public_innovation, update_belief
from asof.research.identification import OutcomeBound, payoff_bounds
from asof.research.mechanisms import kernel_weights, project_on_twins
from asof.research.networks import ExposureEdge, exposure_panel, one_hop
from asof.research.prequential import Forecast, ForecastJournal, Settlement
from asof.research.pricing import campbell_news
from asof.research.trajectories import causal_trajectory


def test_all_nine_reference_directions_work_without_file_network_or_trial_io(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("offline mathematical functions attempted file/network/trial I/O")

    t = datetime(2016, 1, 1, tzinfo=UTC)
    later = t + timedelta(days=1)
    with monkeypatch.context() as m:
        m.setattr(builtins, "open", forbidden)
        m.setattr(socket.socket, "connect", forbidden)
        m.setattr(ledger, "log_trial", forbidden)
        key = MetricKey("INVENTED-A", "backlog", "USD", "issuer", "v1")
        obs = Observation(key, date(2015, 12, 31), t, "invented evidence", 1)
        assert public_innovation(obs, ()).status == "new_observed_value"
        belief = update_belief([0.5, 0.5], np.eye(2), observation="silent",
                               disclosure_probability=[0.2, 0.8])
        assert belief.posterior[0] == pytest.approx(0.8)
        arrival = MarkedHawkes((CalendarRate(t, later, 1, t),), (), 0, 1)
        assert arrival.compensator(t, later) == 1
        path = causal_trajectory([t, later], [[0, 0], [1, -1]], as_of=later)
        assert path.event_count == 2
        edge = ExposureEdge("A", "B", "customer_revenue", 0.2,
                            date(2015, 12, 31), t, "invented statement")
        panel = exposure_panel(("A", "B"), [edge], as_of=t, period_end=edge.period_end,
                               relation=edge.relation, complete_rows=frozenset(("A", "B")))
        assert one_hop(panel, [0, -1])[0] == pytest.approx(-0.2)
        assert campbell_news([[0]], [1], [1], rho=0.9).cash_flow_news == 1
        assert len(kernel_weights([[1], [2]], [1], penalty=1)) == 2
        assert project_on_twins([1, 3, 5, 7], [[0], [1], [2], [3]]).residual_rms < 1e-12
        control = robust_decay_plan(
            [1], [[0.5]], [[1]], [[0]], [0], horizon=1, risk_aversion=1, discount=1,
            mean_ambiguity=[[1]], ambiguity_radius=0.2)
        assert control.positions[0, 0] == pytest.approx(0.8)
        assert payoff_bounds([-1], [OutcomeBound(-1, float("inf"), False, "unknown")]).unbounded
        f = Forecast("f", "invented target", t, t, t, later, later,
                     "a" * 64, "b" * 64, "c" * 64, 0.8, 0.5, 1)
        book = ForecastJournal().append(f).append(Settlement("f", later, 1))
        assert book.score(later).scored == 1
