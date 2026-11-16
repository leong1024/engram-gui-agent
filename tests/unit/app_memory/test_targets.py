import asyncio

import pytest

from artemis.app_memory import hints, service
from artemis.app_memory.milestones import Milestone, plan_milestones
from artemis.app_memory.navigator import Navigator
from artemis.app_memory.retrieval import NoTarget, NoTargetReason, Retriever
from artemis.app_memory.routing import RouteKind
from artemis.app_memory.targets import TargetQueue
from artemis.utils.plan_grammar import parse_plan
from tests.unit.app_memory.fixtures.maps import SETTINGS_MAP, MapBuilder, page, tap
from tests.unit.app_memory.fixtures.retrieval import (
    FakeSelector,
    by_title,
    embed_all,
    hash_provider,
)
from tests.unit.app_memory.test_service import context_for

DARK = Milestone("dark", "Turn on dark theme")
SOUND = Milestone("sound", "Open the sound settings")


class RecordingFind:
    def __init__(self, delay: float = 0.0, error: Exception | None = None) -> None:
        self.keys: list[str] = []
        self.running = self.peak = 0
        self._delay, self._error = delay, error

    async def __call__(self, goal: str, milestone: Milestone) -> NoTarget:
        self.keys.append(milestone.key)
        self.running += 1
        self.peak = max(self.peak, self.running)
        await asyncio.sleep(self._delay)
        self.running -= 1
        if self._error:
            raise self._error
        return NoTarget(milestone.key, NoTargetReason.NO_MATCH)


@pytest.mark.asyncio
async def test_a_plan_edit_retrieves_only_the_new_milestone_keys():
    find = RecordingFind()
    queue = TargetQueue(find)
    queue.request("goal", [DARK])
    await queue.join()
    dropped = queue.request("goal", [DARK, SOUND])
    await queue.join()
    assert find.keys == ["dark", "sound"]
    assert dropped == set()
    assert queue.request("goal", [SOUND]) == {"dark"}
    assert queue.result("dark") is None
    assert queue.result("sound") == NoTarget("sound", NoTargetReason.NO_MATCH)


@pytest.mark.asyncio
async def test_retrieval_runs_at_most_three_milestones_at_once():
    find = RecordingFind(delay=0.01)
    queue = TargetQueue(find)
    queue.request("goal", [Milestone(str(i), f"step {i}") for i in range(7)])
    await queue.join()
    assert (len(find.keys), find.peak) == (7, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("find", "reason"),
    [
        (RecordingFind(delay=1.0), NoTargetReason.TIMED_OUT),
        (RecordingFind(error=RuntimeError("boom")), NoTargetReason.FAILED),
    ],
)
async def test_a_slow_or_failing_retrieval_is_no_target(find, reason):
    queue = TargetQueue(find, budget_seconds=0.05)
    queue.request("goal", [DARK])
    await queue.join()
    assert queue.result("dark") == NoTarget("dark", reason)


def test_milestones_are_the_plans_top_level_items_with_their_children():
    plan = parse_plan("- [ ] Turn on dark theme\n  - [ ] Open display\n- [ ] Open sound\n")
    dark, sound = plan_milestones(plan)
    assert (dark.text, dark.query) == ("Turn on dark theme", "Turn on dark theme\nOpen display")
    assert dark.key == plan.top_level[0].key and sound.details == ()


@pytest.mark.asyncio
async def test_the_service_routes_a_milestone_once_its_target_is_found(tmp_path, monkeypatch):
    build = MapBuilder.open(tmp_path / service.DB_FILE)
    outside, home = build.outside(), build.state("Home")
    display = build.state("Display", "Screen brightness and the dark theme.", ("dark theme",))
    build.edge(outside, home, tap("Settings"))
    build.edge(home, display, tap("Display", "com.android.settings:id/display"))
    await embed_all(build.store, hash_provider())
    build.store.close()

    def navigator(read, installed):
        retriever = Retriever(read, hash_provider(), FakeSelector(by_title("Display")))
        return Navigator(retriever, read, installed)

    monkeypatch.setattr(service, "open_navigator", lambda *args: navigator)
    monkeypatch.setattr(service, "launcher_package", lambda serial: None)
    monkeypatch.setattr(service, "installed_versions", lambda serial: {SETTINGS_MAP.package: 34})
    ctx = context_for(tmp_path)
    memory = service.open_app_memory(ctx.data_engine)
    await memory.prepare_run(device_serial="emulator-5554")

    assert memory.route_for("dark", page("Home")) is None
    memory.request_targets("Use dark mode", [DARK])
    for _ in range(100):
        if route := memory.route_for("dark", page("Home")):
            break
        await asyncio.sleep(0.01)
    await memory.close()
    assert route is not None and route.kind is RouteKind.FROM_STATE
    assert hints.render(route).splitlines()[5].startswith('  1. Tap "Display" (id: display)')
