from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from artemis.app_memory.milestones import Milestone
    from artemis.app_memory.models import ScreenObservation
    from artemis.app_memory.routing import Route


class AppMemoryService(Protocol):
    def on_event(self, event_type: str, data: Any) -> None: ...
    def on_step_recorded(self, session_id: str) -> None: ...
    async def prepare_run(self, *, device_serial: str | None) -> None: ...
    async def finalize_session(self, session_id: str, outcome: str) -> None: ...
    def request_targets(self, goal: str, milestones: "Sequence[Milestone]") -> None: ...
    def route_for(self, milestone_key: str, observation: "ScreenObservation") -> "Route | None": ...
    async def close(self) -> None: ...


class NoopAppMemory:
    """App memory when it is disabled, so call sites never check."""

    def on_event(self, event_type: str, data: Any) -> None:
        return None

    def on_step_recorded(self, session_id: str) -> None:
        return None

    async def prepare_run(self, *, device_serial: str | None) -> None:
        return None

    async def finalize_session(self, session_id: str, outcome: str) -> None:
        return None

    def request_targets(self, goal: str, milestones: "Sequence[Milestone]") -> None:
        return None

    def route_for(self, milestone_key: str, observation: "ScreenObservation") -> "Route | None":
        return None

    async def close(self) -> None:
        return None
