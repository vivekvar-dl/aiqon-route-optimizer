"""What optimal means: a feasible schedule, then the lowest risk-adjusted landed cost."""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

from routeplan._explain import explain_choice, explain_infeasible
from routeplan._simulate import Outcomes, Stream, simulate
from routeplan.model import (
    Axis,
    Breakdown,
    Chosen,
    Criteria,
    Dominated,
    Infeasible,
    NoFeasibleRoute,
    Option,
    Priority,
    Probe,
    Route,
    Sensitivity,
    Shipment,
    Weights,
)

DEFAULT_SCENARIOS = 2_000
TAIL_SHARE = 0.10
SENSITIVITY_FACTORS = (0.5, 0.67, 0.8, 1.25, 1.5, 2.0)


class _Contender(NamedTuple):
    label: str
    route: Route
    criteria: Criteria
    outcomes: Outcomes


def recommend(
    shipment: Shipment,
    weights: Weights | None = None,
    *,
    scenarios: int = DEFAULT_SCENARIOS,
    seed: int = 0,
) -> Chosen | NoFeasibleRoute:
    """Pick a route. Each route is simulated once. Probes re-price those outcomes."""
    prices = shipment.priority.weights if weights is None else weights
    contenders = tuple(
        _Contender(label, route, *_summary(shipment, route, scenarios, seed))
        for label, route in shipment.labeled()
    )
    feasible = tuple(item for item in contenders if item.route.hours <= shipment.deadline)
    infeasible = tuple(
        sorted(
            (
                Infeasible(
                    item.label,
                    item.route,
                    item.criteria,
                    item.route.hours - shipment.deadline,
                )
                for item in contenders
                if item.route.hours > shipment.deadline
            ),
            key=lambda item: (item.shortfall, item.label),
        )
    )
    if not feasible:
        closest, *others = infeasible
        return NoFeasibleRoute(
            shipment.id,
            prices,
            closest,
            tuple(others),
            explain_infeasible(shipment.deadline, closest),
        )
    owners = dominated_by({item.label: item.criteria for item in feasible})
    ranked = sorted((_option(shipment, item, prices) for item in feasible), key=_rank)
    pick, *rest = ranked
    alternatives = tuple(item for item in rest if item.label not in owners)
    dominated = tuple(
        Dominated(item.label, item.route, item.criteria, owners[item.label], item.breakdown)
        for item in rest
        if item.label in owners
    )
    sensitivity = _probe(shipment, feasible, prices, pick.label)
    rejected: tuple[Dominated | Infeasible, ...] = (*dominated, *infeasible)
    explanation = explain_choice(
        shipment.deadline,
        prices,
        pick,
        tuple(alternatives),
        rejected,
        sensitivity,
        owners.get(pick.label),
    )
    return Chosen(
        shipment.id,
        prices,
        pick,
        tuple(alternatives),
        rejected,
        sensitivity,
        explanation,
    )


def dominated_by(criteria: dict[str, Criteria]) -> dict[str, str]:
    labels = sorted(criteria)
    frontier = [
        label
        for label in labels
        if not any(_dominates(criteria[other], criteria[label]) for other in labels if other != label)
    ]
    found: dict[str, str] = {}
    for label in labels:
        if label in frontier:
            continue
        found[label] = next(owner for owner in frontier if _dominates(criteria[owner], criteria[label]))
    return found


def summarize(shipment: Shipment, route: Route, outcomes: Outcomes) -> Criteria:
    loss = float(outcomes.loss.mean())
    hours = float(outcomes.hours.mean())
    late = float(np.mean(outcomes.hours > shipment.deadline))
    return Criteria(route.cost + loss, hours, late)


def landed_cost(
    shipment: Shipment,
    route: Route,
    outcomes: Outcomes,
    weights: Weights,
) -> np.ndarray:
    """The only pricing formula. Score, probes, and evaluation all call it."""
    per_hour = shipment.cargo_value / 24.0
    late_hours = np.maximum(outcomes.hours - shipment.deadline, 0.0)
    return (
        route.cost
        + outcomes.loss
        + weights.holding_per_day * per_hour * outcomes.hours
        + weights.lateness_per_day * per_hour * late_hours
    )


def price(shipment: Shipment, route: Route, outcomes: Outcomes, weights: Weights) -> Breakdown:
    per_hour = shipment.cargo_value / 24.0
    late_hours = np.maximum(outcomes.hours - shipment.deadline, 0.0)
    freight = route.cost
    expected_loss = float(outcomes.loss.mean())
    holding = float(weights.holding_per_day * per_hour * outcomes.hours.mean())
    lateness = float(weights.lateness_per_day * per_hour * late_hours.mean())
    costs = landed_cost(shipment, route, outcomes, weights)
    premium = max(0.0, cvar(costs) - float(costs.mean()))
    return Breakdown(freight, expected_loss, holding, lateness, weights.tail_weight * premium)


def cvar(values: np.ndarray, share: float = TAIL_SHARE) -> float:
    count = max(1, math.ceil(share * len(values)))
    tail = np.partition(values, -count)[-count:]
    return float(tail.mean())


def _summary(
    shipment: Shipment, route: Route, scenarios: int, seed: int
) -> tuple[Criteria, Outcomes]:
    outcomes = simulate(shipment, route, scenarios=scenarios, seed=seed, stream=Stream.PLAN)
    return summarize(shipment, route, outcomes), outcomes


def _option(shipment: Shipment, contender: _Contender, weights: Weights) -> Option:
    return Option(
        contender.label,
        contender.route,
        contender.criteria,
        price(shipment, contender.route, contender.outcomes, weights),
    )


def _rank(option: Option) -> tuple[float, float, str]:
    return (option.breakdown.total, option.criteria.cost, option.label)


def _best(shipment: Shipment, frontier: tuple[_Contender, ...], weights: Weights) -> str:
    return min((_option(shipment, item, weights) for item in frontier), key=_rank).label


def _probe(
    shipment: Shipment,
    feasible: tuple[_Contender, ...],
    weights: Weights,
    pick: str,
) -> Sensitivity:
    seen = {(weights.holding_per_day, weights.lateness_per_day, weights.tail_weight)}
    probes: list[Probe] = []
    for axis in Axis:
        for factor in SENSITIVITY_FACTORS:
            scaled = weights.scaled(axis, factor)
            key = (scaled.holding_per_day, scaled.lateness_per_day, scaled.tail_weight)
            if key in seen:
                continue
            seen.add(key)
            best = _best(shipment, feasible, scaled)
            probes.append(Probe(axis, _applied_factor(weights, scaled, axis), None if best == pick else best))
    by_priority = {priority: _best(shipment, feasible, priority.weights) for priority in Priority}
    return Sensitivity(tuple(probes), by_priority)


def _applied_factor(weights: Weights, scaled: Weights, axis: Axis) -> float:
    base = getattr(weights, axis.value)
    applied = getattr(scaled, axis.value)
    if base == 0:
        return 1.0
    return applied / base


def _dominates(left: Criteria, right: Criteria) -> bool:
    better_or_equal = (
        left.cost <= right.cost and left.hours <= right.hours and left.late <= right.late
    )
    strictly = left.cost < right.cost or left.hours < right.hours or left.late < right.late
    return better_or_equal and strictly
