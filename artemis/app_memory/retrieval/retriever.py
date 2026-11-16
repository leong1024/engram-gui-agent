import asyncio
import functools
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Protocol, TypeVar

from artemis.app_memory.embeddings import EmbeddingProvider
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import EmbeddingModel, MapId, StateId
from artemis.app_memory.retrieval.candidates import candidate_maps, find_candidates
from artemis.app_memory.retrieval.selector import Selection, Selector
from artemis.app_memory.retrieval.types import (
    Candidate,
    NoTarget,
    NoTargetReason,
    Proposal,
    Resolution,
    RetrievalSettings,
    TargetResolution,
)
from artemis.app_memory.store import MapStore
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class StoreReader(Protocol):
    """Runs `job` on the thread that owns the store and awaits its result."""

    def __call__(self, job: Callable[[MapStore], T], /) -> Awaitable[T]: ...


class Retriever:
    """Finds a milestone's target state: tier 1 inside each map, tier 2 across maps."""

    def __init__(
        self,
        read: StoreReader,
        provider: EmbeddingProvider,
        selector: Selector,
        settings: RetrievalSettings = RetrievalSettings(),
    ) -> None:
        self._read = read
        self._provider = provider
        self._selector = selector
        self._settings = settings
        self._provider_down = False

    async def resolve(
        self, goal: str, milestone: Milestone, installed: Mapping[str, int]
    ) -> Resolution:
        fallback = self._settings.fallback_versions
        maps = await self._read(
            lambda store: candidate_maps(installed, store.graph.maps(), fallback)
        )
        if not (maps.primary or maps.fallback):
            return NoTarget(milestone.key, NoTargetReason.NO_MAPS)
        vector = await self._embed(milestone.query)
        if vector is None:
            return NoTarget(milestone.key, NoTargetReason.PROVIDER_UNAVAILABLE)
        model = await self._read(functools.partial(self._stored_model, dim=len(vector)))
        if model is None:
            return NoTarget(milestone.key, NoTargetReason.NO_VECTORS)
        search = functools.partial(self._tier_one, goal, milestone, vector, model)
        proposals = await search(maps.primary, borrowed=False)
        proposals = proposals or await search(maps.fallback, borrowed=True)
        chosen = await self._tier_two(goal, milestone, proposals)
        if chosen is None:
            return NoTarget(milestone.key, NoTargetReason.NO_MATCH)
        return _resolution(milestone, chosen)

    async def _embed(self, text: str) -> list[float] | None:
        """None for the rest of the run once the provider has failed, with one warning."""
        if self._provider_down:
            return None
        try:
            return await self._provider.embed_query(text)
        except Exception as exc:
            self._provider_down = True
            logger.warning(f"App memory finds no targets for the rest of this run: {exc!r}")
            return None

    def _stored_model(self, store: MapStore, dim: int) -> EmbeddingModel | None:
        provider = self._provider
        return store.documents.embedding_model(provider.provider, provider.model, dim)

    async def _tier_one(
        self,
        goal: str,
        milestone: Milestone,
        vector: list[float],
        model: EmbeddingModel,
        maps: Sequence[MapId],
        borrowed: bool,
    ) -> list[Proposal]:
        gate = asyncio.Semaphore(self._settings.map_concurrency)

        async def propose(map_id: MapId) -> Proposal | None:
            async with gate:
                job = functools.partial(
                    find_candidates,
                    model=model,
                    map_id=map_id,
                    vector=vector,
                    settings=self._settings,
                )
                candidates = await self._read(job)
                if not candidates:
                    return None
                selection = await self._selector.select(goal, milestone, candidates)
            return self._accept(selection, candidates, borrowed)

        proposals = await asyncio.gather(*(propose(map_id) for map_id in maps))
        return [proposal for proposal in proposals if proposal is not None]

    async def _tier_two(
        self, goal: str, milestone: Milestone, proposals: Sequence[Proposal]
    ) -> Proposal | None:
        if len(proposals) <= 1:
            return proposals[0] if proposals else None
        candidates = [proposal.candidate for proposal in proposals]
        selection = await self._selector.select(goal, milestone, candidates)
        return self._accept(selection, candidates, proposals[0].borrowed)

    def _accept(
        self, selection: Selection | None, candidates: Sequence[Candidate], borrowed: bool
    ) -> Proposal | None:
        if selection is None or selection.confidence < self._settings.min_confidence:
            return None
        by_id = {candidate.card.state_id: candidate for candidate in candidates}
        candidate = by_id.get(StateId(selection.state_id or ""))
        if candidate is None:
            return None
        return Proposal(candidate, selection.confidence, selection.reason, borrowed)


def _resolution(milestone: Milestone, proposal: Proposal) -> TargetResolution:
    candidate = proposal.candidate
    return TargetResolution(
        milestone_key=milestone.key,
        state_id=candidate.card.state_id,
        map_id=candidate.map_id,
        borrowed=proposal.borrowed,
        confidence=proposal.confidence,
        reason=proposal.reason,
        last_hop_edge_id=candidate.last_hop.edge_id if candidate.last_hop else None,
    )
