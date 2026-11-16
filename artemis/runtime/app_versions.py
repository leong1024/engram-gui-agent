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

"""Installed app versions on the run's device, looked up without blocking the caller."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
import re
import subprocess
import threading

from artemis.runtime.adb_endpoint import adb_command
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)

#: Runs one ``adb shell`` command line and returns its stdout, or None when it failed.
ShellRunner = Callable[[str], "str | None"]

_LIST_VERSIONS_CMD = "pm list packages --show-versioncode"
_LISTING_RE = re.compile(r"^package:(?P<package>\S+) versionCode:(?P<code>\d+)", re.MULTILINE)
_VERSION_NAME_RE = re.compile(r"\bversionName=(?P<name>\S+)")
_PACKAGE_RE = re.compile(r"^[A-Za-z][\w.]*$")
_SHELL_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class AppVersion:
    code: int | None = None
    name: str | None = None


def parse_version_codes(listing: str) -> dict[str, int]:
    """``package:<pkg> versionCode:<n>`` lines from ``pm list packages --show-versioncode``."""
    return {m["package"]: int(m["code"]) for m in _LISTING_RE.finditer(listing)}


def parse_version_name(dump: str) -> str | None:
    """The first ``versionName=`` in ``dumpsys package <pkg>``: the installed one.

    An updated system app also lists its factory version later, under
    "Hidden system packages".
    """
    match = _VERSION_NAME_RE.search(dump)
    return match["name"] if match else None


class AppVersionCache:
    """Per-run versions of installed packages.

    One ``pm list packages`` call fills every versionCode. A package's versionName is
    read with ``dumpsys package`` the first time the package is looked up. All adb work
    runs on one background worker, so :meth:`lookup` answers from what is already
    known and gives None for anything still in flight.
    """

    def __init__(self, shell: ShellRunner, executor: Executor | None = None) -> None:
        self._shell = shell
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="app-versions"
        )
        self._lock = threading.Lock()
        self._generation = 0
        self._codes: dict[str, int] | None = None
        self._codes_requested = False
        self._names: dict[str, str | None] = {}
        self._names_requested: set[str] = set()

    def prefetch(self) -> None:
        """Start the versionCode listing now, so the first step finds it loaded."""
        with self._lock:
            self._request_codes()

    def lookup(self, package: str | None) -> AppVersion:
        if not package or not _PACKAGE_RE.match(package):
            return AppVersion()
        with self._lock:
            self._request_codes()
            if package not in self._names_requested:
                self._names_requested.add(package)
                self._submit(self._load_name, package, self._generation)
            code = (self._codes or {}).get(package)
            return AppVersion(code=code, name=self._names.get(package))

    def note_adb_command(self, command: str) -> None:
        """Forget every version after a command that may install or remove a package."""
        if "install" not in command:
            return
        with self._lock:
            self._generation += 1
            self._codes = None
            self._codes_requested = False
            self._names.clear()
            self._names_requested.clear()
        logger.info(f"App version cache invalidated after adb command: {command!r}")

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _request_codes(self) -> None:
        if not self._codes_requested:
            self._codes_requested = True
            self._submit(self._load_codes, self._generation)

    def _submit(self, job: Callable[..., None], *args: object) -> None:
        try:
            self._executor.submit(job, *args)
        except RuntimeError as exc:
            logger.debug(f"App version lookup skipped, the cache is closed: {exc}")

    def _load_codes(self, generation: int) -> None:
        codes = parse_version_codes(self._shell(_LIST_VERSIONS_CMD) or "")
        with self._lock:
            if generation == self._generation:
                self._codes = codes

    def _load_name(self, package: str, generation: int) -> None:
        name = parse_version_name(self._shell(f"dumpsys package {package}") or "")
        with self._lock:
            if generation == self._generation:
                self._names[package] = name


def adb_shell_runner(serial: str, timeout: float = _SHELL_TIMEOUT_S) -> ShellRunner:
    def run(command: str) -> str | None:
        try:
            result = subprocess.run(
                adb_command(["-s", serial, "shell", command]),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            logger.debug(f"adb shell {command!r} on {serial} failed: {exc}")
            return None
        return result.stdout

    return run
