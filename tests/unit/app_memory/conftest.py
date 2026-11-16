from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from artemis.app_memory.abstraction import abstract
from artemis.app_memory.abstraction.constants import SYSTEM_UI_PACKAGES
from artemis.app_memory.harvester import Harvester
from artemis.app_memory.models import AbstractScreen, ScreenObservation
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import TraceReader
from tests.unit.app_memory.fixtures.sessions import NOW
from tests.unit.app_memory.fixtures.traces import MapView, Trace


def observe(
    elements: list[dict[str, Any]],
    *,
    package: str = "com.android.settings",
    activity: str | None = ".Settings",
    dhash: str | None = None,
) -> ScreenObservation:
    return ScreenObservation(
        package=package,
        activity=activity,
        version_code=1,
        elements=tuple(elements),
        dhash=dhash,
    )


@pytest.fixture
def abstract_of() -> Callable[..., AbstractScreen]:
    def build(elements: list[dict[str, Any]], **kwargs: Any) -> AbstractScreen:
        return abstract(observe(elements, **kwargs))

    return build


@pytest.fixture
def trace(tmp_path: Path) -> Trace:
    return Trace(tmp_path)


@pytest.fixture
def harvest(trace: Trace):
    stores: list[MapStore] = []

    def open_harvester(clock: float = NOW) -> Harvester:
        store = MapStore.open(trace.root / "app_memory.db")
        stores.append(store)
        reader = TraceReader(trace.storage, trace.root)
        return Harvester(store, reader, SYSTEM_UI_PACKAGES, clock=lambda: clock)

    yield open_harvester
    for store in stores:
        store.close()


@pytest.fixture
def view(trace: Trace) -> MapView:
    return MapView(trace.root / "app_memory.db")
