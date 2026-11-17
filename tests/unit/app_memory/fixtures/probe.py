import asyncio
from pathlib import Path

from langchain_core.embeddings import Embeddings

from artemis.app_memory.embeddings import EmbeddingProvider
from artemis.app_memory.knowledge import open_knowledge
from artemis.app_memory.knowledge.reports import ProbeResult
from artemis.app_memory.models import MapId
from artemis.app_memory.store import MapStore
from artemis.config.agent import AppMemoryConfig
from tests.unit.app_memory.fixtures.maps import SETTINGS_MAP, MapBuilder, launch, tap
from tests.unit.app_memory.fixtures.retrieval import DIM, HashEmbeddings, embed_all

CONFIG = AppMemoryConfig()


def provider(embeddings: Embeddings | None = None) -> EmbeddingProvider:
    """The hash-based fake under the configured provider and model, so stored vectors match
    the configured embedding model."""
    embedding = CONFIG.embedding
    return EmbeddingProvider(
        embedding.provider, embedding.model, DIM, embeddings or HashEmbeddings()
    )


def settings_map(store: MapStore, map_id: MapId = SETTINGS_MAP, *, display: bool = True) -> None:
    """Launch, then Home, then Display. Sound has no inbound edge, so no route reaches it."""
    maps = MapBuilder(store, map_id)
    home = maps.state("Home", "The main list of settings.", ("open a settings page",))
    maps.edge(maps.outside(), home, launch(map_id.package))
    if display:
        dark = maps.state("Display", "Brightness and the dark theme.", ("turn on dark theme",))
        maps.edge(home, dark, tap("Display"))
    maps.state("Sound", "Volume and ringtones.", ("change the volume",))


def embed(store: MapStore, fake: EmbeddingProvider | None = None) -> None:
    asyncio.run(embed_all(store, fake or provider()))


def probe(
    traces: Path,
    query: str,
    package: str | None = None,
    embeddings: Embeddings | None = None,
) -> ProbeResult:
    fake = provider(embeddings)
    with open_knowledge(traces, CONFIG, lambda: fake) as knowledge:
        return asyncio.run(knowledge.probe(query, package))
