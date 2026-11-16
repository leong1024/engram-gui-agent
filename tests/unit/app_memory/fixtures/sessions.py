import os

from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.traces import Trace, flash_click, tap

NOW = 10_000.0


def nav(tab: str) -> str:
    return f"clock:id/nav_{tab.lower()}"


def five_step_session(trace: Trace, session_id: str = "s1", status: str = "running"):
    run = trace.session(session_id, status, pid=os.getpid())
    run.step(screens.clock("Alarm"), tap(nav("Timer")))
    run.step(screens.clock("Timer"), flash_click(nav("Stopwatch")))
    run.step(screens.clock("Stopwatch"), tap(nav("Clock")))
    run.step(screens.clock("Clock"), tap(nav("Alarm")))
    run.step(screens.clock("Alarm"))
    return run
