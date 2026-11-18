import functools
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, Tool

import mcp_server.tools.knowledge as knowledge_tool
from mcp_server.base import mcp
from mcp_server import tools
from artemis.app_memory import store as map_store
from artemis.app_memory.knowledge import open_knowledge, render
from artemis.app_memory.knowledge import service as knowledge_service
from artemis.app_memory.knowledge.reports import LEVELS, KnowledgeReport, KnowledgeResponse, Level
from artemis.app_memory.knowledge.reports import Capabilities, NotMapped, Overview, ProbeResult
from artemis.app_memory.store import MapStore
from artemis.runtime import trace_store
from tests.unit.app_memory.fixtures.parts import CLOCK, SETTINGS
from tests.unit.app_memory.fixtures.probe import CONFIG, embed, provider, settings_map

pytestmark = pytest.mark.asyncio

TOOL = "mobile_get_knowledge"
DARK_THEME = "turn on dark theme"
TRUNK_TOOLS = (
    "mobile_run_task",
    "mobile_manage_task",
    "mobile_get_device_state",
    "mobile_inspect_trace",
    "mobile_diagnose",
)


@pytest.fixture
def traces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty traces directory the tool reads, with the hash embedder and default config."""
    monkeypatch.setattr(trace_store, "TRACES_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_tool.env_utils, "get_project_root", lambda: str(tmp_path))
    fake = provider()
    opener = functools.partial(open_knowledge, config=CONFIG, embedder=lambda: fake)
    monkeypatch.setattr(knowledge_tool, "open_knowledge", opener)
    return tmp_path


@pytest.fixture
def mapped(traces: Path) -> Path:
    store = MapStore.open(traces / "app_memory.db")
    settings_map(store)
    embed(store)
    store.close()
    return traces


async def call(arguments: dict[str, Any]) -> CallToolResult:
    async with create_connected_server_and_client_session(mcp) as session:
        return await session.call_tool(TOOL, arguments)


async def listed(server: FastMCP = mcp) -> dict[str, Tool]:
    async with create_connected_server_and_client_session(server) as session:
        return {tool.name: tool for tool in (await session.list_tools()).tools}


def text(result: CallToolResult) -> str:
    [block] = result.content
    assert block.type == "text"
    return block.text


def response(result: CallToolResult) -> KnowledgeResponse:
    assert not result.isError, text(result)
    return KnowledgeResponse.model_validate(result.structuredContent)


def report[R: KnowledgeReport](result: CallToolResult, kind: type[R]) -> R:
    held = getattr(response(result), LEVELS[kind].value)
    assert isinstance(held, kind)
    return held


async def test_the_tool_is_listed_with_one_schema_for_every_level():
    tool = (await listed())[TOOL]
    assert tool.outputSchema is not None
    assert set(tool.outputSchema["properties"]) == {"level", *(level.value for level in Level)}
    assert tool.outputSchema["required"] == ["level"]
    assert set(tool.inputSchema["properties"]) == {"app", "query"}
    assert "never touches the device" in (tool.description or "")


async def test_registering_it_leaves_the_other_five_tools_unchanged():
    alone = FastMCP("artemis")
    for name in TRUNK_TOOLS:
        alone.tool()(getattr(tools, name))

    served, expected = await listed(), await listed(alone)

    assert set(served) == {*TRUNK_TOOLS, TOOL}
    assert {name: served[name] for name in TRUNK_TOOLS} == expected


@pytest.mark.parametrize(
    ("arguments", "level"),
    [
        ({}, Level.OVERVIEW),
        ({"app": SETTINGS}, Level.CAPABILITIES),
        ({"app": "com.example.unmapped"}, Level.NOT_MAPPED),
        ({"query": DARK_THEME}, Level.PROBE),
        ({"app": SETTINGS, "query": DARK_THEME}, Level.PROBE),
    ],
)
async def test_text_and_structured_content_describe_the_same_report(mapped, arguments, level):
    result = await call(arguments)

    reply = response(result)
    assert reply.level is level
    assert text(result) == render(getattr(reply, level.value))


async def test_the_overview_lists_each_mapped_app_with_its_version(mapped):
    result = await call({})
    [app] = report(result, Overview).apps
    assert (app.package, app.version_code) == (SETTINGS, 34)
    assert SETTINGS in text(result) and "34" in text(result)


async def test_capabilities_list_the_pages_engram_has_seen(mapped):
    capabilities = report(await call({"app": SETTINGS}), Capabilities)
    assert {page.title for page in capabilities.pages} == {"Home", "Display", "Sound"}


async def test_an_unknown_package_is_not_mapped_and_not_an_error(mapped):
    result = await call({"app": "com.example.unmapped"})
    assert report(result, NotMapped).package == "com.example.unmapped"


async def test_a_probe_finds_the_page_for_a_known_goal(mapped):
    probe = report(await call({"query": DARK_THEME}), ProbeResult)
    assert probe.status == "found"
    assert [c.page for c in probe.candidates] == ["Display"]


async def test_a_probe_limited_to_another_app_finds_no_maps(mapped):
    probe = report(await call({"app": CLOCK, "query": DARK_THEME}), ProbeResult)
    assert (probe.status, probe.candidates) == ("no_maps", ())


@pytest.mark.parametrize(
    ("arguments", "level"),
    [
        ({"app": "", "query": ""}, Level.OVERVIEW),
        ({"app": "  ", "query": None}, Level.OVERVIEW),
        ({"app": SETTINGS, "query": " "}, Level.CAPABILITIES),
    ],
)
async def test_empty_arguments_are_treated_as_absent(mapped, arguments, level):
    assert response(await call(arguments)).level is level


async def test_an_unreadable_database_is_an_error_result_with_the_reason(traces):
    (traces / "app_memory.db").write_bytes(b"this is not a sqlite database" * 100)

    result = await call({})

    assert result.isError
    assert "database could not be read" in text(result)
    assert "Traceback" not in text(result)


async def test_a_locked_database_is_an_error_result_with_the_reason(mapped, monkeypatch):
    monkeypatch.setattr(map_store, "BUSY_TIMEOUT_MS", 50)
    holder = sqlite3.connect(mapped / "app_memory.db", isolation_level=None)
    holder.execute("PRAGMA journal_mode = DELETE")
    holder.execute("BEGIN EXCLUSIVE")
    try:
        result = await call({})
    finally:
        holder.rollback()
        holder.close()

    assert result.isError
    assert "locked" in text(result)


async def test_a_bad_config_is_an_error_result_with_the_reason(traces, monkeypatch):
    def broken() -> None:
        raise ValueError("Failed to parse 'artemis.jsonc'")

    monkeypatch.setattr(knowledge_tool, "open_knowledge", open_knowledge)
    monkeypatch.setattr(knowledge_service, "load_agent_config", broken)

    result = await call({})

    assert result.isError
    assert "config could not be read" in text(result)
    assert "artemis.jsonc" in text(result)
