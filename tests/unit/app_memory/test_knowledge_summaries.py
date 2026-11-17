import asyncio
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from artemis.app_memory.embeddings import EmbeddingProvider
from artemis.app_memory.knowledge import open_knowledge
from artemis.app_memory.knowledge.reports import Capabilities, Coverage, NotMapped, Profile
from artemis.app_memory.models import MapId, ObservationStatus, SessionOutcome
from artemis.app_memory.store import MapStore
from artemis.config.agent import AppMemoryConfig, AppMemoryHintsConfig
from tests.unit.app_memory.fixtures.maps import NOW, SETTINGS_MAP, MapBuilder, tap
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.retrieval import DIM, HashEmbeddings, embed_all
from tests.unit.app_memory.fixtures.traces import Trace

CONFIG = AppMemoryConfig()
HINTS_OFF = AppMemoryConfig(hints=AppMemoryHintsConfig(enabled=False))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[MapStore]:
    opened = MapStore.open(tmp_path / "app_memory.db")
    yield opened
    opened.close()


def capabilities(traces: Path, package: str = SETTINGS) -> Capabilities:
    with open_knowledge(traces, CONFIG) as knowledge:
        report = knowledge.capabilities(package)
    assert isinstance(report, Capabilities)
    return report


def embed(store: MapStore, provider: str = "gemini", model: str = "gemini-embedding-2") -> None:
    asyncio.run(embed_all(store, EmbeddingProvider(provider, model, DIM, HashEmbeddings())))


def run(
    store: MapStore,
    session_id: str,
    outcome: SessionOutcome = SessionOutcome.COMPLETED,
    at: float = NOW,
    map_id: MapId = SETTINGS_MAP,
) -> None:
    maps = MapBuilder(store, map_id, session_id)
    maps.edge(maps.state("Home"), maps.state("Display"), tap("Display"))
    store.finalize_session(session_id, outcome, ObservationStatus.CONFIRMED, at)


@pytest.mark.parametrize("database", [False, True])
def test_no_maps_read_as_an_empty_overview_and_no_file_is_created(tmp_path, database):
    if database:
        MapStore.open(tmp_path / "app_memory.db").close()
    with open_knowledge(tmp_path, CONFIG) as knowledge:
        assert knowledge.overview().apps == ()
        assert isinstance(knowledge.capabilities(SETTINGS), NotMapped)
    assert (tmp_path / "app_memory.db").exists() is database


def test_the_overview_lists_the_newest_version_of_each_package_most_recent_first(store, tmp_path):
    for map_id, seen_at in ((MapId(SETTINGS, 33), NOW), (MapId(CLOCK, 1), NOW + 50)):
        MapBuilder(store, map_id).state("Home", seen_at=seen_at)
    maps = MapBuilder(store, SETTINGS_MAP, "a")
    home, display = maps.state("Home", seen_at=NOW + 100), maps.state("Display")
    maps.seen("Sound")
    maps.edge(home, display, tap("Display"))
    maps.edge(display, home, tap("Back"), confirmed=0, provisional=1)
    MapBuilder(store, SETTINGS_MAP, "b").edge(home, display, tap("Display"))
    MapBuilder(store, MapId(CLOCK, 2)).state("Alarm", seen_at=NOW + 200)

    with open_knowledge(tmp_path, CONFIG) as knowledge:
        apps = knowledge.overview().apps
    assert [(app.package, app.version_code) for app in apps] == [(CLOCK, 2), (SETTINGS, 34)]
    settings = apps[1]
    assert (settings.pages, settings.routes, settings.sessions) == (2, 1, 2)
    assert settings.last_seen_at == NOW + 100
    assert [old.version_code for old in capabilities(tmp_path).other_versions] == [33]


def test_pages_rank_by_confirmed_and_provisional_arrivals_and_keep_the_top_eight(store, tmp_path):
    maps = MapBuilder(store)
    home = maps.state("Home")
    for i in range(10):
        maps.edge(home, maps.state(f"Page {i}"), tap(f"Page {i}"), confirmed=i)
    maps.edge(home, maps.state("Page 0"), tap("Jump"), confirmed=0, provisional=20)
    maps.edge(home, maps.state("Page 1"), tap("Skip"), confirmed=0, discounted=50)

    pages = [(page.title, page.visits) for page in capabilities(tmp_path).pages]
    assert pages == [("Page 0", 20), *((f"Page {i}", i) for i in range(9, 2, -1))]


