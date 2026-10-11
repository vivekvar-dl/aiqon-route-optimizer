"""JSON is the dataset boundary. Validation happens here and nowhere else."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from typing import cast

from routeplan.model import (
    DatasetError,
    Leg,
    Mode,
    Priority,
    Route,
    Shipment,
    Transfer,
)

_LEG_FIELDS = ("mode", "cost", "hours", "delay_probability", "congestion", "geopolitical_risk")


def parse_shipments(text: str) -> tuple[Shipment, ...]:
    """Turn a JSON array into shipments, reporting every bad field."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as err:
        raise DatasetError((f"invalid JSON: {err.msg}",)) from err
    if not isinstance(raw, list):
        raise DatasetError(("dataset must be a JSON array of shipments",))
    problems: list[str] = []
    shipments: list[Shipment] = []
    hops: dict[tuple[str, str, str], tuple[float, ...]] = {}
    seen_ids: set[str] = set()
    for index, item in enumerate(raw):
        shipment, item_problems = _shipment(item, f"[{index}]")
        problems.extend(item_problems)
        if shipment is None:
            continue
        if shipment.id in seen_ids:
            problems.append(f"[{index}].id: duplicate shipment id {shipment.id}")
        else:
            seen_ids.add(shipment.id)
        problems.extend(_hops(shipment, hops, f"[{index}]"))
        shipments.append(shipment)
    if problems:
        raise DatasetError(tuple(problems))
    if not shipments:
        raise DatasetError(("dataset is empty",))
    return tuple(shipments)


def to_json(value: object) -> str:
    """Serialize shipments, a recommendation, or a report."""
    return json.dumps(_encode(value), indent=2) + "\n"


def _shipment(item: object, path: str) -> tuple[Shipment | None, list[str]]:
    problems: list[str] = []
    if not isinstance(item, dict):
        return None, [f"{path}: expected an object"]
    data = cast(dict[str, object], item)
    origin = _text(data, "origin", path, problems)
    destination = _text(data, "destination", path, problems)
    shipment_id = _text(data, "id", path, problems)
    priority = _priority(data.get("priority"), f"{path}.priority", problems)
    deadline = _number(data, "deadline", path, problems)
    cargo = _number(data, "cargo_value", path, problems)
    routes_raw = data.get("routes")
    routes: list[Route] = []
    if not isinstance(routes_raw, list) or not routes_raw:
        problems.append(f"{path}.routes: expected a non-empty array")
    else:
        for index, route_raw in enumerate(routes_raw):
            route = _route(route_raw, f"{path}.routes[{index}]", problems)
            if route is not None:
                routes.append(route)
    if problems or None in (origin, destination, shipment_id, priority, deadline, cargo) or not routes:
        return None, problems
    try:
        shipment = Shipment(
            shipment_id,
            origin,
            destination,
            priority,
            deadline,
            cargo,
            tuple(routes),
        )
    except ValueError as err:
        problems.append(f"{path}: {err}")
        return None, problems
    return shipment, problems


def _route(item: object, path: str, problems: list[str]) -> Route | None:
    if not isinstance(item, dict):
        problems.append(f"{path}: expected an object")
        return None
    data = cast(dict[str, object], item)
    first = _leg(data.get("first"), f"{path}.first", problems)
    onward_raw = data.get("onward", [])
    transfers: list[Transfer] = []
    if not isinstance(onward_raw, list):
        problems.append(f"{path}.onward: expected an array")
    else:
        for index, hop in enumerate(onward_raw):
            transfer = _transfer(hop, f"{path}.onward[{index}]", problems)
            if transfer is not None:
                transfers.append(transfer)
    if first is None or len(transfers) != (len(onward_raw) if isinstance(onward_raw, list) else 0):
        return None
    return Route(first, tuple(transfers))


