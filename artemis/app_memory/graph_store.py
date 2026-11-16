import sqlite3
from collections.abc import Collection, Iterable, Mapping
from typing import NamedTuple

from artemis.app_memory import graph_queries as queries
from artemis.app_memory import ids
from artemis.app_memory.documents import OUTSIDE_TITLE
from artemis.app_memory.map_graph import GraphEdge, MapGraph, StateCard
from artemis.app_memory.models import EdgeId, MapId, StateId
from artemis.app_memory.rows import card_from_row, edge_from_row, known_from_rows, tally_from_row


class SessionMark(NamedTuple):
    """How much of one map a session has observed. It changes whenever the session adds an
    observation there or settles its provisional ones, the only writes a session makes."""

    observations: int
    provisional: int


class GraphStore:
    """Read-only views of maps for retrieval and routing, on the map store's connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def maps(self) -> list[MapId]:
        return [
            MapId(package, version) for package, version in self._conn.execute(queries.SELECT_MAPS)
        ]

    def cards(self, state_ids: Collection[StateId]) -> dict[StateId, StateCard]:
        sql = queries.select_cards(f"s.state_id IN ({queries.placeholders(len(state_ids))})")
        return _by_id(card_from_row(row) for row in self._conn.execute(sql, tuple(state_ids)))

    def edges(self, edge_ids: Collection[EdgeId]) -> dict[EdgeId, GraphEdge]:
        sql = f"{queries.EDGE_COLUMNS} WHERE edge_id IN ({queries.placeholders(len(edge_ids))})"
        rows = self._conn.execute(sql, tuple(edge_ids))
        return {edge.edge_id: edge for edge in map(edge_from_row, rows)}

    def map_graph(self, map_id: MapId) -> MapGraph:
        outside = ids.outside_state_id(map_id)
        graph = self._read(map_id, queries.WHOLE_MAP, _params(map_id))
        states = {outside: _outside_card(outside)} | dict(graph.states)
        return MapGraph(map_id, outside, states, graph.known, graph.edges, graph.tallies)

    def session_slice(self, map_id: MapId, session_id: str) -> MapGraph:
        """Every row of the map's states that the session observed from: their observations,
        their outgoing edges, and the cards of both ends. See `MapGraph.merged`."""
        return self._read(map_id, queries.SESSION_SLICE, _params(map_id, session=session_id))

    def session_marks(self, session_id: str) -> dict[MapId, SessionMark]:
        rows = self._conn.execute(queries.SELECT_SESSION_MARKS, (session_id,))
        return {MapId(package, version): SessionMark(*counts) for package, version, *counts in rows}

    def _read(
        self, map_id: MapId, sql: queries.GraphQueries, params: Mapping[str, object]
    ) -> MapGraph:
        def rows(query: str) -> sqlite3.Cursor:
            return self._conn.execute(query, params)

        return MapGraph(
            map_id,
            ids.outside_state_id(map_id),
            _by_id(map(card_from_row, rows(sql.cards))),
            known_from_rows(rows(sql.known)),
            tuple(map(edge_from_row, rows(sql.edges))),
            tuple(map(tally_from_row, rows(sql.tallies))),
        )


def _params(map_id: MapId, **extra: object) -> dict[str, object]:
    return {"package": map_id.package, "version": map_id.version_code, **extra}


def _by_id(cards: Iterable[StateCard]) -> dict[StateId, StateCard]:
    return {card.state_id: card for card in cards}


def _outside_card(state_id: StateId) -> StateCard:
    return StateCard(state_id, OUTSIDE_TITLE, "", (), None, (), False, True, 0)
