"""AppVersionCache: one listing per run, non-blocking lookups, invalidation after installs."""

from __future__ import annotations

from collections.abc import Callable
import subprocess
from unittest.mock import patch

from artemis.runtime.app_versions import AppVersion, AppVersionCache, adb_shell_runner

LISTING_V34 = (
    "package:com.android.settings versionCode:34\npackage:com.android.chrome versionCode:6100\n"
)
LISTING_V35 = (
    "package:com.android.settings versionCode:35\npackage:com.android.chrome versionCode:6100\n"
)
SETTINGS_DUMP = (
    "Packages:\n"
    "  Package [com.android.settings] (5d2a1c):\n"
    "    versionCode=34 minSdk=34 targetSdk=34\n"
    "    versionName=14\n"
    "Hidden system packages:\n"
    "  Package [com.android.settings] (77aa01):\n"
    "    versionName=13\n"
)


class QueuedExecutor:
    """Holds submitted jobs until the test runs them, so "in flight" is observable."""

    def __init__(self) -> None:
        self.jobs: list[tuple[Callable[..., None], tuple]] = []

    def submit(self, job, *args):
        self.jobs.append((job, args))

    def run_all(self) -> None:
        while self.jobs:
            job, args = self.jobs.pop(0)
            job(*args)

    def shutdown(self, wait=True, *, cancel_futures=False):
        pass


class FakeShell:
    def __init__(self, listings: list[str | None], dumps: dict[str, str] | None = None) -> None:
        self.listings = listings
        self.dumps = dumps or {}
        self.commands: list[str] = []

    def __call__(self, command: str) -> str | None:
        self.commands.append(command)
        if command.startswith("pm list packages"):
            return self.listings.pop(0) if len(self.listings) > 1 else self.listings[0]
        return self.dumps.get(command.removeprefix("dumpsys package "))

    def count(self, prefix: str) -> int:
        return sum(command.startswith(prefix) for command in self.commands)


def _cache(shell: FakeShell) -> tuple[AppVersionCache, QueuedExecutor]:
    executor = QueuedExecutor()
    return AppVersionCache(shell, executor=executor), executor


def test_one_listing_call_per_run():
    shell = FakeShell([LISTING_V34], {"com.android.settings": SETTINGS_DUMP})
    cache, executor = _cache(shell)
    cache.prefetch()
    executor.run_all()

    for package in ["com.android.settings", "com.android.chrome", "com.android.settings"]:
        cache.lookup(package)
        executor.run_all()

    assert shell.count("pm list packages") == 1
    assert cache.lookup("com.android.settings") == AppVersion(code=34, name="14")
    assert cache.lookup("com.android.chrome").code == 6100


def test_lookup_in_flight_gives_none_and_never_waits():
    shell = FakeShell([LISTING_V34], {"com.android.settings": SETTINGS_DUMP})
    cache, executor = _cache(shell)

    assert cache.lookup("com.android.settings") == AppVersion()
    assert shell.commands == []

    executor.run_all()
    assert cache.lookup("com.android.settings") == AppVersion(code=34, name="14")


def test_version_name_is_read_once_per_package():
    shell = FakeShell([LISTING_V34], {"com.android.settings": SETTINGS_DUMP})
    cache, executor = _cache(shell)

    for _ in range(3):
        cache.lookup("com.android.settings")
        executor.run_all()

    assert shell.count("dumpsys package com.android.settings") == 1


def test_install_invalidates_and_the_next_use_reloads():
    shell = FakeShell([LISTING_V34, LISTING_V35])
    cache, executor = _cache(shell)
    cache.lookup("com.android.settings")
    executor.run_all()
    assert cache.lookup("com.android.settings").code == 34

    cache.note_adb_command("pm install -r /data/local/tmp/settings.apk")

    assert cache.lookup("com.android.settings").code is None
    executor.run_all()
    assert cache.lookup("com.android.settings").code == 35
    assert shell.count("pm list packages") == 2


def test_uninstall_also_invalidates_and_other_commands_do_not():
    shell = FakeShell([LISTING_V34, LISTING_V35])
    cache, executor = _cache(shell)
    cache.lookup("com.android.chrome")
    executor.run_all()

    cache.note_adb_command("ls /sdcard")
    assert cache.lookup("com.android.chrome").code == 6100

    cache.note_adb_command("pm uninstall com.android.chrome")
    assert cache.lookup("com.android.chrome").code is None


def test_a_load_started_before_an_install_is_discarded():
    shell = FakeShell([LISTING_V34, LISTING_V35])
    cache, executor = _cache(shell)
    cache.lookup("com.android.settings")

    cache.note_adb_command("cmd package install-existing com.android.settings")
    executor.run_all()

    assert cache.lookup("com.android.settings").code is None
    executor.run_all()
    assert cache.lookup("com.android.settings").code == 35


def test_failed_adb_gives_none_without_retrying():
    shell = FakeShell([None])
    cache, executor = _cache(shell)

    for _ in range(3):
        assert cache.lookup("com.android.settings") == AppVersion()
        executor.run_all()

    assert shell.count("pm list packages") == 1


def test_unknown_or_unsafe_package_runs_nothing():
    shell = FakeShell([LISTING_V34])
    cache, executor = _cache(shell)

    assert cache.lookup(None) == AppVersion()
    assert cache.lookup("x; reboot") == AppVersion()
    assert executor.jobs == []


def test_adb_shell_runner_gives_none_on_timeout():
    with patch(
        "artemis.runtime.app_versions.subprocess.run",
        side_effect=subprocess.TimeoutExpired("adb", 5),
    ):
        assert adb_shell_runner("emulator-5554")("pm list packages") is None
