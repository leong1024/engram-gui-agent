import asyncio
import functools
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from artemis.app_memory.describer import (
    DescriberService,
    DescriptionLens,
    edge_job,
    save_description,
    state_job,
)
from artemis.app_memory.document_store import DocumentStore
from artemis.app_memory.documents import EmbeddingDoc, Owner
from artemis.app_memory.embeddings import EmbeddingProvider, EmbeddingUnavailable, open_provider
from artemis.app_memory.models import EmbeddingModel
from artemis.app_memory.store import MapStore
from artemis.config.agent import AppMemoryConfig
from artemis.config.llm import get_default_llm_config
from artemis.memory.step_memory import JobKey, StepLens
from artemis.services.llm import get_llm
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)

QUEUE_LIMIT = 50
CLOSE_TIMEOUT_SECONDS = 5.0
DESCRIBER_NODE = "app_memory_describer"

StoreJob = Callable[[MapStore], None]


class Enrichment:
    """Describes and embeds pending states and edges in the background.

    Two threads meet here. `queue` and the `_save_*` jobs run on the app memory worker
    thread, which owns the store. Describer and embedding calls run on the run's event loop,
    and hand every write back to the worker through `offload`."""

    def __init__(
        self,
        lens: StepLens,
        provider: EmbeddingProvider | None,
        image_path: Callable[[str], Path],
        clock: Callable[[], float] = time.time,
        retry_limit: int = 3,
    ) -> None:
        self._describer = DescriberService(lens, self._described, self._gave_up, retry_limit)
        self._provider = provider
        self._image_path = image_path
        self._clock = clock
        self._loop: asyncio.AbstractEventLoop | None = None
        self._offload: Callable[[StoreJob], None] = lambda job: None
        self._model: EmbeddingModel | None = None
        self._embedding: set[tuple[str, str]] = set()
        self._tasks: set[asyncio.Task[None]] = set()
        self._closing = False
        self._warned = False

    def bind(self, loop: asyncio.AbstractEventLoop, offload: Callable[[StoreJob], None]) -> None:
        self._loop, self._offload = loop, offload

    def queue(self, store: MapStore) -> None:
        if self._loop is None or self._closing:
            return
        documents = store.documents
        jobs = [state_job(s, self._image_path) for s in documents.pending_states(QUEUE_LIMIT)]
        jobs += [edge_job(edge) for edge in documents.pending_edges(QUEUE_LIMIT)]
        self._loop.call_soon_threadsafe(self._submit, jobs, self._stale(documents))

    async def close(self, timeout: float = CLOSE_TIMEOUT_SECONDS) -> None:
        self._closing = True
        await self._describer.flush(timeout)
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _stale(self, documents: DocumentStore) -> list[EmbeddingDoc]:
        provider = self._provider
        if provider is None:
            return []
        if self._model is None:
            self._model = documents.embedding_model(
                provider.provider, provider.model, provider.dimensions
            )
        return documents.stale_documents(self._model.model_id if self._model else None)[
            :QUEUE_LIMIT
        ]

    def _submit(self, jobs: Sequence[tuple[str, dict[str, Any]]], docs: list[EmbeddingDoc]) -> None:
        if self._closing:
            return
        for key, payload in jobs:
            if not self._describer.has_job(key):
                self._describer.submit(key, payload)
        fresh = [doc for doc in docs if (doc.owner.key, doc.text_hash) not in self._embedding]
        if fresh:
            self._embedding.update((doc.owner.key, doc.text_hash) for doc in fresh)
            task = asyncio.create_task(self._embed(fresh))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _embed(self, docs: list[EmbeddingDoc]) -> None:
        if self._provider is None:
            return
        try:
            vectors = await self._provider.embed_documents([doc.text for doc in docs])
        except Exception as exc:
            if not self._warned:
                self._warned = True
                logger.warning(f"App memory embeddings failed; they wait for a later run: {exc}")
            return
        model = self._provider.model_for(len(vectors[0]))
        self._offload(functools.partial(self._save_vectors, model, docs, vectors))

    def _save_vectors(
        self,
        model: EmbeddingModel,
        docs: list[EmbeddingDoc],
        vectors: list[list[float]],
        store: MapStore,
    ) -> None:
        store.documents.put_vectors(model, docs, vectors, self._clock())
        self._model = model
        self.queue(store)

    def _described(self, key: JobKey, summary: str) -> None:
        self._offload(functools.partial(self._save_description, key, summary))

    def _save_description(self, key: JobKey, summary: str, store: MapStore) -> None:
        save_description(store.documents, key, summary)
        self.queue(store)

    def _gave_up(self, key: JobKey) -> None:
        owner = Owner.parse(str(key))
        self._offload(lambda store: store.documents.mark_failed(owner))


def open_enrichment(
    ctx: Any, config: AppMemoryConfig, image_path: Callable[[str], Path]
) -> Enrichment | None:
    """None when the describer has no credentials: descriptions then stay pending."""
    try:
        llm_config = getattr(ctx, "llm_config", None) or get_default_llm_config()
        llm_config.get_agent(DESCRIBER_NODE).validate_provider(DESCRIBER_NODE)
    except Exception as exc:
        logger.warning(f"App memory descriptions stay pending for this run: {exc}")
        return None
    try:
        provider = open_provider(config.embedding)
    except EmbeddingUnavailable as exc:
        logger.warning(f"App memory embeddings are off for this run: {exc}")
        provider = None
    lens = DescriptionLens(lambda: get_llm(ctx, DESCRIBER_NODE))
    return Enrichment(lens, provider, image_path)
