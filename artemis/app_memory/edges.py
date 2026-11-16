from collections.abc import Sequence

from artemis.app_memory import ids
from artemis.app_memory.abstraction import abstract, match
from artemis.app_memory.actions import is_entry
from artemis.app_memory.models import (
    CanonicalAction,
    EdgeId,
    KnownState,
    MapId,
    ObservationRecord,
    ObservationStatus,
    Sighting,
    StateId,
    Transition,
)
from artemis.app_memory.store import MapStore

ENTRY_SUFFIX = "@entry"


class MapWriter:
    """Writes transitions into per-app maps, splitting the ones that cross apps."""

    def __init__(self, store: MapStore, excluded: frozenset[str]) -> None:
        self._store = store
        self._excluded = excluded
        self._known: dict[MapId, list[KnownState]] = {}

    def record(self, transition: Transition, status: ObservationStatus) -> None:
        step, now = transition.step, transition.step.recorded_at
        src_map = transition.source.screen.map_id
        src = self._state(transition.source, now)
        if transition.destination.screen.map_id == src_map:
            dst = self._state(transition.destination, now)
        else:
            self._record_entry(transition, status)
            dst = self._store.put_outside_state(src_map, now)
        edge = None if dst == src else self._store.put_edge(src_map, src, dst, step.actions, now)
        self._observe(transition, step.step_id, src, step.actions, edge, status)

    def _record_entry(self, transition: Transition, status: ObservationStatus) -> None:
        destination, step, now = (
            transition.destination,
            transition.step,
            transition.step.recorded_at,
        )
        entries = [index for index, action in enumerate(step.actions) if is_entry(action)]
        if not entries or destination.screen.package in self._excluded:
            return
        actions = step.actions[entries[-1] :]
        dst_map = destination.screen.map_id
        outside = self._store.put_outside_state(dst_map, now)
        dst = self._state(destination, now)
        edge = self._store.put_edge(dst_map, outside, dst, actions, now)
        self._observe(transition, step.step_id + ENTRY_SUFFIX, outside, actions, edge, status)

    def _state(self, sighting: Sighting, now: float) -> StateId:
        map_id = sighting.screen.map_id
        screen = abstract(sighting.screen)
        known = self._known.get(map_id)
        if known is None:
            known = self._known[map_id] = self._store.known_states(map_id)
        state_id = match(screen, known)
        if state_id is None:
            ordinal = sum(1 for k in known if k.screen.coarse_key == screen.coarse_key)
            state_id = ids.state_id(map_id, screen.coarse_key, ordinal)
            known.append(KnownState(state_id, screen))
        self._store.put_state(map_id, state_id, screen, now, sighting.sample)
        return state_id

    def _observe(
        self,
        transition: Transition,
        step_key: str,
        src: StateId,
        actions: Sequence[CanonicalAction],
        edge: EdgeId | None,
        status: ObservationStatus,
    ) -> None:
        record = ObservationRecord(
            session_id=transition.source.sample.session_id,
            step_id=step_key,
            src_state_id=src,
            action_signature=ids.action_signature(actions),
            status=status,
            recorded_at=transition.step.recorded_at,
            edge_id=edge,
        )
        self._store.record_observation(record)
