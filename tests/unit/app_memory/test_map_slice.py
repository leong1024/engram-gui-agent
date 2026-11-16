import os
from collections.abc import Iterator

import pytest

from artemis.app_memory.models import MapId, SessionOutcome
from artemis.app_memory.store import MapStore
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.sessions import nav
from tests.unit.app_memory.fixtures.traces import launch, tap

CLOCK_MAP = MapId(CLOCK, 1)


@pytest.fixture
def store(trace) -> Iterator[MapStore]:
    reader = MapStore.open(trace.root / "app_memory.db")
    yield reader
    reader.close()


def test_a_loaded_map_merged_with_a_sessions_slice_equals_a_fresh_load(trace, harvest, store):
    earlier = trace.session("s0")
    earlier.step(screens.clock("Alarm"), tap(nav("Timer")))
    earlier.step(screens.clock("Timer"))
    run = trace.session("s1", "running", pid=os.getpid())
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.clock("Timer"))
    harvester = harvest()
    harvester.finalize("s0", SessionOutcome.COMPLETED)
    harvester.harvest_live("s1")
    loaded = store.graph.map_graph(CLOCK_MAP)

    run.step(screens.clock("Timer"), tap(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"))
    harvester.harvest_live("s1")
    live = loaded.merged(store.graph.session_slice(CLOCK_MAP, "s1"))
    assert live == store.graph.map_graph(CLOCK_MAP)
    assert len(live.known) == len(loaded.known) + 1

    harvester.finalize("s1", SessionOutcome.FAILED)
    settled = live.merged(store.graph.session_slice(CLOCK_MAP, "s1"))
    assert settled == store.graph.map_graph(CLOCK_MAP)
    assert settled.tallies != live.tallies


def test_session_marks_move_with_each_write_and_only_in_the_maps_written(trace, harvest, store):
    run = trace.session("s1", "running", pid=os.getpid())
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.clock("Timer"), launch(SETTINGS))
    run.step(screens.settings(), package=SETTINGS)
    harvester = harvest()
    harvester.harvest_live("s1")
    marks = store.graph.session_marks
    first = marks("s1")

    run.step(screens.clock("Timer"), tap(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"))
    harvester.harvest_live("s1")
    second = marks("s1")
    harvester.finalize("s1", SessionOutcome.COMPLETED)

    assert CLOCK_MAP in first and len(first) == 2
    assert second[CLOCK_MAP] != first[CLOCK_MAP]
    assert {k: v for k, v in second.items() if k != CLOCK_MAP} == {
        k: v for k, v in first.items() if k != CLOCK_MAP
    }
    assert all(mark.provisional == 0 for mark in marks("s1").values())
    assert marks("nobody") == {}
