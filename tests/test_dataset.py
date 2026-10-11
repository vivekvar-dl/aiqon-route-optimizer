"""The synthetic catalog is seeded, and the same hop never carries two sets of numbers."""

import json

import pytest

from routeplan import DatasetError, Priority, generate, parse_shipments, to_json


def test_generate_is_deterministic_and_builds_the_tradeoff() -> None:
    first = generate(7, 30)
    second = generate(7, 30)
    assert first == second
    assert [shipment.id for shipment in first] == [f"SHP-{index:03d}" for index in range(1, 31)]
    assert {shipment.priority for shipment in first} == set(Priority)
    infeasible = 0
    for shipment in first:
        assert 3 <= len(shipment.routes) <= 5
        assert all(route.hubs for route in shipment.routes)
        costs = [route.cost for route in shipment.routes]
        hours = [route.hours for route in shipment.routes]
        cheap = min(range(len(costs)), key=lambda index: (costs[index], hours[index]))
        fast = min(range(len(hours)), key=lambda index: (hours[index], costs[index]))
        assert costs[cheap] < costs[fast]
        assert hours[fast] < hours[cheap]
        if all(route.hours > shipment.deadline for route in shipment.routes):
            infeasible += 1
    assert infeasible == 3
    assert parse_shipments(to_json(first)) == first


def test_parse_reports_every_problem() -> None:
    payload = [
        {
            "id": "SHP-1",
            "origin": "Rotterdam",
            "destination": "Shanghai",
            "priority": "balanced",
            "deadline": 100,
            "cargo_value": 1000,
            "routes": [
                {
                    "first": {
                        "mode": "sea",
                        "cost": 10,
                        "hours": 10,
                        "delay_probability": 1.4,
                        "congestion": 0,
                        "geopolitical_risk": 0,
                    },
                    "onward": [],
                },
                {
                    "first": {
                        "mode": "air",
                        "cost": 20,
                        "hours": 4,
                        "delay_probability": 0,
                        "congestion": 0,
                        "geopolitical_risk": 0,
                    },
                    "onward": [
                        {
                            "at": None,
                            "leg": {
                                "mode": "sea",
                                "cost": 5,
                                "hours": 5,
                                "delay_probability": 0,
                                "congestion": 0,
                                "geopolitical_risk": 0,
                            },
                        }
                    ],
                },
            ],
        }
    ]
    with pytest.raises(DatasetError) as caught:
        parse_shipments(json.dumps(payload))
    text = "\n".join(caught.value.problems)
    assert "[0].routes[0].first.delay_probability" in text
    assert "[0].routes[1].onward[0].at" in text
    assert len(caught.value.problems) == 2


def test_parse_rejects_a_hop_with_two_sets_of_numbers() -> None:
    payload = [
        {
            "id": "SHP-1",
            "origin": "Rotterdam",
            "destination": "Shanghai",
            "priority": "balanced",
            "deadline": 400,
            "cargo_value": 1000,
            "routes": [
                {
                    "first": _leg(100, 50),
                    "onward": [{"at": "Singapore", "leg": _leg(80, 40)}],
                },
                {
                    "first": _leg(100, 50),
                    "onward": [{"at": "Singapore", "leg": _leg(90, 40)}],
                },
            ],
        }
    ]
    with pytest.raises(DatasetError) as caught:
        parse_shipments(json.dumps(payload))
    assert "Singapore" in caught.value.problems[0]
    assert "different numbers" in caught.value.problems[0]
    assert "[0].routes[1]" in caught.value.problems[0]


def test_parse_rejects_a_duplicate_shipment_id() -> None:
    shipment = {
        "id": "SHP-1",
        "origin": "Rotterdam",
        "destination": "Shanghai",
        "priority": "balanced",
        "deadline": 100,
        "cargo_value": 1000,
        "routes": [{"first": _leg(10, 10), "onward": []}],
    }
    with pytest.raises(DatasetError) as caught:
        parse_shipments(json.dumps([shipment, shipment]))
    assert caught.value.problems == ("[1].id: duplicate shipment id SHP-1",)


def test_parse_reports_the_other_leg_fields_when_the_mode_is_invalid() -> None:
    payload = [
        {
            "id": "SHP-1",
            "origin": "Rotterdam",
            "destination": "Shanghai",
            "priority": "balanced",
            "deadline": 100,
            "cargo_value": 1000,
            "routes": [
                {
                    "first": {
                        "mode": "boat",
                        "cost": 10,
                        "hours": 10,
                        "delay_probability": 1.4,
                        "congestion": 0,
                        "geopolitical_risk": 0,
                    },
                    "onward": [],
                }
            ],
        }
    ]
    with pytest.raises(DatasetError) as caught:
        parse_shipments(json.dumps(payload))
    text = "\n".join(caught.value.problems)
    assert "[0].routes[0].first.mode" in text
    assert "[0].routes[0].first.delay_probability" in text


def _leg(cost: float, hours: float) -> dict[str, object]:
    return {
        "mode": "sea",
        "cost": cost,
        "hours": hours,
        "delay_probability": 0,
        "congestion": 0,
        "geopolitical_risk": 0,
    }
