import json
from pathlib import Path
from typing import Any

import pytest

from artemis.app_memory import plan_routes, service
from artemis.app_memory.harvester import Harvester
from artemis.app_memory.interface import NoopAppMemory
from artemis.config.agent import AgentGlobalConfig
from artemis.context import ArtemisContext, DeviceContext, ExecutionSetup
from artemis.data_engine.engine import DataEngine
from tests.unit.app_memory.fixtures import screens
from tests.unit.app_memory.fixtures.pro_run import MILESTONE, pro_run, script_pro_run
from tests.unit.app_memory.fixtures.traces import MapView, tap
from tests.unit.conftest import HINTS_OFF, HINTS_ON

TABS = ("Alarm", "Timer", "Stopwatch")


def context_for(traces: Path) -> ArtemisContext:
    device = DeviceContext(host_platform="LINUX", device_id="")
    ctx = ArtemisContext(device=device, execution_setup=ExecutionSetup(traces_path=traces))
    ctx.data_engine = DataEngine(ctx)
    return ctx


async def scripted_run(ctx: ArtemisContext, *, open_memory: bool = True) -> tuple[str, int]:
    engine = ctx.data_engine
    assert engine is not None
    session_id = str(engine.start_session(goal="Open the stopwatch"))
    if open_memory:
        ctx.app_memory = service.open_app_memory(engine)
    await ctx.app_memory.prepare_run(device_serial=None)
    async with ctx:
        for index, tab in enumerate(TABS):
            following = TABS[index + 1 : index + 2]
            step_id = engine.record_step(
                pre_screenshot_bytes=json.dumps(tab).encode(),
                ui_tree=screens.clock(tab),
                action_taken=[tap(f"clock:id/nav_{following[0].lower()}")] if following else [],
            )
            await engine.wait_for_writes()
            engine.update_step_execution_result(step_id, {"status": "dispatched"})
        engine.end_session("completed")
    session = engine.storage.get_session(session_id)
    assert session is not None
    return session.status, len(engine.storage.get_steps(session_id))


@pytest.mark.asyncio
async def test_a_run_is_finalized_when_its_context_exits(tmp_path):
    ctx = context_for(tmp_path)
    await scripted_run(ctx)

    session_id = str(ctx.data_engine.current_session_id)
    view = MapView(tmp_path / service.DB_FILE)
    assert view.session(session_id) == ("finalized", "completed")
    assert [status for _, _, status in view.observations(session_id)] == ["confirmed"] * 2


def explode(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError("harvester exploded")


@pytest.mark.asyncio
async def test_a_failing_harvester_never_changes_the_task_result(tmp_path, monkeypatch):
    for name in ("harvest_live", "finalize", "reconcile", "backfill"):
        monkeypatch.setattr(Harvester, name, explode)

    with_failing_memory = await scripted_run(context_for(tmp_path / "failing"))
    without_memory = await scripted_run(context_for(tmp_path / "off"), open_memory=False)

    assert with_failing_memory == without_memory == ("completed", 3)


@pytest.mark.asyncio
async def test_a_corrupt_map_database_turns_app_memory_off_for_the_run(tmp_path):
    (tmp_path / service.DB_FILE).write_bytes(b"not a sqlite database" * 100)
    ctx = context_for(tmp_path)

    assert await scripted_run(ctx) == ("completed", 3)
    assert ctx.app_memory.disabled


@pytest.mark.parametrize("block", [{"enabled": False}, {"harvest": {"enabled": False}}])
def test_switched_off_app_memory_writes_nothing(tmp_path, monkeypatch, block):
    config = AgentGlobalConfig.model_validate({"app_memory": block})
    monkeypatch.setattr(service, "load_agent_config", lambda: config)
    ctx = context_for(tmp_path)

    assert isinstance(service.open_app_memory(ctx.data_engine), NoopAppMemory)
    assert not (tmp_path / service.DB_FILE).exists()


class RaisingNavigator:
    """Fails every hint call, and counts them so the test knows the faults were reached."""

    def __init__(self) -> None:
        self.calls = 0

    def request(self, goal: str, milestones: Any) -> None:
        self.calls += 1
        raise RuntimeError("retrieval exploded")

    def route_for(self, milestone_key: str, observation: Any) -> None:
        self.calls += 1
        raise RuntimeError("routing exploded")

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_a_pro_run_with_failing_app_memory_ends_as_one_without_it(tmp_path, monkeypatch):
    script_pro_run(monkeypatch)
    for name in ("harvest_live", "finalize", "reconcile"):
        monkeypatch.setattr(Harvester, name, explode)
    navigator = RaisingNavigator()
    monkeypatch.setattr(service, "open_navigator", lambda *args: lambda *a: navigator)
    monkeypatch.setattr(plan_routes, "load_agent_config", lambda: HINTS_ON)

    failing = context_for(tmp_path / "failing")
    failing.app_memory = service.open_app_memory(failing.data_engine)
    with_failing_memory = await pro_run(failing)
    monkeypatch.setattr(plan_routes, "load_agent_config", lambda: HINTS_OFF)
    without_memory = await pro_run(context_for(tmp_path / "off"))

    assert with_failing_memory == without_memory == (f"- [x] {MILESTONE}\n", 1)
    assert navigator.calls >= 3
