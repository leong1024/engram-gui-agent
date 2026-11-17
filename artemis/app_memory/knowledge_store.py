import sqlite3
from dataclasses import dataclass

from artemis.app_memory import knowledge_queries as queries
from artemis.app_memory.map_graph import StateCard
from artemis.app_memory.models import MapId
from artemis.app_memory.rows import card_from_row


@dataclass(frozen=True, slots=True)
class MapCounts:
    """One map as app knowledge counts it. `states` counts every real state and `described`
    those with a ready description. `has_vectors` is for the model the query was given."""

    map_id: MapId
    version_name: str | None
    states: int
    described: int
    routes: int
    sessions: int
    last_seen_at: float
    has_vectors: bool


class KnowledgeStore:
    """Read-only aggregates of maps for app knowledge, on the map store's connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def maps(self, model_id: str | None) -> list[MapCounts]:
        rows = self._conn.execute(queries.SELECT_MAP_COUNTS, {"model_id": model_id})
        return [
            MapCounts(
                MapId(package, version),
                name,
                states,
                described,
                routes,
                sessions,
                seen,
                bool(vectored),
            )
            for package, version, name, states, described, routes, sessions, seen, vectored in rows
        ]

    def pages(self, map_id: MapId) -> list[StateCard]:
        """The map's described real states, each with its arrival visits."""
        rows = self._conn.execute(queries.SELECT_PAGES, _params(map_id))
        return [card_from_row(row) for row in rows]

    def completed_sessions(self, map_id: MapId, limit: int) -> list[str]:
        """Sessions that observed the map and finished `completed`, newest first."""
        rows = self._conn.execute(queries.SELECT_COMPLETED_SESSIONS, _params(map_id, limit=limit))
        return [row[0] for row in rows]


def _params(map_id: MapId, **extra: object) -> dict[str, object]:
    return {"package": map_id.package, "version": map_id.version_code, **extra}
