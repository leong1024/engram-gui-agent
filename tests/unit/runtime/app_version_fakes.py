"""Fakes for AppVersionCache: a shell that answers adb commands and a step-wise executor."""

from __future__ import annotations

from collections.abc import Callable

LISTING_V34 = (
    "package:com.android.settings versionCode:34\npackage:com.android.chrome versionCode:6100\n"
)
LISTING_V35 = (
    "package:com.android.settings versionCode:35\npackage:com.android.chrome versionCode:6100\n"
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
