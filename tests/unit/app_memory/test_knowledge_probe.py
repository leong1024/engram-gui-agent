from collections.abc import Iterator
from pathlib import Path

import pytest

from artemis.app_memory.embeddings import EmbeddingProvider
from artemis.app_memory.knowledge.reports import ProbeStatus
from artemis.app_memory.models import MapId
from artemis.app_memory.store import MapStore
from tests.unit.app_memory.fixtures.maps import MapBuilder
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.probe import embed, probe, settings_map
from tests.unit.app_memory.fixtures.retrieval import DIM, HashEmbeddings

DARK_THEME = "turn on dark theme"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[MapStore]:
    opened = MapStore.open(tmp_path / "app_memory.db")
    yield opened
    opened.close()


def found(traces: Path, query: str = DARK_THEME, package: str | None = None) -> list[tuple]:
    result = probe(traces, query, package)
    assert result.status is ProbeStatus.FOUND
    return [
        (c.package, c.version_code, c.page, c.hops_from_launch, c.borrowed)
        for c in result.candidates
    ]


def test_a_known_page_is_found_with_its_hops_from_launch_in_one_embedding_call(store, tmp_path):
    settings_map(store)
    embed(store)
    embeddings = HashEmbeddings()

    result = probe(tmp_path, f"  {DARK_THEME} ", embeddings=embeddings)

    assert result.status is ProbeStatus.FOUND and result.query == DARK_THEME
    [display] = result.candidates
    assert (display.page, display.hops_from_launch, display.borrowed) == ("Display", 2, False)
    assert 0.35 <= display.similarity <= 1.0
    assert embeddings.queries == [DARK_THEME]


def test_a_page_with_no_route_from_launch_is_found_with_null_hops(store, tmp_path):
    settings_map(store)
    embed(store)
    assert found(tmp_path, "change the volume") == [(SETTINGS, 34, "Sound", None, False)]


def test_a_query_under_the_similarity_floor_matches_nothing(store, tmp_path):
    settings_map(store)
    embed(store)
    result = probe(tmp_path, "order a pizza")
    assert (result.status, result.candidates) == (ProbeStatus.NO_MATCH, ())


def test_at_most_three_candidates_are_kept_most_similar_first(store, tmp_path):
    maps = MapBuilder(store)
    for extra in range(5):
        filler = " ".join(f"filler{chr(97 + i)}" for i in range(extra * 2))
        maps.state(f"Theme {chr(97 + extra)}", f"Dark theme {filler}.", ("turn on dark theme",))
    embed(store)

    result = probe(tmp_path, DARK_THEME)

    assert [c.page for c in result.candidates] == ["Theme a", "Theme b", "Theme c"]
    similarities = [c.similarity for c in result.candidates]
    assert similarities == sorted(similarities, reverse=True)


def test_a_package_filter_searches_only_that_package(store, tmp_path):
    settings_map(store)
    clock = MapBuilder(store, MapId(CLOCK, 2))
    clock.state("Night mode", "The clock in a dark theme.", ("turn on dark theme",))
    embed(store)

    assert {row[0] for row in found(tmp_path)} == {SETTINGS, CLOCK}
    assert found(tmp_path, package=CLOCK) == [(CLOCK, 2, "Night mode", None, False)]


def test_older_versions_are_borrowed_only_when_the_newest_finds_nothing(store, tmp_path):
    settings_map(store, MapId(SETTINGS, 33))
    settings_map(store, display=False)
    embed(store)

    assert found(tmp_path, package=SETTINGS) == [(SETTINGS, 33, "Display", 2, True)]
    assert probe(tmp_path, DARK_THEME).status is ProbeStatus.NO_MATCH

    settings_map(store, MapId(SETTINGS, 35))
    embed(store)
    assert found(tmp_path, package=SETTINGS) == [(SETTINGS, 35, "Display", 2, False)]


def test_only_two_older_versions_are_borrowed(store, tmp_path):
    settings_map(store, MapId(SETTINGS, 30))
    for version in (31, 32, 34):
        settings_map(store, MapId(SETTINGS, version), display=False)
    embed(store)
    assert probe(tmp_path, DARK_THEME, SETTINGS).status is ProbeStatus.NO_MATCH


def test_without_a_database_the_status_is_no_maps_and_no_file_is_created(tmp_path):
    assert probe(tmp_path, DARK_THEME).status is ProbeStatus.NO_MAPS
    assert not (tmp_path / "app_memory.db").exists()


def test_a_package_with_no_map_is_no_maps(store, tmp_path):
    settings_map(store)
    embed(store)
    assert probe(tmp_path, DARK_THEME, CLOCK).status is ProbeStatus.NO_MAPS


@pytest.mark.parametrize("model", [None, "text-embedding-3-small"])
def test_maps_without_vectors_of_the_configured_model_are_no_vectors(store, tmp_path, model):
    settings_map(store)
    if model:
        embed(store, EmbeddingProvider("openai", model, DIM, HashEmbeddings()))
    embeddings = HashEmbeddings()
    assert probe(tmp_path, DARK_THEME, embeddings=embeddings).status is ProbeStatus.NO_VECTORS
    assert embeddings.queries == []


def test_a_query_vector_of_another_size_than_the_stored_ones_is_no_vectors(store, tmp_path):
    class ShortVectors(HashEmbeddings):
        def embed_query(self, text: str) -> list[float]:
            return super().embed_query(text)[: DIM // 2]

    settings_map(store)
    embed(store)
    result = probe(tmp_path, DARK_THEME, embeddings=ShortVectors())
    assert result.status is ProbeStatus.NO_VECTORS


@pytest.mark.parametrize("query", ["", "   \n\t"])
def test_an_empty_query_searches_nothing(store, tmp_path, query):
    settings_map(store)
    embed(store)
    embeddings = HashEmbeddings()
    result = probe(tmp_path, query, embeddings=embeddings)
    assert (result.status, result.query, result.candidates) == (ProbeStatus.EMPTY_QUERY, "", ())
    assert embeddings.queries == []
