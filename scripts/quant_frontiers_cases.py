"""Frozen known-truth cells; only the bounded controller may invoke execute_cells."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from itertools import product

T = datetime(2016, 1, 1, tzinfo=UTC)
PERIOD = date(2015, 12, 31)


@dataclass
class Cell:
    name: str
    unit: str
    planned: int
    attempted: int = 0
    completed: int = 0
    checks: int = 0
    failures: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def check(self, condition: bool, label: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append({"case": self.attempted, "check": label})


def execute_cells(plan: dict, publish: Callable[[dict], None], guard: Callable[[], None]) -> None:
    """Run the predeclared cells; no fitting/training pipeline or empirical data is used."""
    import numpy as np
    from scipy.stats import binom

    from asof.research.arrivals import Arrival, CalendarRate, MarkedHawkes
    from asof.research.control import robust_decay_plan
    from asof.research.economic import (
        MetricKey,
        Observation,
        numeric_update,
        public_innovation,
        state_as_of,
        update_belief,
    )
    from asof.research.identification import OutcomeBound, mean_bounds, payoff_bounds
    from asof.research.mechanisms import kernel_weights, project_on_twins
    from asof.research.networks import ExposureEdge, exposure_panel, leontief_total, one_hop
    from asof.research.prequential import Forecast, ForecastJournal, Settlement
    from asof.research.pricing import campbell_news, physical_probabilities
    from asof.research.trajectories import causal_trajectory, signature2

    def step(cell: Cell) -> None:
        cell.completed = cell.attempted
        guard()
        cell.attempted += 1
        if cell.attempted % 8 == 0:
            publish(asdict(cell))

    def done(cell: Cell) -> None:
        cell.completed = cell.attempted
        publish(asdict(cell))

    def rng(index: int):
        return np.random.default_rng(plan["seed"] + index)

    tolerance = plan["oracle_absolute_tolerance"]
    cell = Cell("A_economic_state_and_belief", "invented state/scenario", plan["cases_per_area"])
    random = rng(0)
    correct_risk = naive_risk = wrong_risk = 0.0
    key = MetricKey("INVENTED", "contract_backlog", "USD", "issuer", "v1")
    for i in range(cell.planned):
        step(cell)
        value = float(random.normal())
        first = Observation(key, PERIOD, T, f"source-{i}", value)
        repeat = Observation(key, PERIOD, T + timedelta(hours=1), f"repeat-{i}", value)
        revision = Observation(key, PERIOD, T + timedelta(hours=2), f"revision-{i}", value + 1)
        back = Observation(key, PERIOD, T + timedelta(hours=3), f"reversion-{i}", value)
        cell.check(public_innovation(repeat, [first]).status == "already_public",
                   "document_new_does_not_mean_value_new")
        cell.check(public_innovation(back, [first, revision]).status == "new_observed_value",
                   "reversion_is_new_relative_to_latest_state")
        cell.check(state_as_of([first, revision], T)[(key, PERIOD)] == first, "asof_excludes_future")
        cell.check(abs(numeric_update(revision, first) - 1) < tolerance, "compatible_numeric_update")
        p = random.dirichlet([2, 2])
        d = random.uniform(0.1, 0.9, 2)
        emission = random.uniform(0.1, 0.9, 2)
        for state in ("silent", "category_zero", "category_one"):
            likelihood = 1 - d if state == "silent" else d * (
                emission if state == "category_one" else 1 - emission)
            truth = p * likelihood
            mass = float(truth.sum())
            truth /= mass
            kwargs = {"observation": "silent", "disclosure_probability": d}
            if state != "silent":
                kwargs.update(observation="observed", emission_probability=(
                    emission if state == "category_one" else 1 - emission))
            posterior = update_belief(p, np.eye(2), **kwargs).posterior
            cell.check(bool(np.allclose(posterior, truth, atol=tolerance, rtol=0)),
                       "bayes_matches_enumerated_joint_probability")
            correct_risk += mass * float(truth[1] * (1 - posterior[1])**2
                                        + truth[0] * posterior[1]**2)
            naive_risk += mass * float(truth[1] * (1 - p[1])**2 + truth[0] * p[1]**2)
            wrong = update_belief(p, np.eye(2), **{
                **kwargs, "disclosure_probability": 1 - d}).posterior
            wrong_risk += mass * float(truth[1] * (1 - wrong[1])**2 + truth[0] * wrong[1]**2)
    cell.check(correct_risk <= naive_risk + tolerance, "correct_bayes_expected_brier_not_worse")
    cell.metrics = {"exact_expected_brier_correct_model": correct_risk / cell.planned,
                    "exact_expected_brier_ignore_new_evidence": naive_risk / cell.planned,
                    "exact_expected_brier_wrong_disclosure_model": wrong_risk / cell.planned,
                    "interpretation": "assumed joint model; not semantic/market validation"}
    done(cell)

    cell = Cell("B_arrival_clock", "uncensored event", plan["arrival_events"])
    random = rng(1)
    calendar = tuple(CalendarRate(T + timedelta(days=10*k), T + timedelta(days=10*(k+1)),
                                   1 if k % 2 == 0 else 4, T) for k in range(200))
    events: list[Arrival] = []
    now = T
    proposals = 0
    while len(events) < cell.planned:
        guard()
        proposals += 1
        if proposals > plan["max_arrival_proposals"]:
            raise RuntimeError("frozen arrival proposal ceiling")
        current = MarkedHawkes(calendar, tuple(events), 0.3, 0.5)
        excitation = sum(0.3 * 0.5 * e.mark * math.exp(
            -0.5 * (now-e.at).total_seconds()/86400) for e in events)
        upper = 4 + excitation
        candidate = now + timedelta(days=float(random.exponential(1 / upper)))
        if candidate >= calendar[-1].end:
            raise RuntimeError("frozen arrival calendar exhausted")
        if random.random() * upper <= current.intensity(candidate):
            events.append(Arrival(candidate, float(random.uniform())))
            step(cell)
        now = candidate
    h = MarkedHawkes(calendar, tuple(events), 0.3, 0.5)
    gaps = np.array(h.rescaled_gaps(T, events[-1].at))
    uniforms = np.sort(-np.expm1(-gaps))
    n = len(uniforms)
    statistic = float(max(np.max(np.arange(1, n+1)/n-uniforms),
                          np.max(uniforms-np.arange(n)/n)))
    bound = math.sqrt(math.log(2 / plan["arrival_dkw_delta"]) / (2*n))
    cell.check(statistic <= bound, "known_model_time_rescaling_DKW_screen")
    wrong = MarkedHawkes((CalendarRate(T, calendar[-1].end, 2.5, T),), tuple(events), 0, 0.5)
    wrong_gaps = np.array(wrong.rescaled_gaps(T, events[-1].at))
    wrong_uniforms = np.sort(-np.expm1(-wrong_gaps))
    wrong_statistic = float(max(np.max(np.arange(1, n+1)/n-wrong_uniforms),
                                np.max(wrong_uniforms-np.arange(n)/n)))
    cell.metrics = {"proposals": proposals, "rescaled_mean": float(gaps.mean()),
                    "DKW_statistic": statistic, "frozen_DKW_bound": bound,
                    "wrong_constant_calendar_statistic": wrong_statistic,
                    "wrong_model_screen_is_diagnostic_not_required_rejection": True,
                    "interpretation": "fixed-count known-parameter process; not fitted finance"}
    done(cell)

    cell = Cell("C_order_representation", "invented two-event path", plan["cases_per_area"])
    random = rng(2)
    max_error = 0.0
    for _ in range(cell.planned):
        step(cell)
        a, b = random.normal(size=(2, 3))
        path = np.stack((np.zeros(3), a, a+b))
        sig = signature2(path)
        expected = (np.outer(a, b) - np.outer(b, a))/2
        error = float(np.max(np.abs(sig.area()-expected)))
        max_error = max(max_error, error)
        cell.check(error <= tolerance, "area_matches_analytic_cross_product")
        reverse = signature2(np.stack((np.zeros(3), b, a+b)))
        cell.check(bool(np.allclose(reverse.area(), -sig.area(), atol=tolerance, rtol=0)),
                   "order_reversal_changes_area_not_endpoint")
        last_increment = path[-1]-path[-2]
        lag_area = (np.outer(path[-1]-last_increment, last_increment)
                    - np.outer(last_increment, path[-1]-last_increment))/2
        cell.check(bool(np.allclose(lag_area, sig.area(), atol=tolerance, rtol=0)),
                   "lag_twin_also_recovers_two_event_order")
        prefix = causal_trajectory([T], [a], as_of=T)
        extended = causal_trajectory([T, T+timedelta(days=1)], [a, [None]*3], as_of=T)
        cell.check(bool(np.array_equal(prefix.signature.features(), extended.signature.features())),
                   "future_unknown_values_cannot_change_past_features")
    cell.metrics = {"max_area_absolute_error": max_error,
                    "interpretation": "representation works; no advantage over full lag twin claimed"}
    done(cell)

    cell = Cell("D_typed_network", "invented stable network", plan["cases_per_area"])
    random = rng(3)
    max_error = reversed_error = 0.0
    nodes = tuple(f"INVENTED-{i}" for i in range(6))
    for _ in range(cell.planned):
        step(cell)
        a = random.uniform(0, 1, (6, 6))
        np.fill_diagonal(a, 0)
        a = 0.4 * a / a.sum(axis=1)[:, None]
        edges = [ExposureEdge(nodes[i], nodes[j], "customer_revenue", float(a[i, j]),
                              PERIOD, T, f"edge-{i}-{j}")
                 for i in range(6) for j in range(6) if i != j]
        panel = exposure_panel(nodes, edges, as_of=T, period_end=PERIOD,
                               relation="customer_revenue", complete_rows=frozenset(nodes))
        shock = random.normal(size=6)
        oracle, term = shock.copy(), shock.copy()
        for _ in range(60):
            term = a @ term
            oracle += term
        result = leontief_total(panel, shock)
        error = float(np.max(np.abs(result-oracle)))
        max_error = max(max_error, error)
        reversed_error += float(np.linalg.norm(a.T @ shock - a @ shock))
        cell.check(error <= tolerance, "linear_solve_matches_neumann_series")
        cell.check(bool(np.allclose(one_hop(panel, shock), a@shock, atol=tolerance, rtol=0)),
                   "economic_direction_preserved")
    cell.metrics = {"max_total_propagation_error": max_error,
                    "mean_error_of_reversing_exposure_direction": reversed_error/cell.planned,
                    "interpretation": "known linear exposure model, not causal stock-return evidence"}
    done(cell)

    cell = Cell("E_pricing_identities", "invented VAR/measure pair", plan["cases_per_area"])
    random = rng(4)
    max_error = wrong_measure_error = 0.0
    for _ in range(cell.planned):
        step(cell)
        a = random.uniform(-1, 1, (3, 3))
        a *= 0.65 / np.max(np.sum(np.abs(a), axis=1))
        shock, selector = random.normal(size=(2, 3))
        rho = float(random.uniform(0.8, 0.98))
        news = campbell_news(a, shock, selector, rho=rho)
        term, future = shock.copy(), np.zeros(3)
        for _ in range(180):
            term = rho * a @ term
            future += term
        error = abs(news.discount_rate_news - float(selector @ future))
        max_error = max(max_error, error)
        cell.check(error <= tolerance, "VAR_news_matches_discounted_series")
        p, kernel = random.dirichlet([2, 2, 2]), np.exp(random.normal(size=3))
        q = p * kernel
        q /= q.sum()
        recovered = physical_probabilities(q, kernel)
        cell.check(bool(np.allclose(recovered, p, atol=tolerance, rtol=0)),
                   "physical_measure_recovered_only_with_supplied_kernel")
        wrong_measure_error += float(np.linalg.norm(q-p))
    cell.metrics = {"max_VAR_series_error": max_error,
                    "mean_error_of_equating_risk_neutral_with_physical": wrong_measure_error/cell.planned,
                    "interpretation": "identity checks conditional on supplied economic model"}
    done(cell)

    cell = Cell("F_mechanism_twins", "fixed-feature algebra case", plan["cases_per_area"])
    random = rng(5)
    max_error = residual_rms = 0.0
    for _ in range(cell.planned):
        step(cell)
        phi = random.normal(size=(12, 24))
        query, targets = random.normal(size=24), random.normal(size=12)
        influence = kernel_weights(phi, query, penalty=0.5)
        primal = np.linalg.solve(phi.T@phi+0.5*np.eye(24), phi.T@targets)
        error = abs(float(influence@targets-query@primal))
        max_error = max(max_error, error)
        cell.check(error <= tolerance, "dual_influence_matches_primal")
        twins = random.normal(size=(24, 2))
        score = 0.3 + twins @ np.array([0.7, -0.4])
        projection = project_on_twins(score, twins)
        residual_rms = max(residual_rms, projection.residual_rms)
        cell.check(projection.residual_rms <= tolerance, "known_repackaging_is_mimicked")
    cell.metrics = {"max_dual_primal_error": max_error, "max_twin_reconstruction_RMS": residual_rms,
                    "interpretation": "no learned representation, financial predictor or OOS experiment"}
    done(cell)

    cell = Cell("G_robust_control", "invented convex planning problem", plan["cases_per_area"])
    random = rng(6)
    max_regret = max_stationarity = 0.0
    nominal_sacrifice = 0
    for _ in range(cell.planned):
        step(cell)
        mean = random.normal(size=2)
        cost = np.diag(random.uniform(0.1, 0.8, 2))
        previous = random.normal(scale=0.1, size=2)
        persistence = np.diag(random.uniform(0.2, 0.9, 2))
        v = random.normal(size=(4, 4))
        v = v @ v.T + np.eye(4)
        kwargs = {"horizon": 2, "risk_aversion": 1, "discount": 1, "mean_ambiguity": v}
        robust = robust_decay_plan(mean, persistence, np.eye(2), cost, previous,
                                    ambiguity_radius=0.2, **kwargs)
        nominal = robust_decay_plan(mean, persistence, np.eye(2), cost, previous,
                                     ambiguity_radius=0, **kwargs)
        flat = nominal.positions.ravel()
        nominal_worst = nominal.nominal_utility - 0.2*float(np.sqrt(flat@v@flat))
        zero_value = -0.5*float(previous@cost@previous)
        regret = max(nominal_worst, zero_value)-robust.worst_case_utility
        max_regret = max(max_regret, regret)
        max_stationarity = max(max_stationarity, robust.stationarity_error)
        cell.check(regret <= tolerance, "robust_worst_case_beats_nominal_and_zero_baselines")
        nominal_sacrifice += robust.nominal_utility < nominal.nominal_utility-tolerance
    cell.metrics = {"max_baseline_worst_case_regret": max_regret,
                    "max_stationarity_error": max_stationarity,
                    "cases_with_lower_nominal_utility_than_nominal_optimizer": nominal_sacrifice,
                    "interpretation": "robustness costs nominal utility; no real return dominance"}
    done(cell)

    cell = Cell("H_identification", "invented rectangular support", plan["cases_per_area"])
    random = rng(7)
    max_error = 0.0
    for _ in range(cell.planned):
        step(cell)
        lower = random.uniform(-1, 1, 4)
        upper = lower + random.uniform(0.1, 2, 4)
        weights = random.normal(size=4)
        supports = [OutcomeBound(float(a), float(b), False, "invented interval")
                    for a, b in zip(lower, upper, strict=True)]
        result = payoff_bounds(weights, supports)
        corners = [float(weights@np.where(bits, upper, lower)) for bits in product((0, 1), repeat=4)]
        error = max(abs(result.lower-min(corners)), abs(result.upper-max(corners)))
        max_error = max(max_error, error)
        cell.check(error <= tolerance, "rectangular_bounds_match_all_vertices")
    unbounded = payoff_bounds([-1], [OutcomeBound(-1, math.inf, False, "no upper equity bound")])
    cell.check(unbounded.lower == -math.inf, "unknown_short_not_repaired_by_zero_imputation")
    all_missing = mean_bounds([], missing_count=3, lower=-1, upper=math.inf, reason="unbounded")
    cell.check(all_missing.upper == math.inf, "entirely_missing_population_not_ignored")
    cell.metrics = {"max_vertex_enumeration_error": max_error,
                    "joint_constraint_counterexample": {
                        "rectangular_interval_for_x_plus_y": [0, 2],
                        "interval_if_x_plus_y_is_known_one": [1, 1]},
                    "interpretation": "sharp only for stated supports; not sampling confidence"}
    done(cell)

    cell = Cell("I_prequential", "exact binary null path", 2**plan["binary_horizon"])
    horizon = plan["binary_horizon"]
    alpha = plan["binary_alpha"]
    fixed_tails = {(n, k): float(binom.sf(k-1, n, 0.5))
                   for n in range(1, horizon+1) for k in range(n+1)}
    crossings = naive_crossings = 0
    f = tuple(Forecast(
        f"f{k}", f"target{k}", T, T, T, T+timedelta(days=k+1), T+timedelta(days=k+1),
        "a"*64, "b"*64, "c"*64, 0.5, 0.5, 1) for k in range(horizon))
    for path in product((0, 1), repeat=horizon):
        step(cell)
        book = ForecastJournal(f)
        count = 0
        crossed = naive_crossed = False
        log_wealth = 0.0
        for k, label in enumerate(path):
            count += label
            book = book.append(Settlement(f[k].forecast_id, f[k].target_end, label))
            log_wealth += math.log(1.5 if label else 0.5)
            crossed |= log_wealth >= math.log(1/alpha)
            naive_crossed |= fixed_tails[k+1, count] <= alpha
        score = book.score(T+timedelta(days=horizon+1))
        cell.check(abs(score.log_evalue-log_wealth) <= tolerance, "journal_matches_product_bet")
        crossings += crossed
        naive_crossings += naive_crossed
    rate = crossings/cell.planned
    cell.check(rate <= alpha, "exact_iid_binary_anytime_null_probability_at_most_alpha")
    cell.metrics = {"exact_anytime_null_crossing_probability": rate,
                    "exact_peeking_at_fixed_sample_binomial_tests_probability": naive_crossings/cell.planned,
                    "alpha": alpha, "conditional_null": "iid Bernoulli(0.5), predictable stake=1",
                    "interpretation": "exact toy-null enumeration, not financial-return inference"}
    done(cell)
