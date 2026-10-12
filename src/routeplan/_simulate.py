"""Delay physics. This module does not know prices, so a new price reuses the same outcomes."""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from routeplan.model import Route, Shipment

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
) -> Outcomes:
    """Draw each leg from a stream keyed by the shipment and the hop, not by route order."""
    if scenarios < 1:
        raise ValueError("scenarios must be at least 1")
    stops = (shipment.origin, *route.hubs, shipment.destination)
    hours = np.full(scenarios, route.hours, dtype=np.float64)
    intact = np.ones(scenarios, dtype=np.float64)
    hops = zip(stops, stops[1:], strict=False)
    for (start, end), leg in zip(hops, route.legs, strict=True):
        rng = np.random.default_rng(
            np.random.SeedSequence(
                (seed, stream.value, _key(shipment.id), _key(start, end, leg.mode.value))
            )
        )
        u_late, u_length, u_disrupt, u_damage = rng.random((4, scenarios))
        mean_delay = leg.hours * (BASE_DELAY_SHARE + CONGESTION_DELAY_SHARE * leg.congestion)
        delayed = u_late < leg.delay_probability
        hours = hours + np.where(delayed, -mean_delay * np.log1p(-u_length), 0.0)
        disrupted = u_disrupt < DISRUPTION_RATE * leg.geopolitical_risk
        hours = hours + np.where(disrupted, DISRUPTION_HOLD, 0.0)
        damaged = disrupted & (u_damage < LOSS_GIVEN_DISRUPTION)
        intact = intact * np.where(damaged, 1.0 - LOSS_SHARE, 1.0)
    loss = shipment.cargo_value * (1.0 - intact)
    hours.setflags(write=False)
    loss.setflags(write=False)
    return Outcomes(hours, loss)


def _key(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    return zlib.crc32(text.encode()) & 0xFFFFFFFF
