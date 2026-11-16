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
    """One map as routing reads it: loaded once per run, then kept current with `merged`."""

    map_id: MapId
    outside: StateId
    states: Mapping[StateId, StateCard]
    known: tuple[KnownState, ...]
    edges: tuple[GraphEdge, ...]
    tallies: tuple[Tally, ...]

    def merged(self, part: "MapGraph") -> "MapGraph":
        """This map with `part`'s rows in place of its own. `part` must hold every tally and
        edge of each source state it has a tally for, and the card of each state it changes.
        Rows keep the order a fresh load gives them, so the result equals that load."""
        sources = {tally.src for tally in part.tallies}
        known = _by_state(self.known) | _by_state(part.known)
        edges = {edge.edge_id: edge for edge in self.edges if edge.src not in sources}
        edges |= {edge.edge_id: edge for edge in part.edges}
        tallies = [tally for tally in self.tallies if tally.src not in sources]
        return MapGraph(
            self.map_id,
            self.outside,
            {**self.states, **part.states},
            tuple(known[state_id] for state_id in sorted(known)),
            tuple(edges[edge_id] for edge_id in sorted(edges)),
            tuple(sorted([*tallies, *part.tallies], key=_tally_order)),
        )


def _by_state(known: tuple[KnownState, ...]) -> dict[StateId, KnownState]:
    return {state.state_id: state for state in known}


def _tally_order(tally: Tally) -> tuple[str, str, bool, str, str]:
    """SQLite's `ORDER BY src, signature, edge_id, status`, which puts a NULL edge first."""
    edge = tally.edge_id
    return tally.src, tally.signature, edge is not None, edge or "", tally.status
