from typing import Any, Protocol


class AppMemoryService(Protocol):
    def on_event(self, event_type: str, data: Any) -> None: ...
    def on_step_recorded(self, session_id: str) -> None: ...
    async def prepare_run(self, *, device_serial: str | None) -> None: ...
    async def finalize_session(self, session_id: str, outcome: str) -> None: ...
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

    async def close(self) -> None:
        return None
