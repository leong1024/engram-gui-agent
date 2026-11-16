import os

import pytest

from artemis.app_memory.abstraction.constants import SYSTEM_UI_PACKAGES
from artemis.app_memory.harvester import Harvester
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import TraceReader

from artemis.app_memory.models import SessionOutcome
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.sessions import NOW, five_step_session, nav
from tests.unit.app_memory.fixtures.traces import (
    MapView,
    Trace,
    flash_click,
    launch,
    tap,
    wait,
)


def test_a_scripted_session_becomes_provisional_states_and_edges(trace, harvest, view):
    five_step_session(trace)
    harvest().harvest_live("s1")

    assert view.state_count(CLOCK) == 4
    assert view.edges() == [(CLOCK, False, False, 1, 0, 0, 1)] * 4
    assert view.observations("s1") == [(f"s1-{n}", True, "provisional") for n in range(1, 5)]
    assert view.session("s1") == ("live", None)


def test_harvesting_step_by_step_matches_one_sweep(tmp_path):
    live = Trace(tmp_path / "live")
    run = live.session("s1", "running", pid=os.getpid())
    store = MapStore.open(live.root / "app_memory.db")
    harvester = Harvester(store, TraceReader(live.storage, live.root), SYSTEM_UI_PACKAGES)
    for tab, target in [("Alarm", "Timer"), ("Timer", "Stopwatch"), ("Stopwatch", None)]:
        run.step(screens.clock(tab), *([tap(nav(target))] if target else []))
        harvester.harvest_live("s1")
    store.close()

    swept = Trace(tmp_path / "swept")
    run = swept.session("s1", "running", pid=os.getpid())
    for tab, target in [("Alarm", "Timer"), ("Timer", "Stopwatch"), ("Stopwatch", None)]:
        run.step(screens.clock(tab), *([tap(nav(target))] if target else []))
    store = MapStore.open(swept.root / "app_memory.db")
    Harvester(store, TraceReader(swept.storage, swept.root), SYSTEM_UI_PACKAGES).harvest_live("s1")
    store.close()

    assert (
        MapView(live.root / "app_memory.db").dump() == MapView(swept.root / "app_memory.db").dump()
    )


def test_a_wait_merges_into_the_previous_edge(trace, harvest, view):
    run = trace.session("s1")
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.flutter_canvas(), wait())
    run.step(screens.clock("Timer"), tap(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"))
    harvest().harvest_live("s1")

    assert view.state_count(CLOCK) == 3
    assert view.edges() == [(CLOCK, False, False, 1, 0, 0, 1)] * 2
    assert view.observations("s1") == [("s1-1", True, "provisional"), ("s1-3", True, "provisional")]


def test_a_burst_becomes_one_macro_edge(trace, harvest, view):
    run = trace.session("s1")
    run.step(screens.clock("Alarm"), tap(nav("Timer")), tap(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"))
    harvest().harvest_live("s1")

    assert view.state_count(CLOCK) == 2
    assert view.edges() == [(CLOCK, False, False, 2, 0, 0, 1)]


def test_an_action_that_changes_nothing_records_no_edge(trace, harvest, view):
    run = trace.session("s1")
    run.step(screens.clock("Alarm"), tap(nav("Alarm")))
    run.step(screens.clock("Alarm"))
    harvest().harvest_live("s1")

    assert view.edges() == []
    assert view.observations("s1") == [("s1-1", False, "provisional")]


@pytest.mark.parametrize("status", ["failed", None])
def test_a_step_whose_action_did_not_run_contributes_nothing(trace, harvest, view, status):
    run = trace.session("s1")
    run.step(screens.clock("Alarm"), tap(nav("Timer")), status=status)
    run.step(screens.clock("Timer"))
    harvest().harvest_live("s1")

    assert view.observations("s1") == []


def test_launching_another_app_splits_into_leave_and_entry_edges(trace, harvest, view):
    run = trace.session("s1")
    run.step(screens.settings(), launch(CLOCK), package=SETTINGS)
    run.step(screens.clock("Alarm"))
    harvest().harvest_live("s1")

    assert view.edges() == [
        (SETTINGS, False, True, 1, 0, 0, 1),
        (CLOCK, True, False, 1, 0, 0, 1),
    ]


def test_tapping_into_another_app_records_only_the_leave_edge(trace, harvest, view):
    run = trace.session("s1")
    run.step(screens.settings(), tap("app:id/row"), package=SETTINGS)
    run.step(screens.clock("Alarm"))
    harvest().harvest_live("s1")

    assert view.edges() == [(SETTINGS, False, True, 1, 0, 0, 1)]
    assert view.state_count(CLOCK) == 0


def test_steps_in_an_excluded_package_open_nothing(trace, harvest, view):
    run = trace.session("s1")
    run.step(screens.clock("Alarm"), tap(nav("Timer")), package="com.android.systemui")
    run.step(screens.clock("Timer"))
    harvest().harvest_live("s1")

    assert view.observations("s1") == []
