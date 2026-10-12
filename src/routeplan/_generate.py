"""Seeded catalogs. Lane numbers come from distance and port risk, not from an independent draw."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from routeplan._network import BY_NAME, PORTS as _PORTS, Port as _Port, air_km, sea_path
from routeplan.model import Leg, Mode, Priority, Route, Shipment, Transfer

DEFAULT_COUNT = 30


@dataclass(frozen=True, slots=True)
class _Spec:
    speed_kmh: float
    dollars_per_km: float
    base_dollars: float
    dwell_hours: float
    delay_base: float
    delay_slope: float
    geo_scale: float


_SPECS: dict[Mode, _Spec] = {
    Mode.SEA: _Spec(32, 0.045, 350, 16, 0.18, 0.40, 1.0),
    Mode.AIR: _Spec(780, 0.55, 900, 5, 0.05, 0.10, 0.35),
}


def generate(seed: int, count: int = DEFAULT_COUNT) -> tuple[Shipment, ...]:
    """Build `count` shipments. The same seed and count return equal shipments."""
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an int")
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 50:
        raise ValueError("count must be an int from 1 to 50")
    lanes: dict[tuple[str, str, Mode], Leg] = {}
    return tuple(_shipment(seed, index, lanes) for index in range(count))


def _shipment(
    seed: int,
    index: int,
    lanes: dict[tuple[str, str, Mode], Leg],
) -> Shipment:
    rng = np.random.Generator(np.random.PCG64(seed * 1_000_003 + index))
    origin, destination = _pair(rng)
    others = [port for port in _PORTS if port.name not in {origin.name, destination.name}]
    sea_distance, navigation = sea_path(origin.name, destination.name)
    # Each cross-region lane has an actual maritime gateway on its corridor.
    # Transfer there, rather than visiting the destination and sailing back out.
    sea_hub = BY_NAME[min(navigation[1:-1], key=lambda name: (
        abs(sea_path(origin.name, name)[0] - sea_distance / 2), name,
    ))]
    air_ranked = sorted(others, key=lambda port: (_detour(origin, port, destination), port.name))
    outward = [port for port in others if destination.name not in sea_path(origin.name, port.name)[1]]
    inward = [port for port in others if origin.name not in sea_path(port.name, destination.name)[1]]
    mixed_out = min(outward, key=lambda port: (
        abs(sea_path(origin.name, port.name)[0] - sea_distance / 2)
        + 0.1 * air_km(port, destination), port.name,
    ))
    mixed_in = min(inward, key=lambda port: (
        abs(sea_path(port.name, destination.name)[0] - sea_distance / 2)
        + 0.1 * air_km(origin, port), port.name,
    ))
    routes = [
        _path((origin, sea_hub, destination), (Mode.SEA, Mode.SEA), lanes),
        _path((origin, air_ranked[0], destination), (Mode.AIR, Mode.AIR), lanes),
        _path((origin, mixed_out, destination), (Mode.SEA, Mode.AIR), lanes),
    ]
    route_count = 3 + (index % 3)
    if route_count >= 4:
        routes.append(_path((origin, mixed_in, destination), (Mode.AIR, Mode.SEA), lanes))
    if route_count == 5:
        routes.append(_path((origin, air_ranked[1], destination), (Mode.AIR, Mode.AIR), lanes))
    fastest = min(route.hours for route in routes)
    ordered = sorted(route.hours for route in routes)
    median = ordered[len(ordered) // 2]
    if index % 10 == 9:
        deadline = round(fastest * 0.75)
    else:
        deadline = round(median * (1.2, 1.5, 2.1)[index % 3])
    cargo = round(math.exp(float(rng.uniform(math.log(80_000), math.log(1_500_000)))))
    priority = list(Priority)[index % len(Priority)]
    return Shipment(
        f"SHP-{index + 1:03d}",
        origin.name,
        destination.name,
        priority,
        deadline,
        float(cargo),
        tuple(routes),
    )


def _pair(rng: np.random.Generator) -> tuple[_Port, _Port]:
    regions = sorted({port.region for port in _PORTS})
    origin_region = regions[int(rng.integers(0, len(regions)))]
    dest_regions = [region for region in regions if region != origin_region]
    dest_region = dest_regions[int(rng.integers(0, len(dest_regions)))]
    origin = _choose(rng, [port for port in _PORTS if port.region == origin_region])
    destination = _choose(rng, [port for port in _PORTS if port.region == dest_region])
    return origin, destination


def _choose(rng: np.random.Generator, ports: list[_Port]) -> _Port:
    return ports[int(rng.integers(0, len(ports)))]


def _detour(origin: _Port, hub: _Port, destination: _Port) -> float:
    return air_km(origin, hub) + air_km(hub, destination)


def _path(
    stops: tuple[_Port, ...], modes: tuple[Mode, ...], lanes: dict[tuple[str, str, Mode], Leg]
) -> Route:
    legs = [
        _lane(start, end, mode, lanes)
        for start, end, mode in zip(stops, stops[1:], modes, strict=False)
    ]
    hubs = stops[1:-1]
    onward = tuple(Transfer(hub.name, leg) for hub, leg in zip(hubs, legs[1:], strict=False))
    return Route(legs[0], onward)


def _lane(start: _Port, end: _Port, mode: Mode, lanes: dict[tuple[str, str, Mode], Leg]) -> Leg:
    key = (start.name, end.name, mode)
    cached = lanes.get(key)
    if cached is not None:
        return cached
    spec = _SPECS[mode]
    distance = sea_path(start.name, end.name)[0] if mode is Mode.SEA else air_km(start, end)
    congestion = min(1.0, (start.congestion + end.congestion) / 2)
    delay = min(0.9, spec.delay_base + spec.delay_slope * congestion)
    geo = min(1.0, max(start.risk, end.risk) * spec.geo_scale)
    leg = Leg(
        mode,
        round(spec.base_dollars + spec.dollars_per_km * distance, 2),
        round(distance / spec.speed_kmh + spec.dwell_hours, 2),
        round(delay, 4),
        round(congestion, 4),
        round(geo, 4),
    )
    lanes[key] = leg
    return leg
