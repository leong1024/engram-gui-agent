import asyncio
import base64
import hashlib
import io
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, BaseMessage
from PIL import Image

from artemis.agents.operator.prompts import (
    AppMemoryRoutePromptComponent,
    ObservationPromptComponent,
    PromptBuilder,
    PromptComponent,
)
from artemis.app_memory.hints import HEADER
from artemis.app_memory.map_graph_cache import MapGraphCache
from artemis.app_memory.milestones import Milestone, plan_milestones
from artemis.app_memory.navigator import Navigator
from artemis.app_memory.retrieval import TargetResolution
from artemis.app_memory.service import DB_FILE
from artemis.app_memory.store import MapStore
from artemis.context import ArtemisContext, DeviceContext, ExecutionSetup
from artemis.data_engine.engine import DataEngine
from artemis.graph.state import State
from artemis.memory.transcript import EPHEMERAL_BLOCKS_KEY, TranscriptLedger
from artemis.utils.plan_grammar import parse_plan
from tests.unit.app_memory.fixtures.maps import SETTINGS_MAP, MapBuilder, page, tap

PLAN = "- [/] Open Display\n- [ ] Open Sound\n"
MILESTONES = plan_milestones(parse_plan(PLAN))
DISPLAY = MILESTONES[0].key
GOLDEN = (
    "--- App Memory: Known Route (advisory) ---\n"
    "Milestone: Open Display\n"
    'Target screen: "Display" (com.android.settings v34) — Brightness and theme.\n'
    "Seen 1 time. Route confidence 0.67.\n"
    'From the current screen ("Home"):\n'
    '  1. Tap "Display" → target reached\n'
    "Check that each screen matches before taking the next hop. If the screen does not match,\n"
    "ignore this route and continue normally."
)


class GatedTarget:
    """Finds the Display page once `done` is set, the way a slow selector would."""

    def __init__(self, target: TargetResolution) -> None:
        self.done = asyncio.Event()
        self._target = target

    async def resolve(self, goal: str, milestone: Milestone, installed: Any) -> TargetResolution:
        await self.done.wait()
        return self._target


@pytest.fixture
def screenshot() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 128), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest_asyncio.fixture
async def memory(tmp_path):
    build = MapBuilder.open(tmp_path / DB_FILE)
    home, display = build.state("Home"), build.state("Display", "Brightness and theme.")
    build.edge(home, display, tap("Display"))
    target = GatedTarget(TargetResolution(DISPLAY, display, SETTINGS_MAP, False, 1.0, "fixed"))

    async def read(job: Callable[[MapStore], Any]) -> Any:
        return job(build.store)

    navigator = Navigator(target, read, MapGraphCache(), {})
    navigator.request("Turn on dark theme", MILESTONES)
    yield navigator, target.done
    await navigator.close()
    build.store.close()


@pytest.fixture
def ctx(tmp_path, memory, screenshot) -> ArtemisContext:
    device = DeviceContext(host_platform="LINUX", device_id="")
    context = ArtemisContext(device=device, execution_setup=ExecutionSetup(traces_path=tmp_path))
    context.data_engine = DataEngine(context)
    context.app_memory = memory[0]
    name = hashlib.sha256(screenshot).hexdigest()
    seen = SimpleNamespace(activity=".Home", ui_backend=None)
    context.data_engine.note_observed_screen(name, seen, list(page("Home").elements))
    return context


def on_home(screenshot: bytes) -> State:
    perception = {
        "screenshot_b64": base64.b64encode(screenshot).decode(),
        "xml_hierarchy": list(page("Home").elements),
        "width": 1080,
        "height": 2400,
    }
    return State(initial_goal="Turn on dark theme", operator_raw_data=perception)


async def observation(
    ctx: ArtemisContext, state: State, plan: str = PLAN, *components: PromptComponent
) -> BaseMessage:
    builder = PromptBuilder()
    for component in (*components, AppMemoryRoutePromptComponent()):
        screenshot = state.operator_raw_data["screenshot_b64"] if state.operator_raw_data else ""
        await component(
            builder, state, ctx, task_plan=plan, latest_screenshot_b64=screenshot, minimal_list=""
        )
    return builder.build()[1]


def text(message: BaseMessage) -> str:
    return "\n".join(block["text"] for block in message.content if isinstance(block, dict))


async def route_ready(ctx: ArtemisContext, state: State) -> BaseMessage:
    for _ in range(200):
        message = await observation(ctx, state)
        if message.content:
            return message
        await asyncio.sleep(0.01)
    raise AssertionError("no route in time")


@pytest.mark.asyncio
async def test_the_route_block_is_golden_and_ephemeral(ctx, memory, screenshot, hints_on):
    memory[1].set()

    message = await route_ready(ctx, on_home(screenshot))

    assert text(message) == GOLDEN
    assert message.additional_kwargs[EPHEMERAL_BLOCKS_KEY] == [0]


@pytest.mark.asyncio
async def test_no_block_while_retrieval_is_still_running(ctx, memory, screenshot, hints_on):
    state = on_home(screenshot)

    before = await observation(ctx, state)
    memory[1].set()

    assert before.content == []
    assert text(await route_ready(ctx, state)) == GOLDEN


@pytest.mark.asyncio
@pytest.mark.parametrize("plan", ["- [x] Open Display\n- [x] Open Sound\n", ""])
async def test_no_block_without_an_active_milestone(ctx, memory, screenshot, hints_on, plan):
    memory[1].set()
    await route_ready(ctx, on_home(screenshot))

    assert (await observation(ctx, on_home(screenshot), plan)).content == []


@pytest.mark.asyncio
async def test_no_block_with_hints_off(ctx, memory, screenshot):
    memory[1].set()
    await asyncio.sleep(0.05)

    assert (await observation(ctx, on_home(screenshot))).content == []


@pytest.mark.asyncio
async def test_only_the_latest_observation_carries_the_route(ctx, memory, screenshot, hints_on):
    memory[1].set()
    ledger = TranscriptLedger()
    await route_ready(ctx, on_home(screenshot))
    first = await observation(ctx, on_home(screenshot), PLAN, ObservationPromptComponent())
    ledger.stage_turn([first, AIMessage(content="Tapping Display.")])
    ledger.commit_staged(step_key="step-1")

    latest = await observation(ctx, on_home(screenshot), PLAN, ObservationPromptComponent())
    sent = ledger.render([latest])

    assert [HEADER in str(message.content) for message in sent] == [False, False, True]
