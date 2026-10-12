"""Behavior of recommend on shipments with closed-form scores."""

from routeplan import (
    Axis,
    Chosen,
    Dominated,
    Infeasible,
    Leg,
    Mode,
    NoFeasibleRoute,
    Priority,
    Route,
    Shipment,
    Transfer,
    Weights,
    generate,
    recommend,
)


def _leg(cost: float, hours: float, *, geo: float = 0.0) -> Leg:
    return Leg(Mode.SEA, cost, hours, 0.0, 0.0, geo)


def _via(hub: str, first: Leg, second: Leg) -> Route:
    return Route(first, (Transfer(hub, second),))


def _priced() -> Shipment:
    """Zero-noise routes. Balanced prices pick B. Cost-first picks A."""
    return Shipment(
        "SHP-1",
        "Rotterdam",
        "Shanghai",
        Priority.BALANCED,
        400,
        240_000,
        (
            Route(_leg(10_000, 200)),
            _via("Singapore", _leg(6_400, 60), _leg(4_200, 40)),
            _via("Colombo", _leg(7_000, 120), _leg(5_000, 100)),
            _via("Dubai", _leg(12_000, 300), _leg(8_000, 200)),
        ),
    )


def test_balanced_picks_the_faster_route_and_says_why() -> None:
    rec = recommend(_priced(), scenarios=32, seed=0)
    assert isinstance(rec, Chosen)
    assert rec.pick.label == "B"
    assert rec.pick.breakdown.total == 11_600
    assert rec.explanation.headline == (
        "Ship route B (via Singapore). It costs 6% more than the cheapest route, A, "
        "but takes 50% less time (4.2 vs 8.3 days)."
    )
    assert rec.explanation.details == (
        "Priced for a balanced shipment, B comes out $400 ahead of A. "
        "B pays $600 more in freight and expected loss, and saves $1,000 in holding.",
        "Route C (via Colombo) is dominated by A. It costs more and takes longer.",
        "Route D (via Dubai) misses the 400-hour deadline by 100 hours on its schedule.",
        "The pick holds under 17 of 18 single-price changes. "
        "It switches to A if holding is priced at 0.5x the balanced rate.",
        "Cost-first would ship A. Time-critical would also ship B. Risk-averse would also ship B.",
    )


def test_cost_first_picks_the_cheaper_quote() -> None:
    rec = recommend(_priced(), Priority.COST_FIRST.weights, scenarios=32, seed=0)
    assert isinstance(rec, Chosen)
    assert rec.pick.label == "A"
    assert rec.pick.breakdown.total == 10_600


def test_holding_probe_flips_the_near_tie() -> None:
    rec = recommend(_priced(), scenarios=32, seed=0)
    assert isinstance(rec, Chosen)
    flips = [probe for probe in rec.sensitivity.probes if probe.switches_to is not None]
    assert [(probe.axis, probe.factor, probe.switches_to) for probe in flips] == [
        (Axis.HOLDING, 0.5, "A")
    ]
    assert rec.sensitivity.by_priority[Priority.COST_FIRST] == "A"
    assert rec.sensitivity.by_priority[Priority.TIME_CRITICAL] == "B"
    assert abs(rec.sensitivity.stability - 17 / 18) < 1e-12


def test_rejected_routes_keep_their_reasons() -> None:
    rec = recommend(_priced(), scenarios=32, seed=0)
    assert isinstance(rec, Chosen)
    dominated = [item for item in rec.rejected if isinstance(item, Dominated)]
    infeasible = [item for item in rec.rejected if isinstance(item, Infeasible)]
    assert [(item.label, item.by) for item in dominated] == [("C", "A")]
    assert [(item.label, item.shortfall) for item in infeasible] == [("D", 100)]


def test_schedule_past_the_deadline_has_no_pick() -> None:
    shipment = Shipment(
        "SHP-X",
        "Rotterdam",
        "Shanghai",
        Priority.TIME_CRITICAL,
        50,
        50_000,
        (
            Route(_leg(4_000, 100)),
            _via("Singapore", _leg(3_000, 50), _leg(2_000, 30)),
        ),
    )
    rec = recommend(shipment, scenarios=16, seed=1)
    assert isinstance(rec, NoFeasibleRoute)
    assert rec.closest.label == "B"
    assert rec.closest.shortfall == 30
    assert rec.explanation.headline == (
        "No route meets the 50-hour deadline. The fastest, route B (via Singapore), "
        "is scheduled to arrive 30 hours late."
    )


def test_same_arguments_return_the_same_pick() -> None:
    kwargs = {"scenarios": 24, "seed": 3}
    assert recommend(_priced(), **kwargs) == recommend(_priced(), **kwargs)


