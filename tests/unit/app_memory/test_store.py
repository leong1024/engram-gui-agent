import multiprocessing
import sqlite3
import struct
from pathlib import Path

import pytest
import sqlite_vec

from artemis.app_memory import ids
from artemis.app_memory.abstraction import abstract, match
from artemis.app_memory.models import (
    EdgeCounts,
    EdgeId,
    EmbeddingModel,
    MapId,
    ObservationRecord,
    ObservationStatus,
    ScreenObservation,
    StateId,
)
from artemis.app_memory.store import MapStore, VectorExtensionError
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.writer import click, make_observation, write_confirmed

MAP = MapId("com.android.settings", 1)
WRITERS = 2
PER_WRITER = 100


def _screen(scroll: str = "top"):
    observation = ScreenObservation(
        package=MAP.package,
        activity=".Settings",
        version_code=MAP.version_code,
        elements=tuple(screens.settings(scroll)),
    )
    return abstract(observation)


def _seed_edge(store: MapStore) -> tuple[StateId, EdgeId]:
    src = ids.state_id(MAP, "src")
    dst = ids.state_id(MAP, "dst")
    store.put_state(MAP, src, _screen("top"), now=1.0)
    store.put_state(MAP, dst, _screen("bottom"), now=1.0)
    return src, store.put_edge(MAP, src, dst, [click("Battery")], now=1.0)


@pytest.fixture
def store(tmp_path: Path):
    opened = MapStore.open(tmp_path / "app_memory.db")
    yield opened
    opened.close()


def test_open_creates_every_table_and_uses_wal(store, tmp_path):
    expected = {
        "app_versions",
        "states",
        "edges",
        "observations",
        "harvested_sessions",
        "embedding_models",
        "embeddings",
    }
    assert expected <= store.table_names()
    with sqlite3.connect(tmp_path / "app_memory.db") as raw:
        assert raw.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_reopening_an_existing_file_keeps_its_data(tmp_path):
    path = tmp_path / "app_memory.db"
    first = MapStore.open(path)
    src, edge = _seed_edge(first)
    first.record_observation(make_observation(1, edge, src, ObservationStatus.CONFIRMED))
    first.close()

    second = MapStore.open(path)
    try:
        assert second.edge_counts(edge) == EdgeCounts(1, 0, 0)
        assert len(second.known_states(MAP)) == 2
    finally:
        second.close()


def test_stored_states_round_trip_into_matching(store):
    state = ids.state_id(MAP, "settings")
    store.put_state(MAP, state, _screen("top"), now=1.0)
    store.put_state(MAP, state, _screen("top"), now=2.0)
    known = store.known_states(MAP)
    assert [k.state_id for k in known] == [state]
    assert match(_screen("bottom"), known) == state


def test_known_states_are_scoped_to_one_map_and_skip_outside(store):
    store.put_state(MAP, ids.state_id(MAP, "a"), _screen(), now=1.0)
    other = MapId(MAP.package, 2)
    store.put_state(other, ids.state_id(other, "a"), _screen(), now=1.0)
    store.put_outside_state(MAP, now=1.0)
    assert len(store.known_states(MAP)) == 1


def test_counts_follow_observations_and_status_changes(store):
    src, edge = _seed_edge(store)
    store.record_observation(make_observation(1, edge, src, ObservationStatus.PROVISIONAL))
    store.record_observation(make_observation(2, edge, src, ObservationStatus.PROVISIONAL))
    store.record_observation(make_observation(3, None, src, ObservationStatus.PROVISIONAL))
    assert store.edge_counts(edge) == EdgeCounts(0, 0, 2)

    store.record_observation(make_observation(1, edge, src, ObservationStatus.CONFIRMED))
    store.record_observation(make_observation(2, edge, src, ObservationStatus.DISCOUNTED))
    assert store.edge_counts(edge) == EdgeCounts(1, 1, 0)

    store.record_observation(make_observation(1, edge, src, ObservationStatus.DROPPED))
    assert store.edge_counts(edge) == EdgeCounts(0, 1, 0)


