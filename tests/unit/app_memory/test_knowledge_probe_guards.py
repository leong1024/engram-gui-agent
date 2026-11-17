import asyncio
import hashlib
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.language_models import BaseChatModel

from artemis.app_memory.knowledge import open_knowledge
from artemis.app_memory.knowledge import probe as probe_module
from artemis.app_memory.knowledge.reports import ProbeStatus
from artemis.app_memory.models import MapId
from artemis.app_memory.retrieval import LLMSelector
from artemis.app_memory.store import MapStore
from artemis.config import settings
from tests.unit.app_memory.fixtures.parts import SETTINGS
from tests.unit.app_memory.fixtures.probe import CONFIG, embed, probe, settings_map
from tests.unit.app_memory.fixtures.retrieval import HashEmbeddings

DARK_THEME = "turn on dark theme"


@pytest.fixture
def traces(tmp_path: Path) -> Path:
    """A closed map store: Settings 34 without Display, 33 with it, both embedded."""
    store = MapStore.open(tmp_path / "app_memory.db")
    settings_map(store, MapId(SETTINGS, 33))
    settings_map(store, display=False)
    embed(store)
    store.close()
    return tmp_path


class Hangs(HashEmbeddings):
    async def aembed_query(self, text: str) -> list[float]:
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")


def test_without_an_embedding_key_the_provider_is_unavailable(traces):
    with patch.object(settings, "GOOGLE_API_KEY", None), open_knowledge(traces, CONFIG) as k:
        result = asyncio.run(k.probe(DARK_THEME, SETTINGS))
    assert (result.status, result.candidates) == (ProbeStatus.PROVIDER_UNAVAILABLE, ())


def test_a_failing_provider_is_unavailable_after_one_call(traces):
    embeddings = HashEmbeddings(fail=True)
    result = probe(traces, DARK_THEME, SETTINGS, embeddings)
    assert result.status is ProbeStatus.PROVIDER_UNAVAILABLE
    assert embeddings.queries == [DARK_THEME]


def test_the_embedding_call_is_capped_at_ten_seconds(traces, monkeypatch):
    assert probe_module.EMBED_TIMEOUT_SECONDS == 10
    monkeypatch.setattr(probe_module, "EMBED_TIMEOUT_SECONDS", 0.01)
    result = probe(traces, DARK_THEME, SETTINGS, Hangs())
    assert result.status is ProbeStatus.PROVIDER_UNAVAILABLE


def forbidden(what: str):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"the probe must not {what}")

    return refuse


def test_the_probe_calls_no_llm_no_subprocess_and_no_socket(traces):
    llm = forbidden("call an LLM")
    device = forbidden("start a process or open a socket")
    with (
        patch.object(LLMSelector, "select", llm),
        patch.object(BaseChatModel, "_generate", llm),
        patch.object(BaseChatModel, "_agenerate", llm),
        patch.object(subprocess.Popen, "__init__", device),
        patch.object(asyncio, "create_subprocess_exec", device),
        patch.object(asyncio, "create_subprocess_shell", device),
        patch.object(socket.socket, "connect", device),
    ):
        with pytest.raises(AssertionError, match="start a process"):
            subprocess.run(["true"], check=False)
        result = probe(traces, DARK_THEME, SETTINGS)
    assert [(c.page, c.borrowed) for c in result.candidates] == [("Display", True)]


def test_probes_never_change_the_database(traces):
    database = traces / "app_memory.db"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    statuses = {
        probe(traces, query, package).status
        for query, package in (
            (DARK_THEME, SETTINGS),
            (DARK_THEME, None),
            ("change the volume", SETTINGS),
            ("order a pizza", None),
            ("", None),
        )
    }
    assert statuses == {
        ProbeStatus.FOUND,
        ProbeStatus.NO_MATCH,
        ProbeStatus.EMPTY_QUERY,
    }
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
