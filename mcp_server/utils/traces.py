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

"""Where the MCP tools read recorded runs from."""

from pathlib import Path

from mcp_server.utils import env_utils
from artemis.app_memory.trace_reader import DATA_ENGINE_DB
from artemis.runtime import trace_store


def resolve_traces_dir() -> Path:
    """The configured traces directory, or the project's `traces/` when only that one holds
    a `data_engine.db`."""
    configured = Path(trace_store.TRACES_DIR)
    fallback = Path(env_utils.get_project_root()) / "traces"
    if not (configured / DATA_ENGINE_DB).exists() and (fallback / DATA_ENGINE_DB).exists():
        return fallback
    return configured
