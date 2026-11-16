import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from artemis.app_memory.map_graph import MapGraph
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.retrieval import NoTarget, NoTargetReason, TargetResolution
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)

MILESTONE_CONCURRENCY = 3
BUDGET_SECONDS = 20.0


@dataclass(frozen=True, slots=True)
class KnownTarget:
    milestone: Milestone
    resolution: TargetResolution
    graph: MapGraph


Found = KnownTarget | NoTarget
Find = Callable[[str, Milestone], Awaitable[Found]]


class TargetQueue:
    """The run's targets by milestone key, found in the background, a few at a time.

    Runs on the event loop. A request starts retrieval only for keys it has not seen, and
    forgets keys the plan no longer has."""

    def __init__(
        self,
        find: Find,
        concurrency: int = MILESTONE_CONCURRENCY,
        budget_seconds: float = BUDGET_SECONDS,
    ) -> None:
        self._find = find
        self._gate = asyncio.Semaphore(concurrency)
        self._budget = budget_seconds
        self._found: dict[str, Found] = {}
        self._pending: dict[str, asyncio.Task[None]] = {}

    def request(self, goal: str, milestones: Sequence[Milestone]) -> set[str]:
        """Returns the keys it forgot."""
        keys = {milestone.key for milestone in milestones}
        dropped = (self._found.keys() | self._pending.keys()) - keys
        for key in dropped:
            self._found.pop(key, None)
            if task := self._pending.pop(key, None):
                task.cancel()
        for milestone in milestones:
            if milestone.key not in self._found and milestone.key not in self._pending:
                task = asyncio.create_task(self._run(goal, milestone))
                self._pending[milestone.key] = task
        return dropped

    def result(self, key: str) -> Found | None:
        """None while retrieval for `key` is still running, or was never requested."""
        return self._found.get(key)

    async def join(self) -> None:
        await asyncio.gather(*self._pending.values(), return_exceptions=True)

    async def close(self) -> None:
        for task in self._pending.values():
            task.cancel()
        await self.join()

    async def _run(self, goal: str, milestone: Milestone) -> None:
        async with self._gate:
            try:
                found = await asyncio.wait_for(self._find(goal, milestone), self._budget)
            except TimeoutError:
                found = NoTarget(milestone.key, NoTargetReason.TIMED_OUT)
            except Exception as exc:
                logger.warning(f"App memory retrieval failed for {milestone.key}: {exc!r}")
                found = NoTarget(milestone.key, NoTargetReason.FAILED)
        self._found[milestone.key] = found
        self._pending.pop(milestone.key, None)
