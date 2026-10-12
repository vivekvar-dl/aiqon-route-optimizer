"""Sampling stability and model-error stress tests of a frozen recommendation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import median

from routeplan._decide import DEFAULT_SCENARIOS, price, recommend, summarize
from routeplan._simulate import Environment, NOMINAL, Stream, simulate
from routeplan.model import Chosen, Dominated, Option, Shipment, Weights

STRESS_CASES = {
    "nominal": NOMINAL,
    "longer-delays": Environment(delay_length_scale=1.5),
    "underestimated-events": Environment(delay_probability_scale=1.5, disruption_scale=2.0),
    "regional-shocks": Environment(regional_shock_probability=0.10, regional_shock_hours=72.0),
    "combined": Environment(
        delay_probability_scale=1.5, delay_length_scale=1.5, disruption_scale=2.0,
        regional_shock_probability=0.10, regional_shock_hours=72.0,
    ),
}


@dataclass(frozen=True, slots=True)
class Sampling:
    seeds: tuple[int, ...]
    picks: dict[str, int]
    reference_agreement: float | None
    modal_pick: str | None
    modal_share: float | None
    median_score_gap: float | None


@dataclass(frozen=True, slots=True)
class Stress:
    name: str
    environment: Environment
    on_time: float
    on_time_interval95: tuple[float, float]
    p90_hours: float
    mean_cost: float
    risk_adjusted_cost: float
    best_mean_route: str
    mean_regret: float
    best_risk_route: str
    risk_regret: float


@dataclass(frozen=True, slots=True)
class Audit:
    shipment_id: str
    reference_pick: str | None
    planning_scenarios: int
    realizations: int
    sampling: Sampling
    stresses: tuple[Stress, ...]


def audit(
    shipment: Shipment, weights: Weights | None = None, *, seed: int = 7,
    runs: int = 20, scenarios: int = DEFAULT_SCENARIOS, realizations: int = 5_000,
) -> Audit:
    """Change planning seeds, then stress the original pick without re-optimizing it."""
    if isinstance(runs, bool) or not isinstance(runs, int) or not 1 <= runs <= 100:
        raise ValueError("runs must be an int from 1 to 100")
    if isinstance(realizations, bool) or not isinstance(realizations, int) or realizations < 1:
        raise ValueError("realizations must be at least 1")
    prices = shipment.priority.weights if weights is None else weights
    reference = recommend(shipment, prices, seed=seed, scenarios=scenarios)
    if not isinstance(reference, Chosen):
        return Audit(shipment.id, None, scenarios, realizations, Sampling((), {}, None, None, None, None), ())
    seeds = tuple(range(seed + 1, seed + runs + 1))
    counts: Counter[str] = Counter()
    gaps = []
    for planning_seed in seeds:
        rec = recommend(shipment, prices, seed=planning_seed, scenarios=scenarios)
        assert isinstance(rec, Chosen)  # Schedule eligibility is independent of simulation.
        counts[rec.pick.label] += 1
        scores = sorted(
            item.breakdown.total
            for item in (rec.pick, *rec.alternatives, *rec.rejected)
            if isinstance(item, (Option, Dominated))
        )
        if len(scores) > 1:
            gaps.append(scores[1] - scores[0])
    modal = min(counts, key=lambda label: (-counts[label], label))
    sampling = Sampling(
        seeds, dict(sorted(counts.items())), counts[reference.pick.label] / runs,
        modal, counts[modal] / runs, median(gaps) if gaps else None,
    )
    stresses = tuple(
        _stress(shipment, reference.pick.label, prices, name, environment, seed, realizations)
        for name, environment in STRESS_CASES.items()
    )
    return Audit(shipment.id, reference.pick.label, scenarios, realizations, sampling, stresses)


def _stress(
    shipment: Shipment, picked: str, prices: Weights, name: str,
    environment: Environment, seed: int, realizations: int,
) -> Stress:
    eligible = [(label, route) for label, route in shipment.labeled() if route.hours <= shipment.deadline]
    draws = {
        label: simulate(
            shipment, route, scenarios=realizations, seed=seed,
            stream=Stream.REALITY, environment=environment,
        ) for label, route in eligible
    }
    priced = {label: price(shipment, route, draws[label], prices) for label, route in eligible}
    means = {label: item.total - item.tail for label, item in priced.items()}
    best_mean = min(means, key=lambda label: (means[label], label))
    best_risk = min(priced, key=lambda label: (priced[label].total, label))
    criteria = summarize(shipment, shipment.route(picked), draws[picked])
    return Stress(
        name, environment, 1 - criteria.late, criteria.on_time_interval95, criteria.p90_hours,
        means[picked], priced[picked].total, best_mean, means[picked] - means[best_mean],
        best_risk, priced[picked].total - priced[best_risk].total,
    )
