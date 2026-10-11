"""Compare the recommender with the quote sort, the schedule sort, and a hindsight oracle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from routeplan._decide import DEFAULT_SCENARIOS, dominated_by, landed_cost, recommend
from routeplan._simulate import Outcomes, Stream, simulate
from routeplan.model import Chosen, Criteria, NoFeasibleRoute, Priority, Shipment

DEFAULT_REALIZATIONS = 1_000


class Policy(StrEnum):
    RECOMMENDED = "recommended"
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    ORACLE = "oracle"


@dataclass(frozen=True, slots=True)
class Realized:
    pick: str
    cost: float
    on_time: float
    feasible: bool
    pareto: bool


@dataclass(frozen=True, slots=True)
class Row:
    shipment: str
    priority: Priority
    recommendation: Chosen | NoFeasibleRoute
    realized: dict[Policy, Realized]


@dataclass(frozen=True, slots=True)
class PolicyStats:
    total_cost: float
    cost_ratio: float
    on_time_rate: float
    feasible_rate: float
    pareto_rate: float
    mean_regret: float


@dataclass(frozen=True, slots=True)
class Report:
    rows: tuple[Row, ...]
    stats: dict[Policy, PolicyStats]
    stability: float
    infeasible: int


def evaluate(
    shipments: tuple[Shipment, ...] | list[Shipment],
    *,
    scenarios: int = DEFAULT_SCENARIOS,
    realizations: int = DEFAULT_REALIZATIONS,
    seed: int = 0,
) -> Report:
    """Replay each policy on arrivals drawn from a stream the planner never saw."""
    if not shipments:
        raise ValueError("evaluate needs at least one shipment")
    rows: list[Row] = []
    for shipment in shipments:
        recommendation = recommend(shipment, scenarios=scenarios, seed=seed)
        rows.append(_row(shipment, recommendation, realizations, seed))
    return _aggregate(tuple(rows))


def _row(
    shipment: Shipment,
    recommendation: Chosen | NoFeasibleRoute,
    realizations: int,
    seed: int,
) -> Row:
    outcomes = {
        label: simulate(shipment, route, scenarios=realizations, seed=seed, stream=Stream.REALITY)
        for label, route in shipment.labeled()
    }
    means = {
        label: float(landed_cost(shipment, shipment.route(label), draw, shipment.priority.weights).mean())
        for label, draw in outcomes.items()
    }
    owners = dominated_by(_criteria(recommendation))
    labels = {
        Policy.RECOMMENDED: _recommended_label(recommendation),
        Policy.CHEAPEST: min(shipment.labeled(), key=lambda item: (item[1].cost, item[0]))[0],
        Policy.FASTEST: min(shipment.labeled(), key=lambda item: (item[1].hours, item[0]))[0],
        Policy.ORACLE: min(means, key=lambda label: (means[label], label)),
    }
    realized = {
        policy: _realized(shipment, label, outcomes[label], means[label], label not in owners)
        for policy, label in labels.items()
    }
    return Row(shipment.id, shipment.priority, recommendation, realized)


def _realized(
    shipment: Shipment,
    label: str,
    outcomes: Outcomes,
    cost: float,
    pareto: bool,
) -> Realized:
    on_time = float(np.mean(outcomes.hours <= shipment.deadline))
    return Realized(label, cost, on_time, shipment.route(label).hours <= shipment.deadline, pareto)


def _criteria(recommendation: Chosen | NoFeasibleRoute) -> dict[str, Criteria]:
    if isinstance(recommendation, Chosen):
        items = (recommendation.pick, *recommendation.alternatives, *recommendation.rejected)
    else:
        items = (recommendation.closest, *recommendation.others)
    return {item.label: item.criteria for item in items}


def _recommended_label(recommendation: Chosen | NoFeasibleRoute) -> str:
    if isinstance(recommendation, Chosen):
        return recommendation.pick.label
    return recommendation.closest.label


def _aggregate(rows: tuple[Row, ...]) -> Report:
    stats: dict[Policy, PolicyStats] = {}
    for policy in Policy:
        costs = [row.realized[policy].cost for row in rows]
        recommended = [row.realized[Policy.RECOMMENDED].cost for row in rows]
        oracle = [row.realized[Policy.ORACLE].cost for row in rows]
        ratios = [cost / base if base else 1.0 for cost, base in zip(costs, recommended, strict=True)]
        regrets = [cost - best for cost, best in zip(costs, oracle, strict=True)]
        picked = [row.realized[policy] for row in rows]
        stats[policy] = PolicyStats(
            sum(costs),
            sum(ratios) / len(ratios),
            sum(item.on_time for item in picked) / len(picked),
            sum(item.feasible for item in picked) / len(picked),
            sum(item.pareto for item in picked) / len(picked),
            sum(regrets) / len(regrets),
        )
    chosen = [row.recommendation for row in rows if isinstance(row.recommendation, Chosen)]
    stability = (
        sum(item.sensitivity.stability for item in chosen) / len(chosen) if chosen else 0.0
    )
    infeasible = sum(isinstance(row.recommendation, NoFeasibleRoute) for row in rows)
    return Report(rows, stats, stability, infeasible)
