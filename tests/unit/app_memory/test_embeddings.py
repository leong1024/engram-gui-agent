import sqlite3
from pathlib import Path

import pytest
import sqlite_vec
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from artemis.app_memory import embeddings, schema
from artemis.app_memory.embeddings import EmbeddingUnavailable, open_provider
from artemis.app_memory.models import AbstractScreen, MapId, StateId
from artemis.app_memory.store import MapStore
from artemis.config.agent import AppMemoryEmbeddingConfig

DB = "app_memory.db"
MAP = MapId("com.android.settings", 7)
SCREEN = AbstractScreen(".Settings", "coarse", ("list",), frozenset({"Display"}), False)


@pytest.fixture
def store(tmp_path):
    opened = MapStore.open(tmp_path / DB)
    opened.put_state(MAP, StateId("home"), SCREEN, now=1.0)
    opened.documents.describe_state("home", "Settings", "Lists settings.", ["open Display"])
    yield opened
    opened.close()


def vector_rows(path: Path, table: str, columns: str = "owner_id, rowid") -> list[tuple]:
    raw = sqlite3.connect(path)
    raw.enable_load_extension(True)
    sqlite_vec.load(raw)
    try:
        return raw.execute(f"SELECT {columns} FROM {table} ORDER BY owner_id").fetchall()
    finally:
        raw.close()


@pytest.mark.parametrize(
    ("provider", "client_type"),
    [
        ("gemini", GoogleGenerativeAIEmbeddings),
        ("openai", OpenAIEmbeddings),
        ("ollama", OpenAIEmbeddings),
    ],
)
def test_each_configured_provider_builds_its_langchain_client(monkeypatch, provider, client_type):
    monkeypatch.setattr(embeddings.settings, "GOOGLE_API_KEY", SecretStr("key"))
    monkeypatch.setattr(embeddings.settings, "OPENAI_API_KEY", SecretStr("key"))

    opened = open_provider(AppMemoryEmbeddingConfig(provider=provider, model="m", dimensions=8))

    assert isinstance(opened.client, client_type)
    assert opened.model_for(8).model_id == f"{provider}/m@8"


@pytest.mark.parametrize(
    ("provider", "key"), [("gemini", "GOOGLE_API_KEY"), ("openai", "OPENAI_API_KEY")]
)
def test_a_provider_without_its_key_is_unavailable(monkeypatch, provider, key):
    monkeypatch.setattr(embeddings.settings, key, None)

    with pytest.raises(EmbeddingUnavailable, match="not set"):
        open_provider(AppMemoryEmbeddingConfig(provider=provider))


def test_the_registry_covers_every_configurable_provider():
    configurable = AppMemoryEmbeddingConfig.model_fields["provider"].annotation.__args__
    assert set(embeddings.PROVIDERS) == set(configurable)


def test_each_model_writes_its_own_vector_table(store, tmp_path):
    gemini = embeddings.EmbeddingProvider("gemini", "g", None, client=None).model_for(2)
    openai = embeddings.EmbeddingProvider("openai", "o", None, client=None).model_for(3)
    docs = store.documents.stale_documents(None)

    store.documents.put_vectors(gemini, docs, [[1.0, 0.0]], now=2.0)
    store.documents.put_vectors(openai, docs, [[1.0, 0.0, 0.0]], now=2.0)

    gemini_table = schema.vector_table_name(gemini.model_id)
    openai_table = schema.vector_table_name(openai.model_id)
    assert gemini_table != openai_table
    assert [owner for owner, _ in vector_rows(tmp_path / DB, gemini_table)] == ["home"]
    assert [owner for owner, _ in vector_rows(tmp_path / DB, openai_table)] == ["home"]
    assert store.documents.stale_documents(gemini.model_id) == []
    assert store.documents.embedding_model("openai", "o", None) == openai


def test_a_changed_description_is_embedded_again_in_place(store, tmp_path):
    model = embeddings.EmbeddingProvider("gemini", "g", None, client=None).model_for(2)
    [doc] = store.documents.stale_documents(model.model_id)
    assert doc.text.startswith("Settings. Lists settings. You can: open Display.")
    store.documents.put_vectors(model, [doc], [[1.0, 0.0]], now=2.0)
    before = vector_rows(tmp_path / DB, schema.vector_table_name(model.model_id))

    store.documents.describe_state("home", "Settings", "Changes device settings.", [])
    [changed] = store.documents.stale_documents(model.model_id)
    store.documents.put_vectors(model, [changed], [[0.0, 1.0]], now=3.0)

    assert changed.text_hash != doc.text_hash
    assert vector_rows(tmp_path / DB, schema.vector_table_name(model.model_id)) == before
    assert store.documents.stale_documents(model.model_id) == []


def test_a_vector_table_is_partitioned_by_map(store, tmp_path):
    model = embeddings.EmbeddingProvider("gemini", "g", None, client=None).model_for(2)
    store.documents.put_vectors(model, store.documents.stale_documents(None), [[1.0, 0.0]], 2.0)

    table = schema.vector_table_name(model.model_id)
    assert vector_rows(tmp_path / DB, table, "map_key") == [("com.android.settings:7",)]
