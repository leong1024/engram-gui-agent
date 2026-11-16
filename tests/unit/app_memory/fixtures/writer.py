from pathlib import Path

from artemis.app_memory import ids
from artemis.app_memory.models import (
    ActionKind,
    CanonicalAction,
    EdgeId,
    ObservationRecord,
    ObservationStatus,
    StateId,
    TargetDescriptor,
)
from artemis.app_memory.store import MapStore


def click(text: str) -> CanonicalAction:
    return CanonicalAction(ActionKind.CLICK, TargetDescriptor(text=text))


def make_observation(
    step: int,
    edge: EdgeId | None,
    src: StateId,
    status: ObservationStatus,
    session: str = "s1",
) -> ObservationRecord:
    return ObservationRecord(
        session_id=session,
        step_id=str(step),
        src_state_id=src,
        action_signature=ids.action_signature([click("Battery")]),
        status=status,
        recorded_at=float(step),
        edge_id=edge,
    )


def write_confirmed(path: str, session: str, edge: str, src: str, count: int) -> None:
    writer = MapStore.open(Path(path))
    try:
        for step in range(count):
            record = make_observation(
                step, EdgeId(edge), StateId(src), ObservationStatus.CONFIRMED, session
            )
            writer.record_observation(record)
    finally:
        writer.close()