def test_capabilities_drop_case_and_space_duplicates_ranked_by_their_best_page(store, tmp_path):
    maps = MapBuilder(store)
    home = maps.state("Home", affordances=("Pair a device",))
    display = maps.state("Display", affordances=("Turn on  dark theme", "Change brightness"))
    bluetooth = maps.state("Bluetooth", affordances=("Pair a device", "turn on DARK theme"))
    maps.state("About", affordances=tuple(f"read note {i}" for i in range(25)))
    maps.edge(home, display, tap("Display"), confirmed=2)
    maps.edge(home, bluetooth, tap("Bluetooth"), confirmed=5)

    offered = capabilities(tmp_path).capabilities
    assert offered[:3] == ("Pair a device", "turn on DARK theme", "Change brightness")
    assert len(offered) == 20


@pytest.mark.parametrize(
    ("described", "pending", "expected"),
    [
        (9, 0, Coverage.SPARSE),
        (10, 0, Coverage.PARTIAL),
        (29, 0, Coverage.PARTIAL),
        (30, 0, Coverage.BROAD),
        (16, 15, Coverage.BROAD),
        (15, 16, Coverage.PARTIAL),
        (0, 40, Coverage.SPARSE),
    ],
)
def test_coverage_follows_the_page_thresholds(store, tmp_path, described, pending, expected):
    maps = MapBuilder(store)
    for i in range(described):
        maps.state(f"Page {i}")
    for i in range(pending):
        maps.seen(f"Pending {i}")

    report = capabilities(tmp_path)
    assert report.coverage is expected
    assert len(report.pages) == min(described, 8)


def test_an_unknown_package_is_not_mapped(store, tmp_path):
    MapBuilder(store).state("Home")
    with open_knowledge(tmp_path, CONFIG) as knowledge:
        report = knowledge.capabilities("com.example.unknown")
    assert isinstance(report, NotMapped)
    assert report.package == "com.example.unknown"


def test_example_goals_are_masked_distinct_newest_first_from_completed_runs(store, tmp_path):
    trace = Trace(tmp_path)
    goals = {
        "old": ("Turn on dark theme", SessionOutcome.COMPLETED),
        "dup": ("turn on  dark theme", SessionOutcome.COMPLETED),
        "mail": ("Email my battery level to alex@example.com", SessionOutcome.COMPLETED),
        "failed": ("Open the hidden page", SessionOutcome.FAILED),
    }
    for at, (session_id, (goal, outcome)) in enumerate(goals.items()):
        trace.session(session_id, goal=goal)
        run(store, session_id, outcome, NOW + at)
    trace.session("clock", goal="Set an alarm")
    run(store, "clock", at=NOW + 10, map_id=MapId(CLOCK, 1))

    report = capabilities(tmp_path)
    assert report.example_goals == ("Email my battery level to <EMAIL>", "turn on dark theme")


def test_without_a_trace_database_the_report_has_no_example_goals(store, tmp_path):
    run(store, "s1")
    report = capabilities(tmp_path)
    assert report.example_goals == ()
    assert [page.title for page in report.pages] == ["Display", "Home"]


@pytest.mark.parametrize(
    ("provider", "model", "config", "expected"),
    [
        ("gemini", "gemini-embedding-2", CONFIG, Profile.PRO),
        ("gemini", "gemini-embedding-2", HINTS_OFF, Profile.EITHER),
        ("openai", "text-embedding-3-small", CONFIG, Profile.EITHER),
        (None, None, CONFIG, Profile.EITHER),
    ],
)
def test_pro_is_recommended_only_with_hints_on_and_vectors_of_the_configured_model(
    store, tmp_path, provider, model, config, expected
):
    MapBuilder(store).state("Home", affordances=("open a settings page",))
    if provider:
        embed(store, provider, model)

    with open_knowledge(tmp_path, config) as knowledge:
        overview, report = knowledge.overview(), knowledge.capabilities(SETTINGS)
    assert overview.hints_enabled is config.hints_on
    assert {overview.apps[0].recommended_profile, report.app.recommended_profile} == {expected}


def test_reports_never_change_either_database(store, tmp_path):
    Trace(tmp_path).session("s1", goal="Turn on dark theme")
    run(store, "s1")
    embed(store)
    store.close()
    files = [tmp_path / "app_memory.db", tmp_path / "data_engine.db"]
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in files]
    with open_knowledge(tmp_path, CONFIG) as knowledge:
        knowledge.overview()
        knowledge.capabilities(SETTINGS)
        knowledge.capabilities(CLOCK)
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in files] == before
