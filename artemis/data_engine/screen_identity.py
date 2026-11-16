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

"""What a recorded step says about the screen it acted on.

A screen's identity is captured when it is observed, keyed by its image hash, so a
step stamps the identity of its own pre-action screen rather than whatever the device
shows when the step is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from artemis.runtime.app_versions import AppVersion


class ScreenSource(Protocol):
    """The identity fields of a screen capture (``ScreenDataResponse`` has them)."""

    activity: str | None
    ui_backend: str | None


@dataclass(frozen=True)
class ObservedScreen:
    activity: str | None
    ui_backend: str | None
    foreground_app: str | None


def screen_identity_fields(screen: ObservedScreen | None, version: AppVersion) -> dict[str, Any]:
    """The step's ``extra_metadata`` keys; every unknown value is None."""
    return {
        "activity": screen.activity if screen else None,
        "version_code": version.code,
        "version_name": version.name,
        "ui_backend": screen.ui_backend if screen else None,
    }
