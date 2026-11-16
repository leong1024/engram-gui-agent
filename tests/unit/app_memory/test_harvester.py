import os
import subprocess
import sys
from pathlib import Path

import pytest

from artemis.app_memory.abstraction.constants import SYSTEM_UI_PACKAGES
from artemis.app_memory.harvester import Harvester
from artemis.app_memory.models import SessionOutcome
from artemis.app_memory.outcomes import STALE_AFTER_SECONDS
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import TraceReader
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.traces import (
    MapView,
    Trace,
    flash_click,
    launch,
    tap,
    wait,
)

NOW = 10_000.0


def nav(tab: str) -> str:
    return f"clock:id/nav_{tab.lower()}"


@pytest.fixture
def trace(tmp_path: Path) -> Trace:
    return Trace(tmp_path)


@pytest.fixture
def harvest(trace: Trace):
    stores: list[MapStore] = []

    def open_harvester(clock: float = NOW) -> Harvester:
        store = MapStore.open(trace.root / "app_memory.db")
        stores.append(store)
        reader = TraceReader(trace.storage, trace.root)
        return Harvester(store, reader, SYSTEM_UI_PACKAGES, clock=lambda: clock)

    yield open_harvester
    for store in stores:
        store.close()


@pytest.fixture
def view(trace: Trace) -> MapView:
    return MapView(trace.root / "app_memory.db")


def five_step_session(trace: Trace, session_id: str = "s1", status: str = "running"):
    run = trace.session(session_id, status, pid=os.getpid())
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.clock("Timer"), flash_click(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"), tap(nav("Clock")))
    run.step(screens.clock("Clock"), tap(nav("Alarm")))
    run.step(screens.clock("Alarm"))
    return run


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


@pytest.mark.parametrize(
    ("status", "task_status", "expected", "counts"),
    [
        ("completed", None, ("completed", "confirmed"), (1, 0, 0)),
        ("success", None, ("completed", "confirmed"), (1, 0, 0)),
        ("completed", "partial", ("partial", "discounted"), (0, 1, 0)),
        ("failed", None, ("failed", "discounted"), (0, 1, 0)),
        ("cancelled", None, ("cancelled", "discounted"), (0, 1, 0)),
    ],
)
def test_the_outcome_confirms_or_discounts_the_whole_session(
    trace, harvest, view, status, task_status, expected, counts
):
    run = trace.session("s1", status, task_status=task_status)
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.clock("Timer"))
    harvester = harvest()
    harvester.harvest_live("s1")
    harvester.backfill("s1")

    outcome, observation_status = expected
    assert view.session("s1") == ("finalized", outcome)
    assert view.observations("s1") == [("s1-1", True, observation_status)]
    assert view.edges() == [(CLOCK, False, False, 1, *counts)]


def test_finalizing_sweeps_steps_the_live_path_missed(trace, harvest, view):
    run = five_step_session(trace)
    harvester = harvest()
    harvester.harvest_live("s1")
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.clock("Timer"))
    harvester.finalize("s1", SessionOutcome.COMPLETED)

    expected = [(f"s1-{n}", True, "confirmed") for n in (1, 2, 3, 4, 6)]
    assert view.observations("s1") == expected


def dead_pid() -> int:
    child = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"],
        text=True,
        capture_output=True,
        check=True,
    )
    return int(child.stdout)


@pytest.mark.parametrize(
    ("status", "pid", "started_at", "expected"),
    [
        ("completed", os.getpid(), NOW, ("finalized", "completed")),
        ("running", "dead", NOW, ("finalized", "failed")),
        ("running", os.getpid(), NOW - STALE_AFTER_SECONDS - 1, ("finalized", "failed")),
        ("running", os.getpid(), NOW, ("live", None)),
    ],
)
def test_reconcile_finalizes_sessions_that_ended_without_a_post_run(
    trace, harvest, view, status, pid, started_at, expected
):
    run = trace.session(
        "s1", status, pid=dead_pid() if pid == "dead" else pid, started_at=started_at
    )
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.clock("Timer"))
    harvest().harvest_live("s1")

    harvest().reconcile()

    assert view.session("s1") == expected


def test_backfilling_twice_leaves_the_database_identical(trace, harvest, view):
    five_step_session(trace, "s1", status="completed")
    crossing = trace.session("s2", "failed")
    crossing.step(screens.settings(), launch(CLOCK), package=SETTINGS)
    crossing.step(screens.clock("Alarm"), tap(nav("Alarm")))
    crossing.step(screens.clock("Alarm"))

    for session_id in ("s1", "s2"):
        harvest(clock=NOW).backfill(session_id)
    first = view.dump()
    for session_id in ("s1", "s2"):
        harvest(clock=NOW + 60).backfill(session_id)

    assert view.dump() == first
    assert view.session("s2") == ("finalized", "failed")
