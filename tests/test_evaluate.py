"""Evaluation replays picks on a stream the planner did not use."""

import pytest

from routeplan import Policy, Priority, Route, Shipment, evaluate

from test_decisions import _leg, _priced, _via


def test_zero_noise_shipment_matches_the_closed_form() -> None:
    report = evaluate((_priced(),), scenarios=32, realizations=16, seed=0)
    recommended = report.stats[Policy.RECOMMENDED]
    cheapest = report.stats[Policy.CHEAPEST]
    fastest = report.stats[Policy.FASTEST]
    oracle = report.stats[Policy.ORACLE]
    assert recommended.total_cost == 11_600
    assert recommended.mean_regret == 0
    assert recommended.on_time_rate == 1
    assert recommended.feasible_rate == 1
    assert recommended.pareto_rate == 1
    assert cheapest.total_cost == 12_000
    assert cheapest.mean_regret == 400
    assert cheapest.cost_ratio == 12_000 / 11_600
    assert fastest.total_cost == 11_600
    assert fastest.mean_regret == 0
    assert oracle.mean_regret == 0
    assert oracle.total_cost == 11_600
    assert report.infeasible == 0
    assert report.stability == 17 / 18


def test_cost_ratio_is_the_mean_of_per_shipment_ratios() -> None:
    slow = Shipment(
        "SHP-2",
        "Rotterdam",
        "Shanghai",
        Priority.TIME_CRITICAL,
        500,
        240_000,
        (
            Route(_leg(1_000, 400)),
            _via("Singapore", _leg(3_000, 30), _leg(2_000, 20)),
        ),
    )
    report = evaluate((_priced(), slow), scenarios=32, realizations=16, seed=0)
    ratios = [
        row.realized[Policy.CHEAPEST].cost / row.realized[Policy.RECOMMENDED].cost
        for row in report.rows
    ]
    cheapest = report.stats[Policy.CHEAPEST]
    recommended = report.stats[Policy.RECOMMENDED]
    assert cheapest.cost_ratio == sum(ratios) / len(ratios)
    assert abs(cheapest.cost_ratio - ((12_000 / 11_600) + 2) / 2) < 1e-9
    assert abs(cheapest.total_cost / recommended.total_cost - 25_000 / 18_100) < 1e-9
    assert cheapest.cost_ratio != cheapest.total_cost / recommended.total_cost


def test_evaluate_rejects_an_empty_catalog() -> None:
    with pytest.raises(ValueError, match="at least one"):
        evaluate(())
