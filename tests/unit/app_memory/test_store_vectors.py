import sqlite3
import struct

import pytest
import sqlite_vec

from artemis.app_memory.models import EmbeddingModel
from artemis.app_memory.store import MapStore, VectorExtensionError


@pytest.fixture
def store(tmp_path):
    opened = MapStore.open(tmp_path / "app_memory.db")
    yield opened
    opened.close()


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
