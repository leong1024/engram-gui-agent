"""The helper's snapshot ``activity`` reaches the screen data the recorder reads."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from artemis.clients.accessibility_client import AccessibilityClient
from artemis.runtime.helper_manager import HelperSession

SNAPSHOT = json.loads(
    (Path(__file__).parent / "fixtures" / "helper_snapshot_settings.json").read_text()
)


class _Manager:
    session = HelperSession(
        serial="dev",
        local_port=41000,
        transport_id="3",
        version_code=6,
        version_name="1.2.0",
        owns_forward=True,
        token="a" * 48,
        protocol_version=2,
    )

    def attach(self, serial, *, provision=True, on_event=None):
        return self.session


def _screen_data(snapshot: dict[str, Any]):
    response = MagicMock()
    response.read.return_value = json.dumps(snapshot).encode()
    response.__enter__.return_value = response
    with (
        patch("artemis.clients.accessibility_client.ensure_device_awake", return_value=None),
        patch(
            "artemis.clients.accessibility_client.urllib.request.urlopen",
            return_value=response,
        ),
    ):
        return AccessibilityClient("dev", manager=_Manager()).get_screen_data()


def _dumpsys(**kwargs):
    return patch("artemis.clients.accessibility_client.subprocess.run", **kwargs)


def test_recorded_snapshot_activity_is_on_the_screen_data():
    with _dumpsys() as run:
        data = _screen_data(SNAPSHOT)

    assert data.activity == "com.android.settings.Settings"
    assert data.ui_backend == "helper"
    run.assert_not_called()


WITHOUT_ACTIVITY = pytest.mark.parametrize(
    "snapshot",
    [
        {k: v for k, v in SNAPSHOT.items() if k != "activity"},
        {**SNAPSHOT, "activity": ""},
    ],
    ids=["older-helper-without-activity", "no-window-change-yet"],
)


@WITHOUT_ACTIVITY
def test_snapshot_without_an_activity_falls_back_to_dumpsys(snapshot):
    dump = "  topResumedActivity=ActivityRecord{5d2a1c u0 com.android.settings/.Settings t12}\n"
    with _dumpsys(return_value=subprocess.CompletedProcess([], 0, stdout=dump)) as run:
        data = _screen_data(snapshot)

    assert data.activity == "com.android.settings.Settings"
    assert run.call_args.kwargs["timeout"] == 1.0


@WITHOUT_ACTIVITY
def test_no_activity_anywhere_gives_none(snapshot):
    with _dumpsys(side_effect=subprocess.TimeoutExpired("adb", 1.0)):
        assert _screen_data(snapshot).activity is None


def test_activity_survives_the_adb_screencap_path():
    snapshot = {**SNAPSHOT, "has_screenshot": False, "screenshot_base64": None}
    screenshot = MagicMock(width=1080, height=2400)
    with (
        patch.object(AccessibilityClient, "get_screenshot", return_value=screenshot),
        patch("artemis.clients.accessibility_client.pil_to_base64", return_value="QUJD"),
    ):
        data = _screen_data(snapshot)

    assert data.activity == "com.android.settings.Settings"
    assert data.ui_backend == "helper"
