import math
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from artemis.app_memory.map_graph import StateCard
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import CanonicalAction, MapId, StateId


class RouteKind(StrEnum):
    FROM_STATE = "from_state"
    FROM_OUTSIDE = "from_outside"
    FROM_LAUNCH = "from_launch"
    NO_PATH = "no_path"
    ARRIVED = "arrived"


class HintNote(StrEnum):
    REROUTED = "rerouted"
    UNRECOGNISED = "unrecognised"


@dataclass(frozen=True, slots=True)
class AtState:
    """A known screen of the target's map that is not the target."""

    state_id: StateId
    kind: ClassVar[RouteKind] = RouteKind.FROM_STATE


@dataclass(frozen=True, slots=True)
class InOtherApp:
    """Another app's screen: routes start from the target map's `@outside`."""

    state_id: StateId
    kind: ClassVar[RouteKind] = RouteKind.FROM_OUTSIDE


@dataclass(frozen=True, slots=True)
class Unrecognised:
    """A screen of the target's app that the map does not know: routes start from launch."""

    state_id: StateId
    kind: ClassVar[RouteKind] = RouteKind.FROM_LAUNCH


@dataclass(frozen=True, slots=True)
class Arrived:
    state_id: StateId
    kind: ClassVar[RouteKind] = RouteKind.ARRIVED


Location = AtState | InOtherApp | Unrecognised | Arrived


@dataclass(frozen=True, slots=True)
class Hop:
    from_state: StateCard
    actions: tuple[CanonicalAction, ...]
    to_state: StateCard
    probability: float


@dataclass(frozen=True, slots=True)
class Route:
    milestone: Milestone
    kind: RouteKind
    map_id: MapId
    target: StateCard
    source: StateCard
    hops: tuple[Hop, ...] = ()
    borrowed: bool = False
    notes: tuple[HintNote, ...] = ()

    @property
    def milestone_key(self) -> str:
        return self.milestone.key

    @property
    def confidence(self) -> float:
        return math.prod(hop.probability for hop in self.hops)