def test_a_dearer_copy_of_the_same_legs_is_dominated() -> None:
    base = _priced()
    dear = Route(_leg(15_000, 200))
    shipment = Shipment(
        base.id,
        base.origin,
        base.destination,
        base.priority,
        base.deadline,
        base.cargo_value,
        (*base.routes, dear),
    )
    rec = recommend(shipment, scenarios=16, seed=0)
    assert isinstance(rec, Chosen)
    assert rec.pick.label == "B"
    dominated = [item for item in rec.rejected if isinstance(item, Dominated)]
    assert ("E", "A") in [(item.label, item.by) for item in dominated]


def test_a_dominated_route_ships_when_its_tail_price_is_lower() -> None:
    safe = Route(_leg(12_000, 150))
    risky = Route(_leg(10_000, 100, geo=1.0))
    shipment = Shipment(
        "SHP-DOM",
        "Rotterdam",
        "Shanghai",
        Priority.BALANCED,
        400,
        100_000,
        (risky, safe),
    )
    mean_only = Weights(0.0, 0.0, 0.0)
    tail_only = Weights(0.0, 0.0, 1.0)
    mean_pick = recommend(shipment, mean_only, scenarios=2_000, seed=0)
    tail_pick = recommend(shipment, tail_only, scenarios=2_000, seed=0)
    assert isinstance(mean_pick, Chosen)
    assert isinstance(tail_pick, Chosen)
    assert mean_pick.pick.label == "A"
    assert tail_pick.pick.label == "B"
    assert tail_pick.pick.criteria.cost > tail_pick.alternatives[0].criteria.cost
    assert tail_pick.pick.criteria.hours > tail_pick.alternatives[0].criteria.hours
    assert tail_pick.explanation.headline == (
        "Ship route B (direct). It costs 20% more than the cheapest route, A, "
        "and takes 50% longer (6.2 vs 4.2 days)."
    )
    assert (
        "B is dominated by A on expected cost, expected hours, and delay risk. "
        "Its risk-adjusted cost is $4,900 lower, so it ships."
    ) in tail_pick.explanation.details


def test_headline_uses_the_freight_quote_when_expected_loss_differs() -> None:
    risky = Route(_leg(10_000, 200, geo=1.0))
    dearer = Route(_leg(11_000, 100))
    shipment = Shipment(
        "SHP-Q",
        "Rotterdam",
        "Shanghai",
        Priority.BALANCED,
        500,
        1_000_000,
        (risky, dearer),
    )
    rec = recommend(shipment, scenarios=2_000, seed=0)
    assert isinstance(rec, Chosen)
    assert rec.pick.label == "B"
    others = {item.label: item for item in (*rec.alternatives, *rec.rejected)}
    assert rec.pick.route.cost > others["A"].route.cost
    assert rec.pick.criteria.cost < others["A"].criteria.cost
    assert rec.explanation.headline == (
        "Ship route B (direct). It costs 10% more than the cheapest route, A, "
        "but takes 50% less time (4.2 vs 8.3 days)."
    )


def test_capped_tail_probes_are_counted_once() -> None:
    rec = recommend(_priced(), Priority.RISK_AVERSE.weights, scenarios=16, seed=0)
    assert isinstance(rec, Chosen)
    tail = [probe for probe in rec.sensitivity.probes if probe.axis is Axis.TAIL]
    assert len(tail) == 4
    assert abs(max(probe.factor for probe in tail) - (1 / 0.9)) < 1e-12


def test_catalog_seed_ships_a_dominated_route_when_the_tail_is_cheaper() -> None:
    shipment = next(item for item in generate(42, 30) if item.id == "SHP-015")
    rec = recommend(shipment, scenarios=2_000, seed=42)
    assert isinstance(rec, Chosen)
    assert rec.pick.label == "E"
    assert (
        "E is dominated by B on expected cost, expected hours, and delay risk. "
        "Its risk-adjusted cost is $546 lower, so it ships. "
        "The gap is under 5% of the score, so another sample of the same routes can flip the pick."
    ) in rec.explanation.details


def test_tail_weight_avoids_the_rare_cargo_loss() -> None:
    safe = Route(_leg(20_000, 100))
    risky = _via("Singapore", _leg(9_000, 50, geo=1.0), _leg(9_000, 50, geo=1.0))
    shipment = Shipment(
        "SHP-TAIL",
        "Rotterdam",
        "Shanghai",
        Priority.BALANCED,
        1_000,
        100_000,
        (safe, risky),
    )
    mean_only = Weights(holding_per_day=0.0, lateness_per_day=0.0, tail_weight=0.0)
    tail_only = Weights(holding_per_day=0.0, lateness_per_day=0.0, tail_weight=1.0)
    mean_pick = recommend(shipment, mean_only, scenarios=2_000, seed=0)
    tail_pick = recommend(shipment, tail_only, scenarios=2_000, seed=0)
    assert isinstance(mean_pick, Chosen)
    assert isinstance(tail_pick, Chosen)
    assert mean_pick.pick.label == "B"
    assert tail_pick.pick.label == "A"
