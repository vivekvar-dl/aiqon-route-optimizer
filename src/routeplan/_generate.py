"""Seeded catalogs. Lane numbers come from distance and port risk, not from an independent draw."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from routeplan.model import Leg, Mode, Priority, Route, Shipment, Transfer

DEFAULT_COUNT = 30


@dataclass(frozen=True, slots=True)
class _Port:
    name: str
    lat: float
    lon: float
    region: str
    congestion: float
    risk: float


_PORTS: tuple[_Port, ...] = (
    _Port("Rotterdam", 51.95, 4.14, "europe", 0.45, 0.05),
    _Port("Hamburg", 53.55, 9.99, "europe", 0.40, 0.05),
    _Port("Istanbul", 41.01, 28.98, "europe", 0.55, 0.40),
    _Port("Dubai", 25.20, 55.27, "gulf", 0.50, 0.45),
    _Port("Colombo", 6.93, 79.85, "indian-ocean", 0.55, 0.30),
    _Port("Singapore", 1.29, 103.85, "indian-ocean", 0.70, 0.15),
    _Port("Shenzhen", 22.54, 114.06, "east-asia", 0.60, 0.25),
    _Port("Shanghai", 31.23, 121.47, "east-asia", 0.75, 0.20),
    _Port("Busan", 35.10, 129.04, "east-asia", 0.40, 0.20),
    _Port("Los Angeles", 33.74, -118.27, "americas", 0.65, 0.10),
    _Port("New York", 40.68, -74.04, "americas", 0.50, 0.08),
    _Port("Santos", -23.96, -46.33, "americas", 0.45, 0.20),
)


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
    Mode.RAIL: _Spec(75, 0.14, 250, 8, 0.10, 0.22, 0.60),
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
    nearest, second, farthest = _hubs(origin, destination, others)
    routes = [
        _path((origin, nearest, destination), Mode.SEA, lanes),
        _path((origin, nearest, destination), Mode.AIR, lanes),
        _path((origin, second, destination), Mode.RAIL, lanes),
    ]
    route_count = 3 + (index % 3)
    if route_count >= 4:
        routes.append(_path((origin, nearest, farthest, destination), Mode.SEA, lanes))
    if route_count == 5:
        routes.append(_path((origin, farthest, destination), Mode.AIR, lanes))
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


def _hubs(origin: _Port, destination: _Port, others: list[_Port]) -> tuple[_Port, _Port, _Port]:
    ranked = sorted(others, key=lambda port: (_detour(origin, port, destination), port.name))
    return ranked[0], ranked[1], ranked[-1]


def _detour(origin: _Port, hub: _Port, destination: _Port) -> float:
    return _km(origin, hub) + _km(hub, destination)


def _path(stops: tuple[_Port, ...], mode: Mode, lanes: dict[tuple[str, str, Mode], Leg]) -> Route:
    legs = [_lane(start, end, mode, lanes) for start, end in zip(stops, stops[1:], strict=False)]
    hubs = stops[1:-1]
    onward = tuple(Transfer(hub.name, leg) for hub, leg in zip(hubs, legs[1:], strict=False))
    return Route(legs[0], onward)


def _lane(start: _Port, end: _Port, mode: Mode, lanes: dict[tuple[str, str, Mode], Leg]) -> Leg:
    key = (start.name, end.name, mode)
    cached = lanes.get(key)
    if cached is not None:
        return cached
    spec = _SPECS[mode]
    distance = _km(start, end)
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


def _km(start: _Port, end: _Port) -> float:
    radius = 6371.0
    lat1, lat2 = math.radians(start.lat), math.radians(end.lat)
    dlat = lat2 - lat1
    dlon = math.radians(end.lon - start.lon)
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(arc))
