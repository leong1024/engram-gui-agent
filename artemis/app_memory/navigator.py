import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from artemis.app_memory.embeddings import EmbeddingUnavailable, open_provider
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import ScreenObservation
from artemis.app_memory.retrieval import LLMSelector, NoTarget, Retriever, StoreReader
from artemis.app_memory.retrieval.selector import SELECTOR_NODE
from artemis.app_memory.routing import Route, RoutePlanner, RouteTracker
from artemis.app_memory.targets import Found, KnownTarget, TargetQueue
from artemis.config.agent import AppMemoryConfig
from artemis.services.llm import get_llm
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)


class Navigator:
    """The run's routes: targets found in the background, and one tracker per milestone.
    `request` may be called from any thread; everything else runs on the event loop."""

    def __init__(self, retriever: Retriever, read: StoreReader, installed: Mapping[str, int]):
        self._retriever = retriever
        self._read = read
        self._installed = installed
        self._loop = asyncio.get_running_loop()
        self._queue = TargetQueue(self._find)
        self._trackers: dict[str, RouteTracker] = {}

    def request(self, goal: str, milestones: Sequence[Milestone]) -> None:
        self._loop.call_soon_threadsafe(self._request, goal, list(milestones))

    def route_for(self, milestone_key: str, observation: ScreenObservation) -> Route | None:
        tracker = self._trackers.get(milestone_key) or self._track(milestone_key)
        return tracker.step(observation) if tracker else None

    async def close(self) -> None:
        await self._queue.close()

    def _request(self, goal: str, milestones: list[Milestone]) -> None:
        for key in self._queue.request(goal, milestones):
            self._trackers.pop(key, None)

    def _track(self, milestone_key: str) -> RouteTracker | None:
        found = self._queue.result(milestone_key)
        if not isinstance(found, KnownTarget):
            return None
        resolution, milestone = found.resolution, found.milestone
        planner = RoutePlanner(milestone, found.graph, resolution.state_id, resolution.borrowed)
        return self._trackers.setdefault(milestone_key, RouteTracker(planner))

    async def _find(self, goal: str, milestone: Milestone) -> Found:
        resolution = await self._retriever.resolve(goal, milestone, self._installed)
        if isinstance(resolution, NoTarget):
            logger.info(f"App memory has no target for {milestone.key}: {resolution.reason}")
            return resolution
        graph = await self._read(lambda store: store.graph.map_graph(resolution.map_id))
        return KnownTarget(milestone, resolution, graph)


NavigatorFactory = Callable[[StoreReader, Mapping[str, int]], Navigator]


def open_navigator(ctx: Any, config: AppMemoryConfig) -> NavigatorFactory | None:
    """None when the embedding provider has no key: no milestone gets a target this run."""
    try:
        provider = open_provider(config.embedding)
    except EmbeddingUnavailable as exc:
        logger.warning(f"App memory finds no targets for this run: {exc}")
        return None
    selector = LLMSelector(lambda: get_llm(ctx, SELECTOR_NODE, temperature=0.0))
    return lambda read, installed: Navigator(Retriever(read, provider, selector), read, installed)
