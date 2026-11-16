import logging
from collections.abc import AsyncIterator, Iterator

import pytest
from langchain_core.messages import AIMessageChunk, BaseMessage

from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import MapId
from artemis.app_memory.retrieval import (
    LLMSelector,
    NoTarget,
    NoTargetReason,
    Retriever,
    TargetResolution,
)
from artemis.app_memory.retrieval import retriever as retriever_module
from artemis.app_memory.retrieval.candidates import candidate_maps
from tests.unit.app_memory.fixtures.maps import SETTINGS_MAP, MapBuilder, tap
from tests.unit.app_memory.fixtures.retrieval import (
    FakeSelector,
    by_title,
    embed_all,
    hash_provider,
)

YOUTUBE = MapId("com.google.android.youtube", 5)
MUSIC = MapId("com.google.android.apps.youtube.music", 7)
INSTALLED = {SETTINGS_MAP.package: 34, YOUTUBE.package: 5, MUSIC.package: 7}
DARK_THEME = Milestone("m1", "Turn on dark theme", ("Open the display settings",))


@pytest.fixture
def build(tmp_path) -> Iterator[MapBuilder]:
    builder = MapBuilder.open(tmp_path / "app_memory.db")
    yield builder
    builder.store.close()


async def settings_map(build: MapBuilder, map_id: MapId = SETTINGS_MAP) -> MapBuilder:
    maps = MapBuilder(build.store, map_id)
    home = maps.state("Home", "The main list of settings.", ("open a settings page",))
    display = maps.state("Display", "Screen brightness and colours.", ("change the brightness",))
    toggle = maps.edge(home, display, tap("Display"))
    maps.store.documents.describe_edge(toggle, "Turns on the dark theme from the display page")
    maps.state("Sound", "Volume and ringtones.", ("change the volume",))
    await embed_all(build.store, hash_provider())
    return maps


async def music_maps(build: MapBuilder) -> None:
    for map_id, app in ((YOUTUBE, "Videos"), (MUSIC, "Songs")):
        MapBuilder(build.store, map_id).state(f"{app} player", "Play a song or a video.", ("play",))
    await embed_all(build.store, hash_provider())


def retriever(build: MapBuilder, selector: FakeSelector, fail: bool = False) -> Retriever:
    async def read(job):
        return job(build.store)

    return Retriever(read, hash_provider(fail), selector)


@pytest.mark.asyncio
async def test_an_edge_hit_nominates_its_destination_with_the_edge_as_last_hop(build):
    await settings_map(build)
    selector = FakeSelector(by_title("Display"))
    found = await retriever(build, selector).resolve("Use dark mode", DARK_THEME, INSTALLED)
    assert isinstance(found, TargetResolution)
    assert (found.map_id, found.borrowed, found.confidence) == (SETTINGS_MAP, False, 0.9)
    display = next(c for c in selector.calls[0] if c.card.title == "Display")
    assert display.last_hop is not None and found.last_hop_edge_id == display.last_hop.edge_id
    assert display.last_hop.description == "Turns on the dark theme from the display page"


@pytest.mark.asyncio
async def test_a_map_below_the_similarity_floor_makes_no_selector_call(build):
    await settings_map(build)
    selector = FakeSelector()
    pizza = Milestone("m2", "Order a pizza")
    found = await retriever(build, selector).resolve("Dinner", pizza, INSTALLED)
    assert found == NoTarget("m2", NoTargetReason.NO_MATCH)
    assert selector.calls == []


@pytest.mark.asyncio
async def test_one_proposal_is_accepted_without_a_tier_two_call(build):
    await settings_map(build)
    await music_maps(build)
    selector = FakeSelector()
    found = await retriever(build, selector).resolve("Use dark mode", DARK_THEME, INSTALLED)
    assert isinstance(found, TargetResolution) and found.map_id == SETTINGS_MAP
    assert len(selector.calls) == 1


