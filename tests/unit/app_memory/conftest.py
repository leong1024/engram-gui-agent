from collections.abc import Callable
from typing import Any

import pytest

from artemis.app_memory.abstraction import abstract
from artemis.app_memory.models import AbstractScreen, ScreenObservation


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
