import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
import sqlite_vec
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import AIMessageChunk, BaseMessage

from artemis.app_memory import enrichment, service
from artemis.app_memory.describer import DescriptionLens
from artemis.app_memory.documents import Owner
from artemis.app_memory.embeddings import EmbeddingProvider
from artemis.app_memory.enrichment import Enrichment, open_enrichment
from artemis.app_memory.models import AbstractScreen, MapId, StateId
from artemis.app_memory.store import MapStore
from artemis.config.agent import AppMemoryConfig
from artemis.memory.step_memory import StepLens
from tests.unit.app_memory.test_service import context_for

MAP = MapId("com.android.settings", 3)
EMBEDDED = "SELECT COUNT(*) FROM embeddings WHERE model_id = 'fake/hash@4'"
VECTORS = "SELECT COUNT(*) FROM vec_fake_hash_4"
TITLES = {"home": "Settings home", "display": "Display settings"}


def screen(key: str) -> AbstractScreen:
    return AbstractScreen(".Settings", key, (key,), frozenset({key.title()}), False)


class FakeLens(StepLens):
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self._fail = fail

    async def render(self, key, payload: dict[str, Any]) -> str | None:
        self.calls.append((str(key), payload["text"]))
        if self._fail:
            raise RuntimeError("model unavailable")
        owner = Owner.parse(str(key))
        if owner.kind == "edge":
            return json.dumps({"description": "Opens the display settings."})
        title = TITLES[owner.owner_id]
        return json.dumps({"title": title, "purpose": f"{title}.", "affordances": ["go back"]})


class RecordingModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.seen: list[list[BaseMessage]] = []

    async def astream(self, messages: list[BaseMessage]) -> AsyncIterator[AIMessageChunk]:
        self.seen.append(messages)
        yield AIMessageChunk(content=self.reply)


def fake_enrichment(lens: StepLens, **kwargs: Any) -> Enrichment:
    provider = EmbeddingProvider("fake", "hash", 4, DeterministicFakeEmbedding(size=4))
    return Enrichment(lens, provider, image_path=Path, **kwargs)


def seed(store: MapStore) -> None:
    for key in TITLES:
        store.put_state(MAP, StateId(key), screen(key), now=1.0)
    store.put_edge(MAP, StateId("home"), StateId("display"), [], now=1.0)


def read(path: Path, sql: str) -> list[tuple[Any, ...]]:
    raw = sqlite3.connect(path)
    raw.enable_load_extension(True)
    sqlite_vec.load(raw)
    try:
        return raw.execute(sql).fetchall()
    finally:
        raw.close()


def statuses(path: Path) -> list[tuple[str, str]]:
    states = "SELECT title, description_status FROM states WHERE is_virtual = 0 ORDER BY 1"
    return [*read(path, states), *read(path, "SELECT description, description_status FROM edges")]


async def settle(done: Callable[[], bool]) -> None:
    for _ in range(200):
        if done():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("background jobs did not settle")


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / service.DB_FILE


@pytest.fixture
def store(db):
    opened = MapStore.open(db)
    seed(opened)
    yield opened
    opened.close()


@pytest.mark.asyncio
async def test_a_described_state_is_saved_and_unlocks_its_edges_and_vectors(store, db):
    lens = FakeLens()
    jobs = fake_enrichment(lens)
    jobs.bind(asyncio.get_running_loop(), lambda job: job(store))

    jobs.queue(store)
    await settle(lambda: read(db, EMBEDDED) == [(3,)])
    await jobs.close()

    assert statuses(db) == [
        ("Display settings", "ready"),
        ("Settings home", "ready"),
        ("Opens the display settings.", "ready"),
    ]
    assert read(db, VECTORS) == [(3,)]
    edge_prompt = next(text for key, text in lens.calls if key.startswith("edge:"))
    assert "Screen before: Settings home" in edge_prompt
    assert "Screen after: Display settings" in edge_prompt


@pytest.mark.asyncio
async def test_a_job_that_keeps_failing_is_marked_failed(store, db):
    lens = FakeLens(fail=True)
    jobs = fake_enrichment(lens, retry_limit=1)
    jobs.bind(asyncio.get_running_loop(), lambda job: job(store))

    jobs.queue(store)
    await settle(lambda: [status for _, status in statuses(db)][:2] == ["failed", "failed"])
    await jobs.close()

    assert sorted(key for key, _ in lens.calls) == ["state:display"] * 2 + ["state:home"] * 2
    assert [status for _, status in statuses(db)] == ["failed", "failed", "pending"]


@pytest.mark.asyncio
async def test_prepare_run_describes_rows_an_earlier_run_left_pending(
    tmp_path, store, db, monkeypatch
):
    store.close()
    lens = FakeLens()
    monkeypatch.setattr(service, "open_enrichment", lambda *args: fake_enrichment(lens))
    ctx = context_for(tmp_path)
    ctx.data_engine.start_session(goal="a later run")
    ctx.app_memory = service.open_app_memory(ctx.data_engine)

    async with ctx:
        await ctx.app_memory.prepare_run(device_serial=None)
        await settle(lambda: read(db, EMBEDDED) == [(3,)])

    assert [status for _, status in statuses(db)] == ["ready"] * 3
    assert read(db, VECTORS) == [(3,)]


@pytest.mark.asyncio
async def test_the_describer_reads_the_model_reply_and_forbids_naming_screen_content():
    reply = json.dumps({"title": "Inbox", "purpose": "Lists conversations.", "affordances": []})
    model = RecordingModel(reply)

    rendered = await DescriptionLens(lambda: model).render("state:s1", {"text": "x", "image": None})

    assert json.loads(rendered or "") == json.loads(reply)
    system_prompt = model.seen[0][0].content
    assert "Never name specific content seen in the screenshot" in system_prompt


def test_a_missing_describer_key_leaves_descriptions_pending_with_one_warning(monkeypatch, caplog):
    from third_party.mobile_use.config import llm as base

    monkeypatch.setattr(base.settings, "GOOGLE_API_KEY", None)

    assert open_enrichment(None, AppMemoryConfig(), Path) is None
    warnings = [r for r in caplog.records if r.name == enrichment.__name__]
    assert len(warnings) == 1
