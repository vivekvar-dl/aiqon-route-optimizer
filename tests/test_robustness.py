"""Model errors, correlated events, and finite-sample uncertainty have distinct meanings."""

from dataclasses import replace

import numpy as np
import pytest

from routeplan import Environment, Leg, Mode, Policy, Priority, Route, Shipment, Transfer, audit, evaluate, generate
from routeplan._network import BY_NAME, air_km, sea_path
from routeplan._simulate import NOMINAL, Stream, simulate
from routeplan._statistics import wilson_interval
from routeplan._decide import recommend
from test_decisions import _leg, _priced


def test_maritime_distances_use_waterway_detours() -> None:
    for start, end in (("Rotterdam", "Istanbul"), ("New York", "Los Angeles"), ("Istanbul", "Dubai")):
        distance, path = sea_path(start, end)
        assert path[0] == start and path[-1] == end
        assert distance > air_km(BY_NAME[start], BY_NAME[end]) * 1.2
        assert distance == pytest.approx(sea_path(end, start)[0])
    assert sea_path("New York", "Los Angeles")[1] == ("New York", "Los Angeles")


def test_generated_catalog_has_sea_air_transfers_and_no_ocean_crossing_rail() -> None:
    for seed in (7, 11, 42):
        for shipment in generate(seed, 50):
            assert [leg.mode for leg in shipment.routes[2].legs] == [Mode.SEA, Mode.AIR]
            assert all(leg.mode in (Mode.SEA, Mode.AIR) for route in shipment.routes for leg in route.legs)
            for route in shipment.routes:
                stops = (shipment.origin, *route.hubs, shipment.destination)
                assert len(set(stops)) == len(stops)
                navigation = [stops[0]]
                for start, end, leg in zip(stops, stops[1:], route.legs):
                    if leg.mode is Mode.SEA:
                        distance, path = sea_path(start, end)
                        assert leg.hours == round(distance / 32 + 16, 2)
                        navigation.extend(path[1:])
                    else:
                        navigation.append(end)
                assert len(set(navigation)) == len(navigation)


def test_region_event_is_shared_across_routes_and_applied_once() -> None:
    direct = Route(_leg(1_000, 100))
    transfer = Route(_leg(500, 40), (Transfer("Istanbul", _leg(500, 60)),))
    shipment = Shipment("SHP-COMMON", "Rotterdam", "Hamburg", Priority.BALANCED, 200, 10_000, (direct, transfer))
    kwargs = dict(scenarios=1_000, seed=7, stream=Stream.REALITY)
    environment = Environment(regional_shock_probability=0.3)
    first = simulate(shipment, direct, environment=environment, **kwargs)
    second = simulate(shipment, transfer, environment=environment, **kwargs)
    np.testing.assert_array_equal(first.hours, second.hours)
    other_shipment = simulate(replace(shipment, id="SHP-OTHER"), direct, environment=environment, **kwargs)
    np.testing.assert_array_equal(first.hours, other_shipment.hours)
    assert set(first.hours) == {100.0, 172.0}
    certain = simulate(shipment, transfer, environment=Environment(regional_shock_probability=1), **kwargs)
    np.testing.assert_array_equal(certain.hours, np.full(1_000, 172.0))


def test_worse_environment_increases_paired_hours_and_loss() -> None:
    route = Route(Leg(Mode.SEA, 1_000, 100, 0.3, 0.4, 0.8))
    shipment = Shipment("SHP-STRESS", "Rotterdam", "Shanghai", Priority.BALANCED, 150, 100_000, (route,))
    kwargs = dict(scenarios=2_000, seed=7, stream=Stream.REALITY)
    nominal = simulate(shipment, route, **kwargs)
    worse = simulate(shipment, route, environment=Environment(1.5, 1.5, 2.0, 0.1), **kwargs)
    assert np.all(worse.hours >= nominal.hours)
    assert np.all(worse.loss >= nominal.loss)
    assert worse.hours.mean() > nominal.hours.mean()
    assert worse.loss.mean() > nominal.loss.mean()
    # The nominal planner does not peek at the stressed held-out environment.
    report = evaluate((shipment,), environment=Environment(1.5, 1.5, 2.0, 0.1), scenarios=32, realizations=64, seed=7)
    assert report.rows[0].recommendation == recommend(shipment, scenarios=32, seed=7)
    assert report.environment != NOMINAL


def test_wilson_interval_does_not_turn_zero_misses_into_certainty() -> None:
    low, high = wilson_interval(100, 100)
    assert 0.96 < low < 1
    assert high == pytest.approx(1)
    assert wilson_interval(0, 100)[1] > 0
    assert wilson_interval(1_000, 1_000)[0] > low
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


def test_sampling_audit_is_reproducible_and_uses_independent_planning_seeds() -> None:
    result = audit(_priced(), runs=4, scenarios=32, realizations=64, seed=7)
    assert result == audit(_priced(), runs=4, scenarios=32, realizations=64, seed=7)
    assert result.reference_pick == "B"
    assert result.sampling.seeds == (8, 9, 10, 11)
    assert result.sampling.picks == {"B": 4}
    assert result.sampling.reference_agreement == 1
    assert result.sampling.median_score_gap == 400
    assert len(result.stresses) == 5
    assert result.stresses[0].mean_cost == 11_600
    assert result.stresses[0].risk_regret == 0
    assert result.stresses[-1].on_time <= result.stresses[0].on_time


def test_audit_does_not_treat_an_infeasible_fallback_as_a_recommendation() -> None:
    result = audit(replace(_priced(), deadline=10), runs=2, scenarios=16, realizations=32)
    assert result.reference_pick is None
    assert result.sampling.reference_agreement is None
    assert result.stresses == ()


def test_risk_objective_can_be_optimal_while_mean_only_regret_is_positive() -> None:
    shipment = Shipment(
        "SHP-OBJECTIVE", "Rotterdam", "Shanghai", Priority.RISK_AVERSE, 400, 100_000,
        (
            Route(Leg(Mode.SEA, 10_000, 100, 0, 0, 1)),
            Route(Leg(Mode.AIR, 12_000, 150, 0, 0, 0)),
        ),
    )
    report = evaluate((shipment,), scenarios=2_000, realizations=10_000, seed=0)
    assert report.rows[0].realized[Policy.RECOMMENDED].pick == "B"
    assert report.feasible_stats[Policy.RECOMMENDED].mean_regret > 1_000
    assert report.feasible_stats[Policy.RECOMMENDED].mean_risk_regret == 0


def test_independent_sampling_detects_a_noise_sensitive_choice() -> None:
    shipment = Shipment(
        "SHP-TIE", "Rotterdam", "Shanghai", Priority.BALANCED, 1_000, 100_000,
        tuple(Route(Leg(mode, 1_000, 100, 0, 0, 1)) for mode in (Mode.SEA, Mode.AIR)),
    )
    result = audit(shipment, scenarios=50, realizations=100, runs=20, seed=7)
    assert set(result.sampling.picks) == {"A", "B"}
    assert result.sampling.reference_agreement < 0.9
    assert all(case.risk_regret >= 0 for case in result.stresses)


@pytest.mark.parametrize("environment", [
    {"delay_length_scale": -1}, {"disruption_scale": float("nan")},
    {"regional_shock_probability": 2}, {"delay_probability_scale": True},
])
def test_environment_rejects_invalid_assumptions(environment) -> None:
    with pytest.raises(ValueError):
        Environment(**environment)
