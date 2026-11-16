import asyncio
import os
from collections.abc import Callable, Mapping
from typing import Any

import pytest

from artemis.app_memory import ids
from artemis.app_memory.abstraction import abstract
from artemis.app_memory.graph_store import GraphStore
from artemis.app_memory.map_graph_cache import MapGraphCache
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import MapId, ScreenObservation, StateId
from artemis.app_memory.navigator import Navigator
from artemis.app_memory.retrieval import TargetResolution
from artemis.app_memory.routing import Route, RouteKind
from artemis.app_memory.service import DB_FILE, AppMemory
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import TraceReader
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.maps import SETTINGS_MAP, MapBuilder, page, tap
from tests.unit.app_memory.fixtures.parts import CLOCK
from tests.unit.app_memory.fixtures.sessions import nav
from tests.unit.app_memory.fixtures.traces import tap as trace_tap

MILESTONES = [Milestone(key, f"Open {key}") for key in ("Menu", "Sound", "Display")]


class FixedTargets:
    """Resolves each milestone to the state its key names."""

    def __init__(self, targets: Mapping[str, tuple[MapId, StateId]]) -> None:
        self._targets = targets

    async def resolve(self, goal: str, milestone: Milestone, installed: Any) -> TargetResolution:
        map_id, state_id = self._targets[milestone.key]
        return TargetResolution(milestone.key, state_id, map_id, False, 1.0, "fixed")


RouteFor = Callable[[str, ScreenObservation], Route | None]


async def routes(route_for: RouteFor, keys: list[str], screen: ScreenObservation) -> list[Route]:
    for _ in range(200):
        found = [route_for(key, screen) for key in keys]
        if all(found):
            return [route for route in found if route is not None]
        await asyncio.sleep(0.01)
    raise AssertionError("no route in time")


@pytest.fixture
def settings_map(tmp_path) -> tuple[MapStore, dict[str, tuple[MapId, StateId]]]:
    build = MapBuilder.open(tmp_path / DB_FILE)
    home, *ends = (build.state(name) for name in ("Home", "Menu", "Sound", "Display"))
    for end, milestone in zip(ends, MILESTONES, strict=True):
        build.edge(home, end, tap(milestone.key))
    return build.store, {m.key: (SETTINGS_MAP, end) for m, end in zip(MILESTONES, ends)}


@pytest.mark.asyncio
async def test_milestones_in_one_map_share_one_loaded_map(settings_map, monkeypatch):
    store, targets = settings_map
    loads: list[MapId] = []
    load = GraphStore.map_graph
    monkeypatch.setattr(GraphStore, "map_graph", lambda graph, m: loads.append(m) or load(graph, m))

    async def read(job: Callable[[MapStore], Any]) -> Any:
        return job(store)

    navigator = Navigator(FixedTargets(targets), read, MapGraphCache(), {})
    navigator.request("goal", MILESTONES)
    found = await routes(navigator.route_for, list(targets), page("Home"))
    await navigator.close()
    store.close()

    assert loads == [SETTINGS_MAP]
    assert [route.hops[0].to_state.title for route in found] == ["Menu", "Sound", "Display"]


@pytest.mark.asyncio
async def test_route_for_reads_no_database(settings_map):
    store, targets = settings_map

    async def read(job: Callable[[MapStore], Any]) -> Any:
        return job(store)

    navigator = Navigator(FixedTargets(targets), read, MapGraphCache(), {})
    navigator.request("goal", MILESTONES)
    await routes(navigator.route_for, list(targets), page("Home"))
    store.close()
    with pytest.raises(Exception, match="closed database"):
        store.graph.maps()

    for screen in ("Home", "Sound", "Wifi", "Display"):
        assert navigator.route_for("Display", page(screen)) is not None
    await navigator.close()


class QuietEngine:
    def unsubscribe(self, callback: Callable[..., None]) -> None:
        pass

    async def wait_for_writes(self) -> None:
        pass


def clock_tab(name: str) -> ScreenObservation:
    return ScreenObservation(CLOCK, ".Main", 1, tuple(screens.clock(name)))


@pytest.mark.asyncio
async def test_route_for_routes_from_a_screen_harvested_after_the_target_was_found(trace):
    clock_map = MapId(CLOCK, 1)
    stopwatch = ids.state_id(clock_map, abstract(clock_tab("Stopwatch")).coarse_key)
    run = trace.session("s1", "running", pid=os.getpid())
    run.step(screens.clock("Alarm"), trace_tap(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"))
    reader = TraceReader(trace.storage, trace.root)
    retriever = FixedTargets({"stopwatch": (clock_map, stopwatch)})

    def navigator(read, maps, installed) -> Navigator:
        return Navigator(retriever, read, maps, installed)

    memory = AppMemory(trace.root / DB_FILE, reader, frozenset(), QuietEngine(), None, navigator)
    await memory.prepare_run(device_serial=None)
    memory.on_step_recorded("s1")
    memory.request_targets("goal", [Milestone("stopwatch", "Open the stopwatch")])
    first = await routes(memory.route_for, ["stopwatch"], clock_tab("Timer"))

    run.step(screens.clock("Stopwatch"), trace_tap(nav("Timer")))
    run.step(screens.clock("Timer"), trace_tap(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"))
    memory.on_step_recorded("s1")
    for _ in range(200):
        later = memory.route_for("stopwatch", clock_tab("Timer"))
        if later is not None and later.kind is RouteKind.FROM_STATE:
            break
        await asyncio.sleep(0.01)
    await memory.close()

    assert first[0].kind is RouteKind.NO_PATH
    assert later is not None and [hop.to_state.state_id for hop in later.hops] == [stopwatch]
