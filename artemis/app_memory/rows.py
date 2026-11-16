import json
from collections.abc import Iterable, Sequence
from typing import Any

from artemis.app_memory.documents import endpoint_title, loads_list
from artemis.app_memory.map_graph import GraphEdge, StateCard, Tally
from artemis.app_memory.models import (
    AbstractScreen,
    ActionKind,
    ActionSignature,
    CanonicalAction,
    EdgeId,
    KnownState,
    MapId,
    MapStats,
    ObservationRecord,
    ObservationStatus,
    StateId,
    StateSample,
    TargetDescriptor,
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


def known_from_rows(rows: Iterable[Sequence[Any]]) -> tuple[KnownState, ...]:
    return tuple(KnownState(StateId(row[0]), screen_from_row(row[1:])) for row in rows)


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


def card_from_row(row: Sequence[Any]) -> StateCard:
    state_id, title, purpose, affordances, activity, tokens, is_opaque, is_virtual, visits = row
    return StateCard(
        state_id=StateId(state_id),
        title=endpoint_title(title, bool(is_virtual)),
        purpose=purpose or "",
        affordances=tuple(str(a) for a in loads_list(affordances)),
        activity=activity,
        static_tokens=tuple(str(t) for t in loads_list(tokens)),
        is_opaque=bool(is_opaque),
        is_virtual=bool(is_virtual),
        visits=visits,
    )


def edge_from_row(row: Sequence[Any]) -> GraphEdge:
    edge_id, src, dst, signature, actions, description, last_seen_at = row
    return GraphEdge(
        edge_id=EdgeId(edge_id),
        src=StateId(src),
        dst=StateId(dst),
        signature=ActionSignature(signature),
        actions=tuple(action_from_dict(a) for a in loads_list(actions)),
        description=description,
        last_seen_at=last_seen_at,
    )


def tally_from_row(row: Sequence[Any]) -> Tally:
    src, signature, edge_id, status, count = row
    edge = EdgeId(edge_id) if edge_id is not None else None
    return Tally(StateId(src), ActionSignature(signature), edge, ObservationStatus(status), count)


def action_from_dict(raw: dict[str, Any]) -> CanonicalAction:
    target = raw.get("target")
    return CanonicalAction(
        kind=ActionKind(raw["kind"]),
        target=_target_from_dict(target) if target else None,
        params=raw.get("params") or {},
        input_slot=raw.get("input_slot"),
    )


def _target_from_dict(raw: dict[str, Any]) -> TargetDescriptor:
    bounds = raw.get("rel_bounds")
    return TargetDescriptor(
        resource_id=raw.get("resource_id"),
        text=raw.get("text"),
        content_desc=raw.get("content_desc"),
        class_name=raw.get("class"),
        rel_bounds=tuple(bounds) if bounds else None,
        target_description=raw.get("target_description"),
    )
