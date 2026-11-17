import sqlite3
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType

from artemis.app_memory.knowledge import summaries
from artemis.app_memory.knowledge.reports import Capabilities, NotMapped, Overview
from artemis.app_memory.knowledge_store import MapCounts
from artemis.app_memory.service import DB_FILE
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import DATA_ENGINE_DB, TraceReader
from artemis.config.agent import AppMemoryConfig, load_agent_config
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)


class Knowledge:
    """App knowledge reports, read from the databases on each call. A missing database reads
    as no maps or no goals. Open one per request: it holds read-only connections."""

    def __init__(
        self, store: MapStore | None, reader: TraceReader | None, config: AppMemoryConfig
    ) -> None:
        self._store = store
        self._reader = reader
        self._config = config

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
        """Each map, with `has_vectors` for the configured embedding model. The model is
        looked up the way enrichment does, from the stored models, so no provider is called."""
        if self._store is None:
            return []
        embedding = self._config.embedding
        model = self._store.documents.embedding_model(
            embedding.provider, embedding.model, embedding.dimensions
        )
        return self._store.knowledge.maps(model.model_id if model else None)

    def _goals(self, session_ids: Sequence[str]) -> list[str]:
        if self._reader is None:
            return []
        try:
            return list(self._reader.session_goals(session_ids).values())
        except sqlite3.Error as exc:
            logger.warning(f"App knowledge shows no example goals: {exc!r}")
            return []


def open_knowledge(traces_dir: Path, config: AppMemoryConfig | None = None) -> Knowledge:
    """Opens both databases read-only and creates neither. Without `config`, reads the
    agent config's app-memory section."""
    if config is None:
        config = load_agent_config().app_memory
    db_path = traces_dir / DB_FILE
    store = MapStore.open_read_only(db_path) if db_path.is_file() else None
    reader = TraceReader.open(traces_dir) if (traces_dir / DATA_ENGINE_DB).is_file() else None
    return Knowledge(store, reader, config)
