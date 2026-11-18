import json
import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import AbstractContextManager
from pathlib import Path

import sqlite_vec

from artemis.app_memory import ids, queries, schema
from artemis.app_memory.document_store import DocumentStore
from artemis.app_memory.graph_store import GraphStore
from artemis.app_memory.knowledge_store import KnowledgeStore
from artemis.app_memory.models import (
    AbstractScreen,
    CanonicalAction,
    EdgeCounts,
    EdgeId,
    KnownState,
    MapId,
    MapStats,
    ObservationRecord,
    ObservationStatus,
    SessionOutcome,
    StateId,
    StateSample,
)
from artemis.app_memory.transaction import transaction
from artemis.app_memory.rows import (
    known_from_rows,
    map_key,
    observation_params,
    state_params,
    stats_from_row,
)

BUSY_TIMEOUT_MS = 30_000


class VectorExtensionError(RuntimeError):
    pass


class MapStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.documents = DocumentStore(conn)
        self.graph = GraphStore(conn)
        self.knowledge = KnowledgeStore(conn)

    @classmethod
    def open(cls, path: Path) -> "MapStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
        try:
            _configure(conn)
            store = cls(conn)
            store._create_schema()
        except BaseException:
            conn.close()
            raise
        return store

    @classmethod
    def open_read_only(cls, path: Path) -> "MapStore":
        """Reads an existing file and never writes it. Raises sqlite3.Error when it is missing."""
        uri = f"{path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
        try:
            _load_vector_extension(conn)
        except VectorExtensionError:
            conn.close()
            raise
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    def _transaction(self) -> AbstractContextManager[sqlite3.Connection]:
        return transaction(self._conn)

    def _create_schema(self) -> None:
        with self._transaction() as conn:
            for statement in schema.TABLES:
                conn.execute(statement)

    def put_state(
        self,
        map_id: MapId,
        state_id: StateId,
        screen: AbstractScreen,
        now: float,
        sample: StateSample | None = None,
        version_name: str | None = None,
    ) -> None:
        params = state_params(map_id, state_id, screen, now, sample)
        with self._transaction() as conn:
            _touch_version(conn, map_id, now, version_name)
            conn.execute(queries.UPSERT_STATE, params)

    def put_outside_state(self, map_id: MapId, now: float) -> StateId:
        state_id = ids.outside_state_id(map_id)
        with self._transaction() as conn:
            _touch_version(conn, map_id, now)
            conn.execute(queries.INSERT_OUTSIDE, (state_id, *map_key(map_id), now, now))
        return state_id

    def known_states(self, map_id: MapId) -> list[KnownState]:
        return list(known_from_rows(self._conn.execute(queries.SELECT_STATES, map_key(map_id))))

    def put_edge(
        self,
        map_id: MapId,
        src: StateId,
        dst: StateId,
        actions: Sequence[CanonicalAction],
        now: float,
    ) -> EdgeId:
        signature = ids.action_signature(actions)
        edge_id = ids.edge_id(src, signature, dst)
        payload = json.dumps([a.as_dict() for a in actions], sort_keys=True)
        with self._transaction() as conn:
            conn.execute(
                queries.UPSERT_EDGE, (edge_id, *map_key(map_id), src, dst, signature, payload, now)
            )
        return edge_id

    def record_observation(self, record: ObservationRecord) -> None:
        with self._transaction() as conn:
            previous = conn.execute(
                queries.SELECT_OBSERVED_EDGE, (record.session_id, record.step_id)
            ).fetchone()
            conn.execute(queries.UPSERT_OBSERVATION, observation_params(record))
            touched = {record.edge_id, previous[0] if previous else None}
            _refresh_counts(conn, touched)

    def observed_steps(self, session_id: str) -> set[str]:
        rows = self._conn.execute(queries.SELECT_OBSERVED_STEPS, (session_id,))
        return {row[0] for row in rows}

    def open_session(self, session_id: str) -> None:
        with self._transaction() as conn:
            conn.execute(queries.INSERT_LIVE_SESSION, (session_id,))

    def finalize_session(
        self, session_id: str, outcome: SessionOutcome, status: ObservationStatus, now: float
    ) -> None:
        with self._transaction() as conn:
            conn.execute(queries.SETTLE_OBSERVATIONS, (status.value, session_id))
            edges = conn.execute(queries.SELECT_SESSION_EDGES, (session_id,)).fetchall()
            _refresh_counts(conn, (row[0] for row in edges))
            conn.execute(queries.FINALIZE_SESSION, (session_id, outcome.value, now))

    def live_sessions(self) -> list[str]:
        return [row[0] for row in self._conn.execute(queries.SELECT_LIVE_SESSIONS)]

    def last_activity(self, session_id: str) -> float | None:
        return self._conn.execute(queries.SELECT_LAST_ACTIVITY, (session_id,)).fetchone()[0]

    def map_stats(self) -> list[MapStats]:
        return [stats_from_row(row) for row in self._conn.execute(queries.SELECT_MAP_STATS)]

    def rebuild_counts(self) -> None:
        with self._transaction() as conn:
            conn.execute(schema.REBUILD_COUNTS)

    def edge_counts(self, edge_id: EdgeId) -> EdgeCounts:
        row = self._conn.execute(queries.SELECT_COUNTS, (edge_id,)).fetchone()
        return EdgeCounts(*row)

    def table_names(self) -> set[str]:
        rows = self._conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {row[0] for row in rows}


def _configure(conn: sqlite3.Connection) -> None:
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _load_vector_extension(conn)


def _load_vector_extension(conn: sqlite3.Connection) -> None:
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (AttributeError, sqlite3.Error, OSError) as exc:
        raise VectorExtensionError(f"sqlite-vec could not be loaded: {exc}") from exc


def _touch_version(
    conn: sqlite3.Connection, map_id: MapId, now: float, version_name: str | None = None
) -> None:
    conn.execute(queries.TOUCH_VERSION, (*map_key(map_id), version_name, now, now))


def _refresh_counts(conn: sqlite3.Connection, edge_ids: Iterable[str | None]) -> None:
    for edge_id in {e for e in edge_ids if e is not None}:
        conn.execute(f"{schema.REBUILD_COUNTS} WHERE edge_id = ?", (edge_id,))
