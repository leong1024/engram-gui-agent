import functools
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType

from artemis.app_memory.embeddings import open_provider
from artemis.app_memory.knowledge import probe as route_probe
from artemis.app_memory.knowledge import summaries
from artemis.app_memory.knowledge.probe import Embedder
from artemis.app_memory.knowledge.reports import Capabilities, NotMapped, Overview, ProbeResult
from artemis.app_memory.knowledge_store import MapCounts
from artemis.app_memory.models import EmbeddingModel
from artemis.app_memory.service import DB_FILE
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import DATA_ENGINE_DB, TraceReader
from artemis.config.agent import AppMemoryConfig, load_agent_config
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)


class Knowledge:
    """App knowledge reports, read from the databases on each call. A missing database reads
    as no maps or no goals. Open one per request: it holds read-only connections. `embedder`
    builds the query's embedding provider, by default from `config`, and only a probe calls it."""

    def __init__(
        self,
        store: MapStore | None,
        reader: TraceReader | None,
        config: AppMemoryConfig,
        embedder: Embedder | None = None,
    ) -> None:
        self._store = store
        self._reader = reader
        self._config = config
        self._embedder = embedder or functools.partial(open_provider, config.embedding)

    def overview(self) -> Overview:
        return summaries.overview(self._maps(), self._config.hints_on)

    def capabilities(self, package: str) -> Capabilities | NotMapped:
        versions = summaries.versions_of(self._maps(), package)
        if self._store is None or not versions:
            return summaries.not_mapped(package)
        newest = versions[0].map_id
        pages = self._store.knowledge.pages(newest)
        sessions = self._store.knowledge.completed_sessions(newest, summaries.GOAL_SESSIONS)
        return summaries.capabilities(versions, pages, self._goals(sessions), self._config.hints_on)

    async def probe(self, query: str, package: str | None = None) -> ProbeResult:
        """Never calls an LLM and never touches a device."""
        model = self._stored_model()
        return await route_probe.probe(self._store, model, self._embedder, query, package)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()

    def __enter__(self) -> "Knowledge":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _maps(self) -> list[MapCounts]:
        """Each map, with `has_vectors` for the configured embedding model."""
        if self._store is None:
            return []
        model = self._stored_model()
        return self._store.knowledge.maps(model.model_id if model else None)

    def _stored_model(self) -> EmbeddingModel | None:
        """The configured embedding model as stored. It is looked up the way enrichment does,
        from the stored models, so no provider is called."""
        if self._store is None:
            return None
        embedding = self._config.embedding
        return self._store.documents.embedding_model(
            embedding.provider, embedding.model, embedding.dimensions
        )

    def _goals(self, session_ids: Sequence[str]) -> list[str]:
        if self._reader is None:
            return []
        try:
            return list(self._reader.session_goals(session_ids).values())
        except sqlite3.Error as exc:
            logger.warning(f"App knowledge shows no example goals: {exc!r}")
            return []


def open_knowledge(
    traces_dir: Path, config: AppMemoryConfig | None = None, embedder: Embedder | None = None
) -> Knowledge:
    """Opens both databases read-only and creates neither. Without `config`, reads the
    agent config's app-memory section."""
    if config is None:
        config = load_agent_config().app_memory
    db_path = traces_dir / DB_FILE
    store = MapStore.open_read_only(db_path) if db_path.is_file() else None
    reader = TraceReader.open(traces_dir) if (traces_dir / DATA_ENGINE_DB).is_file() else None
    return Knowledge(store, reader, config, embedder)
