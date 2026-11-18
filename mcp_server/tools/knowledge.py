# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""MCP Tool: mobile_get_knowledge."""

import sqlite3
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from mcp_server.base import mcp
from mcp_server.utils import env_utils
from artemis.app_memory.knowledge import Knowledge, open_knowledge, render
from artemis.app_memory.knowledge.reports import KnowledgeReport, KnowledgeResponse
from artemis.app_memory.store import VectorExtensionError
from artemis.app_memory.trace_reader import DATA_ENGINE_DB
from artemis.runtime import trace_store

DATABASE_ERRORS = (sqlite3.Error, OSError, VectorExtensionError)


@mcp.tool()
async def mobile_get_knowledge(
    app: str | None = None, query: str | None = None
) -> Annotated[CallToolResult, KnowledgeResponse]:
    """Reports what Engram, the agent behind `mobile_run_task`, has learned about Android apps
    in past runs. Call it before `mobile_run_task`.

    It reads Engram's app maps only. It never touches the device, starts no task and calls no
    LLM; a probe makes one embedding call. It reports only what Engram has seen, not
    everything an app can do.

    The arguments pick the report:
    - No arguments: the apps Engram has mapped, each with its package, `version_code` and
      recommended profile.
    - `app` only: what Engram has seen in that app (pages, capabilities, example goals). An
      app with no map comes back with level `not_mapped`, which is not an error.
    - `query`, with or without `app`: a probe of whether Engram knows a route for that goal,
      with the closest pages and their similarity. Similarity is not a promise that the task
      will succeed.

    Only the Pro profile uses these routes; Flash does not. The text ends with what to do
    next, and the structured content holds the same report under its `level`.

    Args:
        app: Android package name, e.g. "com.android.settings". The no-argument report lists
          the known packages.
        query: A goal worded as you would give it to `mobile_run_task`, e.g. "turn on dark
          theme". With `app`, the probe searches only that app.
    """
    try:
        with _open() as knowledge:
            report = await _report(knowledge, _present(app), _present(query))
    except DATABASE_ERRORS as exc:
        raise ToolError(f"Engram's app-memory database could not be read: {exc}") from exc
    return CallToolResult(
        content=[TextContent(type="text", text=render(report))],
        structuredContent=KnowledgeResponse.of(report).model_dump(mode="json"),
    )


def _open() -> Knowledge:
    try:
        return open_knowledge(_traces_dir())
    except ValueError as exc:
        raise ToolError(f"Engram's config could not be read: {exc}") from exc


async def _report(knowledge: Knowledge, app: str | None, query: str | None) -> KnowledgeReport:
    if query is not None:
        return await knowledge.probe(query, app)
    if app is not None:
        return knowledge.capabilities(app)
    return knowledge.overview()


def _present(value: str | None) -> str | None:
    return (value or "").strip() or None


def _traces_dir() -> Path:
    """The directory `mobile_inspect_trace` reads, so both tools see the same runs."""
    configured = Path(trace_store.TRACES_DIR)
    fallback = Path(env_utils.get_project_root()) / "traces"
    if not (configured / DATA_ENGINE_DB).exists() and (fallback / DATA_ENGINE_DB).exists():
        return fallback
    return configured