@pytest.mark.asyncio
async def test_two_proposals_are_settled_by_one_tier_two_call(build):
    await music_maps(build)
    selector = FakeSelector(lambda found: by_title("Songs player")(found) or found[0])
    song = Milestone("m3", "Play a song")
    found = await retriever(build, selector).resolve("Play Coldplay", song, INSTALLED)
    assert isinstance(found, TargetResolution) and found.map_id == MUSIC
    assert [len(call) for call in selector.calls] == [1, 1, 2]


@pytest.mark.asyncio
async def test_with_no_primary_proposal_an_older_version_is_borrowed(build):
    await settings_map(build)
    newer = {**INSTALLED, SETTINGS_MAP.package: 35}
    found = await retriever(build, FakeSelector()).resolve("Dark mode", DARK_THEME, newer)
    assert isinstance(found, TargetResolution)
    assert (found.map_id, found.borrowed) == (SETTINGS_MAP, True)


@pytest.mark.asyncio
async def test_a_package_that_is_not_installed_is_never_searched(build):
    await settings_map(build)
    selector = FakeSelector()
    found = await retriever(build, selector).resolve("Dark mode", DARK_THEME, {})
    assert found == NoTarget("m1", NoTargetReason.NO_MAPS)
    assert selector.calls == []


@pytest.mark.asyncio
async def test_a_low_confidence_answer_is_no_proposal(build):
    await settings_map(build)
    found = await retriever(build, FakeSelector(confidence=0.4)).resolve("x", DARK_THEME, INSTALLED)
    assert found == NoTarget("m1", NoTargetReason.NO_MATCH)


@pytest.mark.asyncio
async def test_a_failing_provider_gives_no_target_for_the_run_with_one_warning(build, caplog):
    await settings_map(build)
    search = retriever(build, FakeSelector(), fail=True)
    with caplog.at_level(logging.WARNING):
        first = await search.resolve("Dark mode", DARK_THEME, INSTALLED)
        second = await search.resolve("Dark mode", Milestone("m2", "Open sound"), INSTALLED)
    assert first == NoTarget("m1", NoTargetReason.PROVIDER_UNAVAILABLE)
    assert second == NoTarget("m2", NoTargetReason.PROVIDER_UNAVAILABLE)
    warnings = [r for r in caplog.records if r.name == retriever_module.__name__]
    assert len(warnings) == 1


def test_candidate_maps_prefer_the_installed_version_then_older_ones():
    pkg = "com.android.settings"
    maps = [MapId(pkg, v) for v in (-1, 30, 31, 32, 34, 36)] + [MapId("gone.app", 1)]
    found = candidate_maps({pkg: 34}, maps, fallback_versions=2)
    assert found.primary == (MapId(pkg, 34),)
    assert found.fallback == (MapId(pkg, 32), MapId(pkg, 31), MapId(pkg, -1))


class ReplyModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.seen: list[list[BaseMessage]] = []

    async def astream(self, messages: list[BaseMessage]) -> AsyncIterator[AIMessageChunk]:
        self.seen.append(messages)
        if not self.reply:
            raise ConnectionError("selector model unavailable")
        yield AIMessageChunk(content=self.reply)


@pytest.mark.asyncio
async def test_the_llm_selector_reads_a_structured_answer_and_survives_failure(build):
    await settings_map(build)
    found = FakeSelector()
    await retriever(build, found).resolve("Use dark mode", DARK_THEME, INSTALLED)
    candidates = found.calls[0]
    reply = f'{{"state_id": "{candidates[0].card.state_id}", "confidence": 0.8, "reason": "r"}}'
    model = ReplyModel(reply)
    answer = await LLMSelector(lambda: model).select("Use dark mode", DARK_THEME, candidates)
    assert answer is not None and (answer.state_id, answer.confidence) == (
        candidates[0].card.state_id,
        0.8,
    )
    prompt = model.seen[0][1].content
    assert "Milestone: Turn on dark theme\nOpen the display settings" in prompt
    assert f"app: {SETTINGS_MAP.package} v34" in prompt
    failing = LLMSelector(lambda: ReplyModel(""))
    assert await failing.select("Use dark mode", DARK_THEME, candidates) is None
