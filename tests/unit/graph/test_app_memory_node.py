from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.tools import StructuredTool

from artemis.app_memory import plan_routes
from artemis.app_memory.interface import NoopAppMemory
from artemis.app_memory.milestones import Milestone
from artemis.context import ArtemisContext, DeviceContext, DevicePlatform, ExecutionSetup
from artemis.data_engine.engine import DataEngine
from artemis.graph.app_memory_targets import APP_MEMORY_NODE, app_memory_targets_node
from artemis.graph.graph import get_graph, wrap_update_note_tool
from artemis.graph.state import State
from artemis.utils.notes import get_note_file_path
from tests.unit.conftest import HINTS_ON
from third_party.mobile_use.graph import CONVERGENCE_NODE

GOAL = "Turn on dark theme, then play a song"
PLAN = "- [ ] Open Display settings\n  - [ ] Find Dark theme\n- [ ] Open YouTube\n"


class RecordingMemory(NoopAppMemory):
    def __init__(self) -> None:
        self.requests: list[tuple[str, list[tuple[str, ...]]]] = []

    def request_targets(self, goal: str, milestones: Sequence[Milestone]) -> None:
        self.requests.append((goal, [(m.text, *m.details) for m in milestones]))


def context(tmp_path: Path) -> ArtemisContext:
    device = DeviceContext(
        host_platform="LINUX",
        mobile_platform=DevicePlatform.ANDROID,
        device_id="",
        device_width=1080,
        device_height=2400,
    )
    setup = ExecutionSetup(traces_path=tmp_path, disable_planner_validation=True)
    ctx = ArtemisContext(device=device, execution_setup=setup)
    ctx.data_engine = DataEngine(ctx)
    ctx.data_engine.start_session(goal=GOAL)
    ctx.app_memory = RecordingMemory()
    return ctx


def write_plan(ctx: ArtemisContext, plan: str) -> Path:
    assert ctx.data_engine is not None
    path = get_note_file_path(ctx.data_engine.base_dir, "task_plan")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan, encoding="utf-8")
    return path


async def edges(ctx: ArtemisContext) -> set[tuple[str, str]]:
    graph = (await get_graph(ctx)).get_graph()
    return {(edge.source, edge.target) for edge in graph.edges}


@pytest.mark.asyncio
async def test_the_planner_hands_over_through_app_memory_only_when_hints_are_on(
    tmp_path, monkeypatch
):
    ctx = context(tmp_path)
    hints_off = await edges(ctx)
    monkeypatch.setattr(plan_routes, "load_agent_config", lambda: HINTS_ON)
    hints_on = await edges(ctx)

    detour = {("planner", APP_MEMORY_NODE), (APP_MEMORY_NODE, CONVERGENCE_NODE)}
    assert detour <= hints_on
    assert ("planner", CONVERGENCE_NODE) not in hints_on
    assert hints_off == (hints_on - detour) | {("planner", CONVERGENCE_NODE)}


@pytest.mark.asyncio
async def test_the_node_requests_targets_for_the_top_level_milestones(tmp_path):
    ctx = context(tmp_path)
    write_plan(ctx, PLAN)

    assert await app_memory_targets_node(State.initial(GOAL), ctx) == {}
    assert ctx.app_memory.requests == [
        (GOAL, [("Open Display settings", "Find Dark theme"), ("Open YouTube",)])
    ]


@pytest.mark.asyncio
async def test_the_node_requests_nothing_before_a_plan_exists(tmp_path):
    ctx = context(tmp_path)

    await app_memory_targets_node(State.initial(GOAL), ctx)

    assert ctx.app_memory.requests == []


async def update_plan(ctx: ArtemisContext, target: str, replacement: str) -> None:
    path = write_plan(ctx, PLAN)

    async def apply(tool, args, tool_call_id, state, record_trace=None):
        path.write_text(path.read_text().replace(args["target"], args["replacement"]))
        return "Success"

    noop = StructuredTool.from_function(lambda **kwargs: None, name="update_note", description="")
    with patch("artemis.graph.graph.invoke_tool_with_injection", side_effect=apply):
        await wrap_update_note_tool(ctx, noop).ainvoke(
            {"key": "task_plan", "target": target, "replacement": replacement}
        )


@pytest.mark.asyncio
async def test_an_accepted_plan_write_requests_the_new_plan(tmp_path, hints_on):
    ctx = context(tmp_path)

    await update_plan(ctx, "- [ ] Open YouTube\n", "- [ ] Open YouTube\n- [ ] Play a song\n")

    assert [milestones for _, milestones in ctx.app_memory.requests] == [
        [("Open Display settings", "Find Dark theme"), ("Open YouTube",), ("Play a song",)]
    ]


@pytest.mark.asyncio
async def test_a_rejected_plan_write_requests_nothing(tmp_path, hints_on):
    ctx = context(tmp_path)

    await update_plan(ctx, PLAN, PLAN.replace("- [ ] Open", "- [x] Open"))

    assert ctx.app_memory.requests == []


@pytest.mark.asyncio
async def test_a_plan_write_requests_nothing_with_hints_off(tmp_path):
    ctx = context(tmp_path)

    await update_plan(ctx, "- [ ] Open YouTube", "- [x] Open YouTube")

    assert ctx.app_memory.requests == []
