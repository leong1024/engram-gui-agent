"""The UIAutomator backend reads the resumed activity from ``dumpsys``, capped at 1 s."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
import pytest
import uiautomator2 as u2

from third_party.mobile_use.clients.ui_automator_client import UIAutomatorClient

XML = '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0"></hierarchy>'


def _screen_data(shell: MagicMock):
    device = MagicMock()
    device.dump_hierarchy.return_value = XML
    device.shell = shell
    client = UIAutomatorClient("dev")
    with (
        patch.object(client, "_ensure_connected", return_value=device),
        patch.object(client, "get_screenshot", return_value=Image.new("RGB", (4, 8))),
    ):
        return client.get_screen_data()


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ("com.android.settings/.Settings", "com.android.settings.Settings"),
        (
            "com.android.settings/com.android.settings.SubSettings",
            "com.android.settings.SubSettings",
        ),
    ],
)
def test_resumed_activity_is_recorded_fully_qualified(record, expected):
    dump = f"    topResumedActivity=ActivityRecord{{5d2a1c u0 {record} t12}}\n"
    shell = MagicMock(return_value=SimpleNamespace(output=dump, exit_code=0))

    data = _screen_data(shell)

    assert data.activity == expected
    assert data.ui_backend == "uiautomator"
    assert shell.call_args.kwargs["timeout"] == 1.0


def test_dumpsys_failure_still_returns_the_screen_with_no_activity():
    shell = MagicMock(side_effect=u2.exceptions.AdbShellError("timeout"))

    data = _screen_data(shell)

    assert data.activity is None
    assert data.width == 4 and data.height == 8
