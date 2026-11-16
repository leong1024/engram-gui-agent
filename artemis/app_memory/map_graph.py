from collections.abc import Mapping
from dataclasses import dataclass

from artemis.app_memory.models import (
    ActionSignature,
    CanonicalAction,
    EdgeId,
    KnownState,
    MapId,
    ObservationStatus,
    StateId,
)


@dataclass(frozen=True, slots=True)
class StateCard:
    """What retrieval and hints show of a state: its description and its screen signature."""

    state_id: StateId
    title: str
    purpose: str
    affordances: tuple[str, ...]
    activity: str | None
    static_tokens: tuple[str, ...]
    is_opaque: bool
    is_virtual: bool
    visits: int


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_id: EdgeId
    src: StateId
    dst: StateId
    signature: ActionSignature
    actions: tuple[CanonicalAction, ...]
    description: str | None
    last_seen_at: float


@dataclass(frozen=True, slots=True)
class Tally:
    """Observations sharing a source, an action and an outcome. `edge_id` is None for an
    action that left the screen unchanged."""

    src: StateId
    signature: ActionSignature
    edge_id: EdgeId | None
    status: ObservationStatus
    count: int


@dataclass(frozen=True, slots=True)
class MapGraph:
    """One map as routing reads it, loaded once per resolved target."""

    map_id: MapId
    outside: StateId
    states: Mapping[StateId, StateCard]
    known: tuple[KnownState, ...]
    edges: tuple[GraphEdge, ...]
    tallies: tuple[Tally, ...]
