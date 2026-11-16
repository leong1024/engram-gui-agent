import os
import subprocess
import sys

import pytest

from artemis.app_memory.models import SessionOutcome
from artemis.app_memory.outcomes import STALE_AFTER_SECONDS
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.sessions import NOW, five_step_session, nav
from tests.unit.app_memory.fixtures.traces import launch, tap


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