def _transfer(item: object, path: str, problems: list[str]) -> Transfer | None:
    if not isinstance(item, dict):
        problems.append(f"{path}: expected an object")
        return None
    data = cast(dict[str, object], item)
    hub = data.get("at")
    if not isinstance(hub, str) or not hub.strip():
        problems.append(f"{path}.at: expected a port name")
        hub_name = None
    else:
        hub_name = hub
    leg = _leg(data.get("leg"), f"{path}.leg", problems)
    if hub_name is None or leg is None:
        return None
    return Transfer(hub_name, leg)


def _leg(item: object, path: str, problems: list[str]) -> Leg | None:
    if not isinstance(item, dict):
        problems.append(f"{path}: expected an object")
        return None
    data = cast(dict[str, object], item)
    mode_raw = data.get("mode")
    try:
        mode = Mode(mode_raw)
    except ValueError:
        problems.append(f"{path}.mode: expected sea, rail, road, or air")
        mode = None
    numbers: dict[str, float] = {}
    missing_number = False
    for name in _LEG_FIELDS[1:]:
        value = _number(data, name, path, problems)
        if value is None:
            missing_number = True
        else:
            numbers[name] = value
    if missing_number:
        return None
    try:
        leg = Leg(mode if mode is not None else Mode.SEA, **numbers)
    except ValueError as err:
        message = str(err)
        field = message.split(" ", 1)[0]
        problems.append(f"{path}.{field}: {message}")
        return None
    if mode is None:
        return None
    return leg


def _hops(
    shipment: Shipment,
    seen: dict[tuple[str, str, str], tuple[float, ...]],
    path: str,
) -> list[str]:
    problems: list[str] = []
    for route_index, (_label, route) in enumerate(shipment.labeled()):
        stops = (shipment.origin, *route.hubs, shipment.destination)
        for start, end, leg in zip(stops, stops[1:], route.legs, strict=False):
            signature = (
                leg.cost,
                leg.hours,
                leg.delay_probability,
                leg.congestion,
                leg.geopolitical_risk,
            )
            key = (start, end, leg.mode.value)
            previous = seen.get(key)
            if previous is None:
                seen[key] = signature
                continue
            if previous != signature:
                problems.append(
                    f"{path}.routes[{route_index}]: hop {start} to {end} by {leg.mode.value} "
                    f"has different numbers than an earlier leg"
                )
    return problems


def _text(data: dict[str, object], name: str, path: str, problems: list[str]) -> str | None:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{path}.{name}: expected a non-empty string")
        return None
    return value


def _number(data: Mapping[str, object], name: str, path: str, problems: list[str]) -> float | None:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append(f"{path}.{name}: expected a number")
        return None
    return float(value)


def _priority(value: object, path: str, problems: list[str]) -> Priority | None:
    if not isinstance(value, str):
        problems.append(f"{path}: expected a priority name")
        return None
    try:
        return Priority.from_slug(value)
    except ValueError as err:
        problems.append(f"{path}: {err}")
        return None


def _encode(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        raw = asdict(value)
        if isinstance(value, Shipment):
            return _shipment_json(value)
        return {key: _encode(item) for key, item in raw.items()}
    if isinstance(value, Priority):
        return value.slug
    if isinstance(value, Mode):
        return value.value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_encode(item) for item in value]
    if isinstance(value, Mapping):
        return {str(_encode(key)): _encode(item) for key, item in value.items()}
    if isinstance(value, float):
        return round(value, 6) if not value.is_integer() else value
    return value


def _shipment_json(shipment: Shipment) -> dict[str, object]:
    return {
        "id": shipment.id,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "priority": shipment.priority.slug,
        "deadline": shipment.deadline,
        "cargo_value": shipment.cargo_value,
        "routes": [
            {
                "first": _leg_json(route.first),
                "onward": [
                    {"at": transfer.at, "leg": _leg_json(transfer.leg)} for transfer in route.onward
                ],
            }
            for route in shipment.routes
        ],
    }


def _leg_json(leg: Leg) -> dict[str, object]:
    return {
        "mode": leg.mode.value,
        "cost": leg.cost,
        "hours": leg.hours,
        "delay_probability": leg.delay_probability,
        "congestion": leg.congestion,
        "geopolitical_risk": leg.geopolitical_risk,
    }
