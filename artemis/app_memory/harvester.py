import time
from collections.abc import Callable, Iterable

from artemis.app_memory.edges import MapWriter
from artemis.app_memory.models import ObservationStatus, SessionOutcome, Transition
from artemis.app_memory.outcomes import OBSERVATION_STATUS, settled_outcome
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import TraceReader
from artemis.app_memory.transitions import scan


class Harvester:
    """Turns recorded sessions into map observations. Every entry point is idempotent per
    (session_id, step_id): a step that already has an observation is never written again."""

    def __init__(
        self,
        store: MapStore,
        reader: TraceReader,
        excluded: frozenset[str],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._reader = reader
        self._excluded = excluded
        self._clock = clock
        self._resume_at: dict[str, int] = {}

    def harvest_live(self, session_id: str) -> None:
        start = self._resume_at.get(session_id, 0)
        result = scan(self._reader.steps(session_id)[start:], self._excluded)
        self._store.open_session(session_id)
        self._write(session_id, result.transitions)
        self._resume_at[session_id] = start + result.resume_at

    def finalize(self, session_id: str, outcome: SessionOutcome) -> None:
        self._write(session_id, scan(self._reader.steps(session_id), self._excluded).transitions)
        status = OBSERVATION_STATUS[outcome]
        self._store.finalize_session(session_id, outcome, status, self._clock())
        self._resume_at.pop(session_id, None)

    def reconcile(self) -> list[str]:
        finalized = []
        for session_id in self._store.live_sessions():
            outcome = self._settled_outcome(session_id)
            if outcome is not None:
                self.finalize(session_id, outcome)
                finalized.append(session_id)
        return finalized

    def backfill(self, session_id: str) -> SessionOutcome | None:
        outcome = self._settled_outcome(session_id)
        if outcome is None:
            self.harvest_live(session_id)
        else:
            self.finalize(session_id, outcome)
        return outcome

    def _settled_outcome(self, session_id: str) -> SessionOutcome | None:
        session = self._reader.session(session_id)
        return settled_outcome(session, self._store.last_activity(session_id), self._clock())

    def _write(self, session_id: str, transitions: Iterable[Transition]) -> None:
        observed = self._store.observed_steps(session_id)
        writer = MapWriter(self._store, self._excluded)
        for transition in transitions:
            if transition.step.step_id not in observed:
                writer.record(transition, ObservationStatus.PROVISIONAL)
