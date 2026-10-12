"""Illustrative maritime corridors. Waypoints avoid straight-line ocean/land shortcuts.

These are coarse navigation distances, not published carrier services or navigational charts.
City nodes represent colocated sea/air gateways; handling is included in leg dwell time.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Port:
    name: str
    lat: float
    lon: float
    region: str
    congestion: float
    risk: float


PORTS = (
    Port("Rotterdam", 51.95, 4.14, "europe", 0.45, 0.05),
    Port("Hamburg", 53.55, 9.99, "europe", 0.40, 0.05),
    Port("Istanbul", 41.01, 28.98, "europe", 0.55, 0.40),
    Port("Dubai", 25.20, 55.27, "gulf", 0.50, 0.45),
    Port("Colombo", 6.93, 79.85, "indian-ocean", 0.55, 0.30),
    Port("Singapore", 1.29, 103.85, "indian-ocean", 0.70, 0.15),
    Port("Shenzhen", 22.54, 114.06, "east-asia", 0.60, 0.25),
    Port("Shanghai", 31.23, 121.47, "east-asia", 0.75, 0.20),
    Port("Busan", 35.10, 129.04, "east-asia", 0.40, 0.20),
    Port("Los Angeles", 33.74, -118.27, "americas", 0.65, 0.10),
    Port("New York", 40.68, -74.04, "americas", 0.50, 0.08),
    Port("Santos", -23.96, -46.33, "americas", 0.45, 0.20),
)
GATEWAYS = (
    Port("Algeciras", 36.13, -5.45, "europe", 0.35, 0.10),
    Port("Port Said", 31.26, 32.30, "mediterranean", 0.55, 0.35),
    Port("Salalah", 16.94, 54.0, "gulf", 0.30, 0.20),
    Port("Hong Kong", 22.30, 114.17, "east-asia", 0.50, 0.15),
    Port("Honolulu", 21.30, -157.85, "americas", 0.30, 0.05),
    Port("Cape Town", -33.90, 18.40, "southern-africa", 0.35, 0.15),
)
BY_NAME = {port.name: port for port in (*PORTS, *GATEWAYS)}

# Intermediate coordinates describe sailing corridors, not additional cargo transfers.
CORRIDORS = (
    ("Rotterdam", "Hamburg", ((54.0, 4.0), (54.0, 8.0))),
    ("Rotterdam", "Algeciras", ((51.5, 2.0), (50.0, -4.0), (44.0, -10.0), (37.0, -10.0))),
    ("Algeciras", "Istanbul", ((35.9, -5.6), (37.0, 5.0), (36.0, 14.0), (35.0, 21.0), (38.0, 26.0))),
    ("Istanbul", "Port Said", ((38.0, 26.0), (35.0, 27.0))),
    ("Port Said", "Salalah", ((29.90, 32.55), (20.0, 38.0), (12.6, 43.3), (13.0, 50.0))),
    ("Salalah", "Dubai", ((15.0, 58.0), (26.6, 56.2))),
    ("Salalah", "Colombo", ((6.0, 75.0),)),
    ("Colombo", "Singapore", ((3.0, 80.0), (3.0, 95.0), (2.0, 101.0))),
    ("Singapore", "Hong Kong", ((2.0, 105.0), (12.0, 112.0))),
    ("Hong Kong", "Shenzhen", ()),
    ("Shenzhen", "Shanghai", ((23.0, 117.0), (28.0, 124.0))),
    ("Shanghai", "Busan", ((32.0, 125.0),)),
    ("Busan", "Honolulu", ((33.0, 132.0), (34.0, 145.0), (35.0, 170.0))),
    ("Honolulu", "Los Angeles", ((25.0, -140.0),)),
    ("Algeciras", "New York", ((35.0, -15.0), (35.0, -50.0), (39.0, -70.0))),
    ("New York", "Los Angeles", (
        (35.0, -72.0), (25.0, -72.0), (12.0, -78.0),
        (9.35, -79.9), (8.95, -79.57), (8.0, -85.0), (15.0, -100.0),
    )),
    ("New York", "Santos", ((20.0, -60.0), (5.0, -45.0), (-10.0, -33.0), (-23.0, -40.0))),
    ("Algeciras", "Santos", ((20.0, -25.0), (-10.0, -33.0), (-23.0, -40.0))),
    ("Colombo", "Cape Town", ((0.0, 75.0), (-35.0, 55.0), (-36.0, 20.0))),
    ("Cape Town", "Santos", ((-36.0, 10.0), (-20.0, -20.0))),
)


def great_circle(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lat2 = math.radians(start[0]), math.radians(end[0])
    dlat, dlon = lat2 - lat1, math.radians(end[1] - start[1])
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, max(0.0, arc))))


def air_km(start: Port, end: Port) -> float:
    return great_circle((start.lat, start.lon), (end.lat, end.lon))


@lru_cache(maxsize=None)
def sea_path(start: str, end: str) -> tuple[float, tuple[str, ...]]:
    """Shortest sailing distance through the explicit, bidirectional corridor graph."""
    if start not in BY_NAME or end not in BY_NAME:
        raise ValueError("unknown maritime gateway")
    graph: dict[str, list[tuple[str, float]]] = {name: [] for name in BY_NAME}
    for first, last, waypoints in CORRIDORS:
        p, q = BY_NAME[first], BY_NAME[last]
        points = ((p.lat, p.lon), *waypoints, (q.lat, q.lon))
        distance = 1.05 * sum(great_circle(a, b) for a, b in zip(points, points[1:]))
        graph[first].append((last, distance))
        graph[last].append((first, distance))
    queue = [(0.0, (start,))]
    visited: set[str] = set()
    while queue:
        distance, path = heapq.heappop(queue)
        node = path[-1]
        if node in visited:
            continue
        visited.add(node)
        if node == end:
            return distance, path
        for neighbor, length in graph[node]:
            if neighbor not in visited:
                heapq.heappush(queue, (distance + length, (*path, neighbor)))
    raise ValueError(f"no maritime corridor from {start} to {end}")


def regions(start: str, end: str, *, sea: bool) -> tuple[str, ...]:
    nodes = sea_path(start, end)[1] if sea and start in BY_NAME and end in BY_NAME else (start, end)
    return tuple(sorted({BY_NAME[node].region if node in BY_NAME else f"port:{node}" for node in nodes}))
