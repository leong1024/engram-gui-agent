import json
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from typing import Any
from contextlib import contextmanager
from pathlib import Path

import sqlite_vec

from artemis.app_memory import ids, queries, schema
from artemis.app_memory.models import (
    AbstractScreen,
    CanonicalAction,
    EdgeCounts,
    EdgeId,
    EmbeddingModel,
    KnownState,
    MapId,
    ObservationRecord,
    StateId,
)

BUSY_TIMEOUT_MS = 30_000


class VectorExtensionError(RuntimeError):
    pass


class MapStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

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

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def _create_schema(self) -> None:
        with self._transaction() as conn:
            for statement in schema.TABLES:
                conn.execute(statement)

    def put_state(
        self, map_id: MapId, state_id: StateId, screen: AbstractScreen, now: float
    ) -> None:
        with self._transaction() as conn:
            _touch_version(conn, map_id, now)
            conn.execute(queries.UPSERT_STATE, _state_params(map_id, state_id, screen, now))

    def put_outside_state(self, map_id: MapId, now: float) -> StateId:
        state_id = ids.outside_state_id(map_id)
        with self._transaction() as conn:
            _touch_version(conn, map_id, now)
            conn.execute(queries.INSERT_OUTSIDE, (state_id, *_map_key(map_id), now, now))
        return state_id

    def known_states(self, map_id: MapId) -> list[KnownState]:
        rows = self._conn.execute(queries.SELECT_STATES, _map_key(map_id)).fetchall()
        return [KnownState(StateId(row[0]), _screen_from_row(row[1:])) for row in rows]

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
                queries.UPSERT_EDGE, (edge_id, *_map_key(map_id), src, dst, signature, payload, now)
            )
        return edge_id

    def record_observation(self, record: ObservationRecord) -> None:
        with self._transaction() as conn:
            previous = conn.execute(
                queries.SELECT_OBSERVED_EDGE, (record.session_id, record.step_id)
            ).fetchone()
            conn.execute(queries.UPSERT_OBSERVATION, _observation_params(record))
            touched = {record.edge_id, previous[0] if previous else None}
            _refresh_counts(conn, touched)

    def rebuild_counts(self) -> None:
        with self._transaction() as conn:
            conn.execute(schema.REBUILD_COUNTS)

    def edge_counts(self, edge_id: EdgeId) -> EdgeCounts:
        row = self._conn.execute(queries.SELECT_COUNTS, (edge_id,)).fetchone()
        return EdgeCounts(*row)

    def ensure_vector_table(self, model: EmbeddingModel) -> str:
        with self._transaction() as conn:
            conn.execute(
                queries.INSERT_MODEL, (model.model_id, model.provider, model.model, model.dim)
            )
            conn.execute(schema.vector_table_ddl(model))
        return schema.vector_table_name(model.model_id)

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


def _map_key(map_id: MapId) -> tuple[str, int]:
    return map_id.package, map_id.version_code


def _touch_version(conn: sqlite3.Connection, map_id: MapId, now: float) -> None:
    conn.execute(queries.TOUCH_VERSION, (*_map_key(map_id), now, now))


def _state_params(
    map_id: MapId, state_id: StateId, screen: AbstractScreen, now: float
) -> tuple[object, ...]:
    return (
        state_id,
        *_map_key(map_id),
        screen.activity,
        screen.coarse_key,
        json.dumps(screen.skeleton),
        json.dumps(sorted(screen.static_tokens)),
        screen.is_opaque,
        screen.dhash,
        now,
        now,
    )


def _screen_from_row(row: Sequence[Any]) -> AbstractScreen:
    activity, coarse_key, skeleton, static_tokens, is_opaque, dhash = row
    return AbstractScreen(
        activity=activity,
        coarse_key=coarse_key,
        skeleton=tuple(json.loads(skeleton)),
        static_tokens=frozenset(json.loads(static_tokens)),
        is_opaque=bool(is_opaque),
        dhash=dhash,
    )


def _refresh_counts(conn: sqlite3.Connection, edge_ids: Iterable[str | None]) -> None:
    for edge_id in {e for e in edge_ids if e is not None}:
        conn.execute(f"{schema.REBUILD_COUNTS} WHERE edge_id = ?", (edge_id,))


def _observation_params(record: ObservationRecord) -> tuple[object, ...]:
    return (
        record.session_id,
        record.step_id,
        record.edge_id,
        record.src_state_id,
        record.action_signature,
        record.status.value,
        record.recorded_at,
    )
