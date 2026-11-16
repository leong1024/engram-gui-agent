import sqlite3
from collections.abc import Collection, Iterable

from artemis.app_memory import graph_queries as queries
from artemis.app_memory import ids
from artemis.app_memory import queries as map_queries
from artemis.app_memory.documents import OUTSIDE_TITLE
from artemis.app_memory.map_graph import GraphEdge, MapGraph, StateCard
from artemis.app_memory.models import EdgeId, MapId, StateId
from artemis.app_memory.rows import (
    card_from_row,
    edge_from_row,
    known_from_rows,
    map_key,
    tally_from_row,
)


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
        key = map_key(map_id)
        outside = ids.outside_state_id(map_id)
        states = {outside: _outside_card(outside)}
        states |= _by_id(
            card_from_row(row) for row in self._conn.execute(queries.SELECT_MAP_CARDS, key)
        )
        known = known_from_rows(self._conn.execute(map_queries.SELECT_STATES, key))
        edges = [edge_from_row(row) for row in self._conn.execute(queries.SELECT_MAP_EDGES, key)]
        tallies = [
            tally_from_row(row) for row in self._conn.execute(queries.SELECT_MAP_TALLIES, key)
        ]
        return MapGraph(map_id, outside, states, tuple(known), tuple(edges), tuple(tallies))


def _by_id(cards: Iterable[StateCard]) -> dict[StateId, StateCard]:
    return {card.state_id: card for card in cards}


def _outside_card(state_id: StateId) -> StateCard:
    return StateCard(state_id, OUTSIDE_TITLE, "", (), None, (), False, True, 0)