def test_rebuild_counts_repairs_a_stale_cache(store, tmp_path):
    src, edge = _seed_edge(store)
    for step in range(3):
        store.record_observation(make_observation(step, edge, src, ObservationStatus.CONFIRMED))
    with sqlite3.connect(tmp_path / "app_memory.db") as raw:
        raw.execute("UPDATE edges SET confirmed_n = 99, provisional_n = 7")
    store.rebuild_counts()
    assert store.edge_counts(edge) == EdgeCounts(3, 0, 0)


def test_an_edge_must_leave_its_source_state(store):
    src, _ = _seed_edge(store)
    with pytest.raises(sqlite3.IntegrityError):
        store.put_edge(MAP, src, src, [click("Battery")], now=2.0)


def test_a_rejected_write_does_not_wedge_the_store(store):
    src, _ = _seed_edge(store)
    ghost = StateId("missing")
    with pytest.raises(sqlite3.IntegrityError):
        store.put_edge(MAP, src, ghost, [click("x")], now=2.0)
    store.put_edge(MAP, src, ids.state_id(MAP, "dst"), [click("again")], now=3.0)


def test_two_writer_processes_lose_no_writes(tmp_path):
    path = tmp_path / "app_memory.db"
    seed = MapStore.open(path)
    src, edge = _seed_edge(seed)
    seed.close()

    context = multiprocessing.get_context("spawn")
    workers = [
        context.Process(
            target=write_confirmed, args=(str(path), f"w{n}", str(edge), str(src), PER_WRITER)
        )
        for n in range(WRITERS)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=120)
        assert worker.exitcode == 0

    check = MapStore.open(path)
    try:
        assert check.edge_counts(edge) == EdgeCounts(WRITERS * PER_WRITER, 0, 0)
        check.rebuild_counts()
        assert check.edge_counts(edge) == EdgeCounts(WRITERS * PER_WRITER, 0, 0)
    finally:
        check.close()


def test_vector_tables_are_created_per_model_and_searchable(store):
    model = EmbeddingModel("gemini/text-embedding-004", "gemini", "text-embedding-004", 4)
    table = store.ensure_vector_table(model)
    assert store.ensure_vector_table(model) == table
    assert table in store.table_names()


def test_vector_table_accepts_and_ranks_embeddings(tmp_path):
    path = tmp_path / "app_memory.db"
    opened = MapStore.open(path)
    table = opened.ensure_vector_table(EmbeddingModel("m", "p", "m", 2))
    opened.close()

    raw = sqlite3.connect(path)
    raw.enable_load_extension(True)
    sqlite_vec.load(raw)
    for owner, vector in (("near", [1.0, 0.0]), ("far", [0.0, 1.0])):
        raw.execute(
            f"INSERT INTO {table} (map_key, owner_kind, owner_id, embedding) VALUES (?, ?, ?, ?)",
            ("pkg:1", "state", owner, struct.pack("2f", *vector)),
        )
    rows = raw.execute(
        f"SELECT owner_id FROM {table} WHERE embedding MATCH ? AND k = 2 AND map_key = ? "
        "ORDER BY distance",
        (struct.pack("2f", 1.0, 0.1), "pkg:1"),
    ).fetchall()
    raw.close()
    assert [r[0] for r in rows] == ["near", "far"]


def test_unloadable_vector_extension_fails_loudly(tmp_path, monkeypatch):
    def broken(_conn):
        raise sqlite3.OperationalError("no such extension")

    monkeypatch.setattr(sqlite_vec, "load", broken)
    with pytest.raises(VectorExtensionError, match="sqlite-vec"):
        MapStore.open(tmp_path / "app_memory.db")


def test_a_build_without_extension_loading_fails_loudly(tmp_path, monkeypatch):
    class NoExtensions(sqlite3.Connection):
        def enable_load_extension(self, enabled):
            raise AttributeError("not authorized")

    real_connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3, "connect", lambda *a, **kw: real_connect(*a, factory=NoExtensions, **kw)
    )
    with pytest.raises(VectorExtensionError):
        MapStore.open(tmp_path / "app_memory.db")
