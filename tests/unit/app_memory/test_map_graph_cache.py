import os
from collections.abc import Iterator

import pytest

from artemis.app_memory.map_graph_cache import MapGraphCache
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import MapId, ScreenObservation, SessionOutcome, StateId
from artemis.app_memory.routing import RouteKind, RoutePlanner, RouteTracker, RoutingMap, locate
from artemis.app_memory.routing.types import HintNote, Route
from artemis.app_memory.store import MapStore
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.sessions import nav
from tests.unit.app_memory.fixtures.traces import launch, tap

CLOCK_MAP = MapId(CLOCK, 1)
MILESTONE = Milestone("m1", "Open the stopwatch")


def tab(name: str) -> ScreenObservation:
    return ScreenObservation(CLOCK, ".Main", 1, tuple(screens.clock(name)))


def state(routing_map: RoutingMap, name: str) -> StateId:
    return locate(tab(name), routing_map.graph, routing_map.graph.outside).state_id


def path(route: Route | None) -> list[StateId]:
    assert route is not None
    return [route.source.state_id, *(hop.to_state.state_id for hop in route.hops)]


@pytest.fixture
def store(trace) -> Iterator[MapStore]:
    reader = MapStore.open(trace.root / "app_memory.db")
    yield reader
    reader.close()


@pytest.fixture
def run(trace):
    script = trace.session("s1", "running", pid=os.getpid())
    script.step(screens.clock("Alarm"), tap(nav("Timer")))
    script.step(screens.clock("Timer"), tap(nav("Stopwatch")))
    script.step(screens.clock("Stopwatch"))
    return script


def test_a_screen_harvested_after_the_load_is_located_and_routed_after_refresh(run, harvest, store):
    harvester, maps = harvest(), MapGraphCache()
    harvester.harvest_live("s1")
    loaded = maps.load(store, CLOCK_MAP)
    assert state(loaded, "Clock") == loaded.graph.outside

    run.step(screens.clock("Stopwatch"), tap(nav("Clock")))
    run.step(screens.clock("Clock"))
    harvester.harvest_live("s1")
    maps.refresh(store, "s1")
    current = maps.get(CLOCK_MAP)
    assert current is not None and current.graph == store.graph.map_graph(CLOCK_MAP)
    clock = state(current, "Clock")
    assert clock != current.graph.outside

    planner = RoutePlanner(MILESTONE, clock, borrowed=False)
    route = planner.route(planner.locate(tab("Alarm"), current), current)
    assert (route.kind, len(route.hops)) == (RouteKind.FROM_STATE, 3)

    harvester.finalize("s1", SessionOutcome.COMPLETED)
    maps.refresh(store, "s1")
    settled = maps.get(CLOCK_MAP)
    assert settled is not None and settled.graph == store.graph.map_graph(CLOCK_MAP)


def test_an_unchanged_map_is_not_rebuilt(trace, run, harvest, store):
    harvester, maps = harvest(), MapGraphCache()
    harvester.harvest_live("s1")
    loaded = maps.load(store, CLOCK_MAP)
    maps.refresh(store, "s1")
    refreshed = maps.get(CLOCK_MAP)

    maps.refresh(store, "s1")
    other = trace.session("s2", "running", pid=os.getpid())
    other.step(screens.settings(), launch(CLOCK), package=SETTINGS)
    other.step(screens.settings("bottom"), package=SETTINGS)
    harvester.harvest_live("s2")
    assert set(store.graph.session_marks("s2")) == {MapId(SETTINGS, 1)}
    maps.refresh(store, "s2")

    assert maps.load(store, CLOCK_MAP) is maps.get(CLOCK_MAP) is refreshed
    assert refreshed is not None and refreshed.graph == loaded.graph


def test_a_route_in_flight_survives_a_swap(run, harvest, store):
    harvester, maps = harvest(), MapGraphCache()
    harvester.harvest_live("s1")
    before = maps.load(store, CLOCK_MAP)
    stopwatch = state(before, "Stopwatch")
    tracker = RouteTracker(RoutePlanner(MILESTONE, stopwatch, borrowed=False))
    first = tracker.step(tab("Alarm"), before)

    run.step(screens.clock("Stopwatch"), tap(nav("Clock")))
    run.step(screens.clock("Clock"), tap(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"))
    harvester.harvest_live("s1")
    maps.refresh(store, "s1")
    after = maps.get(CLOCK_MAP)
    assert after is not None and after is not before

    ahead = tracker.step(tab("Timer"), after)
    assert path(ahead) == path(first)[1:] and ahead is not None and ahead.notes == ()
    rerouted = tracker.step(tab("Clock"), after)
    assert path(rerouted) == [state(after, "Clock"), stopwatch]
    assert rerouted is not None and rerouted.notes == (HintNote.REROUTED,)
