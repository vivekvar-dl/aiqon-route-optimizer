"""Domain types. A priority is its price list. A result is either a pick or a miss."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, StrEnum, unique
from typing import assert_never


class Mode(StrEnum):
    SEA = "sea"
    RAIL = "rail"
    ROAD = "road"
    AIR = "air"


def _check_range(name: str, value: float, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number from {lo:g} to {hi:g}")
    number = float(value)
    if not lo <= number <= hi:
        raise ValueError(f"{name} must be a number from {lo:g} to {hi:g}")
    return number


@dataclass(frozen=True, slots=True)
class Leg:
    """One movement. Endpoints live on the route, so a leg cannot disagree with its neighbors."""

    mode: Mode
    cost: float
    hours: float
    delay_probability: float
    congestion: float
    geopolitical_risk: float

    def __post_init__(self) -> None:
        if not isinstance(self.mode, Mode):
            raise ValueError("mode must be sea, rail, road, or air")
        object.__setattr__(self, "cost", _check_range("cost", self.cost, 0, 1e12))
        object.__setattr__(self, "hours", _check_range("hours", self.hours, 0, 1e7))
        object.__setattr__(
            self, "delay_probability", _check_range("delay_probability", self.delay_probability, 0, 1)
        )
        object.__setattr__(self, "congestion", _check_range("congestion", self.congestion, 0, 1))
        object.__setattr__(
            self, "geopolitical_risk", _check_range("geopolitical_risk", self.geopolitical_risk, 0, 1)
        )


@dataclass(frozen=True, slots=True)
class Transfer:
    at: str
    leg: Leg

    def __post_init__(self) -> None:
        if not isinstance(self.at, str) or not self.at.strip():
            raise ValueError("hub name must be a non-empty string")
        if not isinstance(self.leg, Leg):
            raise ValueError("transfer leg must be a Leg")


@dataclass(frozen=True, slots=True)
class Route:
    """First leg leaves the origin. Each onward transfer names the hub it departs."""

    first: Leg
    onward: tuple[Transfer, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.first, Leg):
            raise ValueError("route must start with a Leg")
        object.__setattr__(self, "onward", tuple(self.onward))

    @property
    def legs(self) -> tuple[Leg, ...]:
        return (self.first, *(transfer.leg for transfer in self.onward))

    @property
    def hubs(self) -> tuple[str, ...]:
        return tuple(transfer.at for transfer in self.onward)

    @property
    def cost(self) -> float:
        return sum(leg.cost for leg in self.legs)

    @property
    def hours(self) -> float:
        return sum(leg.hours for leg in self.legs)


class Axis(StrEnum):
    """One price in Weights. Values are the field names."""

    HOLDING = "holding_per_day"
    LATENESS = "lateness_per_day"
    TAIL = "tail_weight"


@dataclass(frozen=True, slots=True)
class Weights:
    """Prices in shares of cargo value per day. The tail weight blends mean and CVaR."""

    holding_per_day: float
    lateness_per_day: float
    tail_weight: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "holding_per_day", _check_range("holding_per_day", self.holding_per_day, 0, 10)
        )
        object.__setattr__(
            self, "lateness_per_day", _check_range("lateness_per_day", self.lateness_per_day, 0, 10)
        )
        object.__setattr__(self, "tail_weight", _check_range("tail_weight", self.tail_weight, 0, 1))

    def scaled(self, axis: Axis, factor: float) -> Weights:
        if isinstance(factor, bool) or not isinstance(factor, (int, float)) or factor < 0:
            raise ValueError("factor must be a non-negative number")
        match axis:
            case Axis.HOLDING:
                return replace(self, holding_per_day=min(10.0, self.holding_per_day * factor))
            case Axis.LATENESS:
                return replace(self, lateness_per_day=min(10.0, self.lateness_per_day * factor))
            case Axis.TAIL:
                return replace(self, tail_weight=min(1.0, self.tail_weight * factor))
            case _:
                assert_never(axis)


@unique
class Priority(Enum):
    """The only profile table. Each priority is the prices it uses."""

    COST_FIRST = Weights(holding_per_day=0.0003, lateness_per_day=0.002, tail_weight=0.1)
    BALANCED = Weights(holding_per_day=0.001, lateness_per_day=0.01, tail_weight=0.3)
    TIME_CRITICAL = Weights(holding_per_day=0.003, lateness_per_day=0.05, tail_weight=0.3)
    RISK_AVERSE = Weights(holding_per_day=0.001, lateness_per_day=0.02, tail_weight=0.9)

    @property
    def weights(self) -> Weights:
        value = self.value
        assert isinstance(value, Weights)
        return value

    @property
    def slug(self) -> str:
        return self.name.lower().replace("_", "-")

    @classmethod
    def from_slug(cls, slug: str) -> Priority:
        for priority in cls:
            if priority.slug == slug:
                return priority
        known = ", ".join(priority.slug for priority in cls)
        raise ValueError(f"unknown priority {slug!r}. Known priorities: {known}")


@dataclass(frozen=True, slots=True)
class Shipment:
    id: str
    origin: str
    destination: str
    priority: Priority
    deadline: float
    cargo_value: float
    routes: tuple[Route, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("shipment id must be a non-empty string")
        if not isinstance(self.origin, str) or not self.origin.strip():
            raise ValueError("origin must be a non-empty string")
        if not isinstance(self.destination, str) or not self.destination.strip():
            raise ValueError("destination must be a non-empty string")
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        if not isinstance(self.priority, Priority):
            raise ValueError("priority must be a Priority")
        object.__setattr__(self, "deadline", _check_range("deadline", self.deadline, 0, 1e7))
        object.__setattr__(self, "cargo_value", _check_range("cargo_value", self.cargo_value, 0, 1e12))
        routes = tuple(self.routes)
        if not routes:
            raise ValueError("a shipment needs at least one route")
        if len(routes) > 26:
            raise ValueError("a shipment can have at most 26 routes")
        object.__setattr__(self, "routes", routes)

    def labeled(self) -> tuple[tuple[str, Route], ...]:
        return tuple((chr(ord("A") + index), route) for index, route in enumerate(self.routes))

    def route(self, label: str) -> Route:
        for current, route in self.labeled():
            if current == label:
                return route
        raise KeyError(label)


@dataclass(frozen=True, slots=True)
class Criteria:
    """Freight plus expected loss, expected hours, and the chance of missing the deadline."""

    cost: float
    hours: float
    late: float
    on_time_interval95: tuple[float, float] = (0.0, 1.0)
    p90_hours: float = 0.0
    expected_late_hours: float = 0.0
    samples: int = 0


@dataclass(frozen=True, slots=True)
class Breakdown:
    freight: float
    expected_loss: float
    holding: float
    lateness: float
    tail: float

    @property
    def total(self) -> float:
        return self.freight + self.expected_loss + self.holding + self.lateness + self.tail


@dataclass(frozen=True, slots=True)
class Option:
    label: str
    route: Route
    criteria: Criteria
    breakdown: Breakdown


@dataclass(frozen=True, slots=True)
class Infeasible:
    label: str
    route: Route
    criteria: Criteria
    shortfall: float


@dataclass(frozen=True, slots=True)
class Dominated:
    label: str
    route: Route
    criteria: Criteria
    by: str
    breakdown: Breakdown


@dataclass(frozen=True, slots=True)
class Probe:
    axis: Axis
    factor: float
    switches_to: str | None


@dataclass(frozen=True, slots=True)
class Sensitivity:
    probes: tuple[Probe, ...]
    by_priority: dict[Priority, str]

    @property
    def stability(self) -> float:
        if not self.probes:
            return 1.0
        held = sum(probe.switches_to is None for probe in self.probes)
        return held / len(self.probes)


@dataclass(frozen=True, slots=True)
class Explanation:
    headline: str
    details: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Chosen:
    shipment_id: str
    weights: Weights
    pick: Option
    alternatives: tuple[Option, ...]
    rejected: tuple[Dominated | Infeasible, ...]
    sensitivity: Sensitivity
    explanation: Explanation


@dataclass(frozen=True, slots=True)
class NoFeasibleRoute:
    shipment_id: str
    weights: Weights
    closest: Infeasible
    others: tuple[Infeasible, ...]
    explanation: Explanation


class DatasetError(ValueError):
    def __init__(self, problems: tuple[str, ...]) -> None:
        self.problems = problems
        joined = "\n".join(problems)
        super().__init__(joined if joined else "invalid dataset")
