from collections.abc import Mapping
from dataclasses import dataclass

from artemis.app_memory.models import ObservationStatus, SessionOutcome

STALE_AFTER_SECONDS = 6 * 3600

OBSERVATION_STATUS: Mapping[SessionOutcome, ObservationStatus] = {
    SessionOutcome.COMPLETED: ObservationStatus.CONFIRMED,
    SessionOutcome.PARTIAL: ObservationStatus.DISCOUNTED,
    SessionOutcome.BLOCKED: ObservationStatus.DISCOUNTED,
    SessionOutcome.FAILED: ObservationStatus.DISCOUNTED,
    SessionOutcome.CANCELLED: ObservationStatus.DISCOUNTED,
}

_OUTCOMES: Mapping[str, SessionOutcome] = {outcome.value: outcome for outcome in SessionOutcome}
_SESSION_STATUSES: Mapping[str, SessionOutcome] = {**_OUTCOMES, "success": SessionOutcome.COMPLETED}
_RUN_REFINEMENTS = frozenset({SessionOutcome.PARTIAL, SessionOutcome.BLOCKED})
_LIVE_STATUSES = frozenset({"running", "paused"})


@dataclass(frozen=True, slots=True)
class TraceSession:
    status: str
    started_at: float
    process_alive: bool
    run_task_status: str | None = None

    @property
    def is_live(self) -> bool:
        return self.status in _LIVE_STATUSES


def parse_outcome(status: str, run_task_status: str | None = None) -> SessionOutcome:
    outcome = _SESSION_STATUSES.get(status, SessionOutcome.FAILED)
    refined = _OUTCOMES.get(run_task_status or "", outcome)
    return (
        refined if outcome is SessionOutcome.COMPLETED and refined in _RUN_REFINEMENTS else outcome
    )


def settled_outcome(
    session: TraceSession | None, last_activity: float | None, now: float
) -> SessionOutcome | None:
    """The outcome a session ended with, or None while it may still be running."""
    if session is None:
        stale = last_activity is None or now - last_activity > STALE_AFTER_SECONDS
        return SessionOutcome.FAILED if stale else None
    if not session.is_live:
        return parse_outcome(session.status, session.run_task_status)
    if not session.process_alive or now - session.started_at > STALE_AFTER_SECONDS:
        return SessionOutcome.FAILED
    return None
