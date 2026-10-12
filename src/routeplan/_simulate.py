"""Delay physics. This module does not know prices, so a new price reuses the same outcomes."""

from __future__ import annotations

import zlib
import math
from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from routeplan.model import Mode, Route, Shipment
from routeplan._network import regions

FloatArray = NDArray[np.float64]

BASE_DELAY_SHARE = 0.15
CONGESTION_DELAY_SHARE = 0.60
DISRUPTION_RATE = 0.08
DISRUPTION_HOLD = 96.0
LOSS_GIVEN_DISRUPTION = 0.25
LOSS_SHARE = 0.30


class Stream(Enum):
    PLAN = 0
    REALITY = 1


@dataclass(frozen=True, slots=True)
class Environment:
    """Explicit model-error assumptions. Defaults preserve the nominal simulator."""

    delay_probability_scale: float = 1.0
    delay_length_scale: float = 1.0
    disruption_scale: float = 1.0
    regional_shock_probability: float = 0.0
    regional_shock_hours: float = 72.0

    def __post_init__(self) -> None:
        for name, upper in (
            ("delay_probability_scale", 10), ("delay_length_scale", 10),
            ("disruption_scale", 10), ("regional_shock_probability", 1),
            ("regional_shock_hours", 1e7),
        ):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= upper):
                raise ValueError(f"{name} must be a finite number from 0 to {upper:g}")


NOMINAL = Environment()


@dataclass(frozen=True, slots=True, eq=False)
class Outcomes:
    hours: FloatArray
    loss: FloatArray


def simulate(
    shipment: Shipment,
    route: Route,
    *,
    scenarios: int,
    seed: int,
    stream: Stream,
    environment: Environment = NOMINAL,
) -> Outcomes:
    """Draw each leg from a stream keyed by the shipment and the hop, not by route order."""
    if isinstance(scenarios, bool) or not isinstance(scenarios, int) or scenarios < 1:
        raise ValueError("scenarios must be at least 1")
    stops = (shipment.origin, *route.hubs, shipment.destination)
    hours = np.full(scenarios, route.hours, dtype=np.float64)
    intact = np.ones(scenarios, dtype=np.float64)
    hops = zip(stops, stops[1:], strict=False)
    touched_regions: set[str] = set()
    for (start, end), leg in zip(hops, route.legs, strict=True):
        rng = np.random.default_rng(
            np.random.SeedSequence(
                (seed, stream.value, _key(shipment.id), _key(start, end, leg.mode.value))
            )
        )
        u_late, u_length, u_disrupt, u_damage = rng.random((4, scenarios))
        mean_delay = (
            leg.hours * (BASE_DELAY_SHARE + CONGESTION_DELAY_SHARE * leg.congestion)
            * environment.delay_length_scale
        )
        delayed = u_late < min(1.0, leg.delay_probability * environment.delay_probability_scale)
        hours = hours + np.where(delayed, -mean_delay * np.log1p(-u_length), 0.0)
        disrupted = u_disrupt < min(1.0, DISRUPTION_RATE * leg.geopolitical_risk * environment.disruption_scale)
        hours = hours + np.where(disrupted, DISRUPTION_HOLD, 0.0)
        damaged = disrupted & (u_damage < LOSS_GIVEN_DISRUPTION)
        intact = intact * np.where(damaged, 1.0 - LOSS_SHARE, 1.0)
        if environment.regional_shock_probability:
            touched_regions.update(regions(start, end, sea=leg.mode is Mode.SEA))
    # One hold per affected region, not once for every leg in that region.
    # The key excludes shipment/route IDs: a scenario represents the same regional
    # event for all routes and shipments. Local leg streams remain unchanged.
    for region in sorted(touched_regions):
        rng = np.random.default_rng(np.random.SeedSequence((seed, stream.value, _key("region", region))))
        shocked = rng.random(scenarios) < environment.regional_shock_probability
        hours = hours + np.where(shocked, environment.regional_shock_hours, 0.0)
    loss = shipment.cargo_value * (1.0 - intact)
    hours.setflags(write=False)
    loss.setflags(write=False)
    return Outcomes(hours, loss)


def _key(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    return zlib.crc32(text.encode()) & 0xFFFFFFFF
