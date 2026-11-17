import uuid
import pytest
from langchain_core.messages import AIMessage, BaseMessage

from artemis.context import ArtemisContext
from artemis.drivers.base import ScreenData
from artemis.drivers.mock.mock_driver import MockDeviceDriver
from artemis.graph.graph import get_graph
from artemis.graph.state import State
from artemis.llm.fake_model import FakeChatModel
from artemis.llm.router import ModelFactory
from artemis.utils.notes import get_note_file_path

GOAL = "Turn on dark theme"
MILESTONE = "Open Display settings"
SETTINGS_ELEMENT = {
    "text": "Display",
    "bounds": "[0,200][1080,320]",
    "package": "com.android.settings",
    "class": "android.widget.TextView",
}


def _call(name: str, args: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": uuid.uuid4().hex}])


def _decide(model: FakeChatModel, messages: list[BaseMessage]) -> AIMessage:
    """The Planner writes one open milestone; the Operator checks it off, then stops."""
    called = {tc["name"] for m in messages for tc in (getattr(m, "tool_calls", None) or [])}
    if "ask_diagnoser" in model.bound_tool_names:
        if "update_note" in called:
            return AIMessage(content="Done.")
        done = {"target": f"- [ ] {MILESTONE}", "replacement": f"- [x] {MILESTONE}"}
        return _call("update_note", {"key": "task_plan", **done})
    if "save_note" in model.bound_tool_names and "save_note" not in called:
        return _call("save_note", {"key": "task_plan", "content": f"- [ ] {MILESTONE}\n"})
    return AIMessage(content="ok")


_MOCK_SCREEN = MockDeviceDriver.get_screen_data


async def _settings_screen(driver: MockDeviceDriver, skip_settling: bool = False) -> ScreenData:
    """The mock's screen with a parseable element tree and an activity, as a device reports."""
    screen = await _MOCK_SCREEN(driver, skip_settling)
    return screen.model_copy(update={"ui_elements": [SETTINGS_ELEMENT], "activity": ".Settings"})


def script_pro_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline Pro: the mock driver shows one Settings screen and the fake model follows
    `_decide`."""
    monkeypatch.setenv("ARTEMIS_FAKE_LLM", "1")
    monkeypatch.setenv("ARTEMIS_MOCK_DRIVER", "1")
    monkeypatch.setattr(ModelFactory, "_cache", {})
    monkeypatch.setattr(FakeChatModel, "_decide", _decide)
    monkeypatch.setattr(MockDeviceDriver, "get_screen_data", _settings_screen)


async def pro_run(ctx: ArtemisContext) -> tuple[str, int]:
    """Runs the Pro graph to the end; returns the final plan and the recorded step count."""
    engine = ctx.data_engine
    assert engine is not None
    session_id = str(engine.start_session(goal=GOAL))
    await ctx.app_memory.prepare_run(device_serial=None)
    async with ctx:
        graph = await get_graph(ctx)
        await graph.ainvoke(State.initial(GOAL), config={"recursion_limit": 40})
        await engine.wait_for_writes()
        plan = get_note_file_path(engine.base_dir, "task_plan").read_text(encoding="utf-8")
        engine.end_session("completed")
    return plan, len(engine.storage.get_steps(session_id))
