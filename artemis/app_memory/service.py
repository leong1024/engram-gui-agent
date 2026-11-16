import asyncio
import functools
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar

from artemis.app_memory.abstraction.constants import SYSTEM_UI_PACKAGES
from artemis.app_memory.harvester import Harvester
from artemis.app_memory.interface import AppMemoryService, NoopAppMemory
from artemis.app_memory.launcher import launcher_package
from artemis.app_memory.outcomes import parse_outcome
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import TraceReader
from artemis.config.agent import AppMemoryConfig, load_agent_config
from third_party.mobile_use.utils.logger import get_logger

if TYPE_CHECKING:
    from artemis.data_engine.engine import DataEngine

logger = get_logger(__name__)

DB_FILE = "app_memory.db"
CLOSE_TIMEOUT_SECONDS = 10.0

P = ParamSpec("P")
R = TypeVar("R")


def guarded(
    method: Callable[Concatenate["AppMemory", P], R],
) -> Callable[Concatenate["AppMemory", P], R | None]:
    """App memory never raises into the agent: log, and stop after a database error."""

    @functools.wraps(method)
    def run(self: "AppMemory", *args: P.args, **kwargs: P.kwargs) -> R | None:
        if self.disabled:
            return None
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            logger.warning(f"App memory {method.__name__}{args} failed: {exc!r}", exc_info=True)
            if isinstance(exc, sqlite3.DatabaseError):
                self.disabled = True
                logger.warning("App memory is disabled for the rest of this run.")
            return None

    return run


class AppMemory:
    """Harvests the steps a run records. All map work runs on one worker thread, which
    owns the store's SQLite connection, so the agent's own loop never waits on it."""

    def __init__(
        self, db_path: Path, reader: TraceReader, excluded: frozenset[str], engine: "DataEngine"
    ) -> None:
        self.disabled = False
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
        await self._run(self._prepare, device_serial)

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
        await self._engine.wait_for_writes()
        for session_id, outcome in self._ended.items():
            await self.finalize_session(session_id, outcome)
        await self._run(self._close_store)

    async def _run(self, job: Callable[..., None], *args: Any) -> None:
        if not self._closed:
            await asyncio.wrap_future(self._executor.submit(job, *args))

    def _harvester_for_run(self) -> Harvester:
        if self._harvester is None:
            self._store = MapStore.open(self._db_path)
            self._harvester = Harvester(self._store, self._reader, self._excluded)
        return self._harvester

    @guarded
    def _prepare(self, device_serial: str | None) -> None:
        launcher = launcher_package(device_serial) if device_serial else None
        if launcher:
            self._excluded |= {launcher}
        self._harvester_for_run().reconcile()

    @guarded
    def _harvest_live(self, session_id: str) -> None:
        self._harvester_for_run().harvest_live(session_id)

    @guarded
    def _finalize(self, session_id: str, status: str) -> None:
        session = self._reader.session(session_id)
        outcome = parse_outcome(status, session.run_task_status if session else None)
        self._harvester_for_run().finalize(session_id, outcome)

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
    memory = AppMemory(engine.global_base_dir / DB_FILE, reader, excluded_packages(config), engine)
    engine.subscribe(memory.on_event)
    return memory
