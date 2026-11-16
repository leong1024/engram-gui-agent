import json
from collections.abc import Sequence
from typing import Any

from artemis.app_memory.models import (
    AbstractScreen,
    MapId,
    MapStats,
    ObservationRecord,
    StateId,
    StateSample,
)


def map_key(map_id: MapId) -> tuple[str, int]:
    return map_id.package, map_id.version_code


def state_params(
    map_id: MapId,
    state_id: StateId,
    screen: AbstractScreen,
    now: float,
    sample: StateSample | None,
) -> tuple[object, ...]:
    return (
        state_id,
        *map_key(map_id),
        screen.activity,
        screen.coarse_key,
        json.dumps(screen.skeleton),
        json.dumps(sorted(screen.static_tokens)),
        screen.is_opaque,
        screen.dhash,
        sample.session_id if sample else None,
        sample.step_id if sample else None,
        sample.image_sha if sample else None,
        now,
        now,
    )


def screen_from_row(row: Sequence[Any]) -> AbstractScreen:
    activity, coarse_key, skeleton, static_tokens, is_opaque, dhash = row
    return AbstractScreen(
        activity=activity,
        coarse_key=coarse_key,
        skeleton=tuple(json.loads(skeleton)),
        static_tokens=frozenset(json.loads(static_tokens)),
        is_opaque=bool(is_opaque),
        dhash=dhash,
    )


def observation_params(record: ObservationRecord) -> tuple[object, ...]:
    return (
        record.session_id,
        record.step_id,
        record.edge_id,
        record.src_state_id,
        record.action_signature,
        record.status.value,
        record.recorded_at,
    )


def stats_from_row(row: Sequence[Any]) -> MapStats:
    package, version_code, states, edges, *counts = row
    return MapStats(MapId(package, version_code), states, edges, *counts)
