import asyncio
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from artemis.app_memory.abstraction.constants import SYSTEM_UI_PACKAGES
from artemis.app_memory.enrichment import Enrichment, StoreJob, open_enrichment
from artemis.app_memory.guard import guarded
from artemis.app_memory.harvester import Harvester
from artemis.app_memory.interface import AppMemoryService, NoopAppMemory
from artemis.app_memory.launcher import installed_versions, launcher_package
from artemis.app_memory.map_graph_cache import MapGraphCache
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import ScreenObservation
from artemis.app_memory.navigator import Navigator, NavigatorFactory, open_navigator
from artemis.app_memory.outcomes import parse_outcome
from artemis.app_memory.routing import Route
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import TraceReader
from artemis.config.agent import AppMemoryConfig, load_agent_config
from third_party.mobile_use.utils.logger import get_logger

if TYPE_CHECKING:
    from artemis.data_engine.engine import DataEngine

logger = get_logger(__name__)

DB_FILE = "app_memory.db"
CLOSE_TIMEOUT_SECONDS = 10.0

T = TypeVar("T")


class AppMemory:
    """Harvests the steps a run records. All map work runs on one worker thread, which
    owns the store's SQLite connection, so the agent's own loop never waits on it."""

    def __init__(
        self,
        db_path: Path,
        reader: TraceReader,
        excluded: frozenset[str],
        engine: "DataEngine",
        enrichment: Enrichment | None = None,
        navigator: NavigatorFactory | None = None,
    ) -> None:
        self.disabled = False
        self._enrichment = enrichment
        self._open_navigator = navigator
        self._navigator: Navigator | None = None
        self._maps = MapGraphCache()
        self._installed: dict[str, int] = {}
        self._db_path = db_path
        self._reader = reader
        self._excluded = excluded
        self._engine = engine
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="app-memory")
        self._closed = False
        self._ended: dict[str, str] = {}
        self._store: MapStore | None = None
        self._harvester: Harvester | None = None

    @guarded
    def on_event(self, event_type: str, data: Any) -> None:
        session_id = str(data.get("session_id")) if isinstance(data, dict) else ""
        if session_id and event_type == "step_recorded":
            self.on_step_recorded(session_id)
        elif session_id and event_type == "session_ended":
            self._ended[session_id] = str(data.get("status"))

    @guarded
    def on_step_recorded(self, session_id: str) -> None:
        if not self._closed:
            self._executor.submit(self._harvest_live, session_id)

    async def prepare_run(self, *, device_serial: str | None) -> None:
        if self._enrichment is not None:
            self._enrichment.bind(asyncio.get_running_loop(), self._offload)
        await self._run(self._prepare, device_serial)
        if self._open_navigator is not None:
            self._navigator = self._open_navigator(self._read, self._maps, self._installed)

    @guarded
    def request_targets(self, goal: str, milestones: Sequence[Milestone]) -> None:
        if self._navigator is not None and not self._closed:
            self._navigator.request(goal, milestones)

    @guarded
    def route_for(self, milestone_key: str, observation: ScreenObservation) -> Route | None:
        return self._navigator.route_for(milestone_key, observation) if self._navigator else None

    async def finalize_session(self, session_id: str, outcome: str) -> None:
        await self._run(self._finalize, session_id, outcome)

    async def close(self) -> None:
        if self._closed:
            return
        self._engine.unsubscribe(self.on_event)
        try:
            await asyncio.wait_for(self._drain(), timeout=CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("App memory did not finish within the close timeout.")
        self._closed = True
        self._executor.shutdown(wait=False)

    async def _drain(self) -> None:
        if self._navigator is not None:
            await self._navigator.close()
        await self._engine.wait_for_writes()
        for session_id, outcome in self._ended.items():
            await self.finalize_session(session_id, outcome)
        if self._enrichment is not None:
            await self._enrichment.close()
        await self._run(self._close_store)

    async def _run(self, job: Callable[..., None], *args: Any) -> None:
        if not self._closed:
            await asyncio.wrap_future(self._executor.submit(job, *args))

    async def _read(self, job: Callable[[MapStore], T]) -> T:
        return await asyncio.wrap_future(self._executor.submit(lambda: job(self._open()[0])))

    def _open(self) -> tuple[MapStore, Harvester]:
        if self._store is None or self._harvester is None:
            self._store = MapStore.open(self._db_path)
            self._harvester = Harvester(self._store, self._reader, self._excluded)
        return self._store, self._harvester

    def _harvested(self, session_id: str | None = None) -> None:
        if self._store is None:
            return
        if session_id is not None:
            self._maps.refresh(self._store, session_id)
        if self._enrichment is not None:
            self._enrichment.queue(self._store)

    def _offload(self, job: StoreJob) -> None:
        if not self._closed:
            self._executor.submit(self._store_job, job)

    @guarded
    def _store_job(self, job: StoreJob) -> None:
        job(self._open()[0])

    @guarded
    def _prepare(self, device_serial: str | None) -> None:
        launcher = launcher_package(device_serial) if device_serial else None
        if launcher:
            self._excluded |= {launcher}
        self._installed = installed_versions(device_serial) if device_serial else {}
        self._open()[1].reconcile()
        self._harvested()

    @guarded
    def _harvest_live(self, session_id: str) -> None:
        self._open()[1].harvest_live(session_id)
        self._harvested(session_id)

    @guarded
    def _finalize(self, session_id: str, status: str) -> None:
        session = self._reader.session(session_id)
        outcome = parse_outcome(status, session.run_task_status if session else None)
        self._open()[1].finalize(session_id, outcome)
        self._harvested(session_id)

    @guarded
    def _close_store(self) -> None:
        if self._store is not None:
            self._store.close()
        self._store = self._harvester = None


def excluded_packages(config: AppMemoryConfig) -> frozenset[str]:
    return SYSTEM_UI_PACKAGES | frozenset(config.harvest.exclude_packages)


def open_app_memory(engine: "DataEngine | None") -> AppMemoryService:
    try:
        config = load_agent_config().app_memory
    except ValueError as exc:
        logger.warning(f"App memory is off: the agent config did not load ({exc}).")
        return NoopAppMemory()
    if engine is None or not (config.enabled and config.harvest.enabled):
        return NoopAppMemory()
    reader = TraceReader(engine.storage, engine.global_base_dir)
    enrichment = open_enrichment(engine.ctx, config, engine.get_image_path)
    db_path = engine.global_base_dir / DB_FILE
    navigator = open_navigator(engine.ctx, config)
    memory = AppMemory(db_path, reader, excluded_packages(config), engine, enrichment, navigator)
    engine.subscribe(memory.on_event)
    return memory
