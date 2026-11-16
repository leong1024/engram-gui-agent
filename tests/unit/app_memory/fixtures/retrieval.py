import hashlib
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from langchain_core.embeddings import Embeddings

from artemis.app_memory.embeddings import EmbeddingProvider
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.retrieval import Selection
from artemis.app_memory.retrieval.types import Candidate
from artemis.app_memory.store import MapStore

DIM = 256
WORD = re.compile(r"[a-z]+")


class HashEmbeddings(Embeddings):
    """Bag of words hashed into a fixed size: texts that share words are similar."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        if self.fail:
            raise ConnectionError("embedding provider unreachable")
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * DIM
        for word in WORD.findall(text.lower()):
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def hash_provider(fail: bool = False) -> EmbeddingProvider:
    return EmbeddingProvider("fake", "hash", DIM, HashEmbeddings(fail))


async def embed_all(store: MapStore, provider: EmbeddingProvider) -> None:
    docs = store.documents.stale_documents(None)
    vectors = await provider.embed_documents([doc.text for doc in docs])
    store.documents.put_vectors(provider.model_for(DIM), docs, vectors, 1.0)


Choose = Callable[[Sequence[Candidate]], Candidate | None]


def by_title(title: str) -> Choose:
    return lambda candidates: next((c for c in candidates if c.card.title == title), None)


@dataclass
class FakeSelector:
    """Picks with `choose` at a fixed confidence and records every call's candidates."""

    choose: Choose = lambda candidates: candidates[0]
    confidence: float = 0.9
    calls: list[tuple[Candidate, ...]] = field(default_factory=list)

    async def select(
        self, goal: str, milestone: Milestone, candidates: Sequence[Candidate]
    ) -> Selection | None:
        self.calls.append(tuple(candidates))
        chosen = self.choose(candidates)
        state_id = chosen.card.state_id if chosen else None
        return Selection(state_id=state_id, confidence=self.confidence, reason="fake")
