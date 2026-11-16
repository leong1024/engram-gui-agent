from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from artemis.app_memory.abstraction.masking import mask_text
from artemis.app_memory.models import ActionKind, CanonicalAction, TargetDescriptor
from artemis.mcp.action_names import OPERATOR_ACTION_TO_CANONICAL

WAIT = "wait_for_delay"
DISPATCHED = "dispatched"
TEXT_SLOT = "text"

Params = dict[str, str | int | bool]


@dataclass(frozen=True, slots=True)
class StepActions:
    actions: tuple[CanonicalAction, ...]
    is_wait: bool


NO_ACTIONS = StepActions((), is_wait=False)


def step_actions(action_taken: Any, execution_status: str | None) -> StepActions:
    """The device actions a recorded step executed, reduced to their canonical form."""
    items = _items(action_taken)
    verbs = [_verb(item) for item in items]
    if verbs and all(verb == WAIT for verb in verbs):
        return StepActions((), is_wait=True)
    if execution_status != DISPATCHED or not items:
        return NO_ACTIONS
    actions = [_canonical(verb, item) for verb, item in zip(verbs, items) if verb != WAIT]
    if any(action is None for action in actions):
        return NO_ACTIONS
    return StepActions(tuple(a for a in actions if a is not None), is_wait=False)


def is_entry(action: CanonicalAction) -> bool:
    return action.kind is ActionKind.OPEN_LINK or (
        action.kind is ActionKind.MANAGE_APP and action.params.get("action") == "launch"
    )


def _items(action_taken: Any) -> list[Mapping[str, Any]]:
    raw = action_taken if isinstance(action_taken, list) else [action_taken]
    return [item for item in raw if isinstance(item, Mapping)]


def _verb(item: Mapping[str, Any]) -> str:
    return str(item.get("action") or item.get("name") or "")


def _canonical(verb: str, item: Mapping[str, Any]) -> CanonicalAction | None:
    kind = _KINDS.get(OPERATOR_ACTION_TO_CANONICAL.get(verb, verb))
    if kind is None:
        return None
    fields = {**item, **(item.get("args") or {})}
    return CanonicalAction(
        kind=kind,
        target=_target(fields) if kind in _TARGETED else None,
        params=_PARAMS[kind](verb, fields),
        input_slot=TEXT_SLOT if kind is ActionKind.INPUT_TEXT else None,
    )


def _target(fields: Mapping[str, Any]) -> TargetDescriptor | None:
    text = fields.get("target_text")
    descriptor = {
        "resource_id": fields.get("target_resource_id") or None,
        "text": mask_text(text) if isinstance(text, str) and text else None,
        "class_name": fields.get("target_class") or None,
        "target_description": fields.get("target_description") or None,
    }
    if descriptor["target_description"]:
        descriptor["rel_bounds"] = _point_bounds(fields.get("normalized_coordinates"))
    if not any(descriptor.values()):
        return None
    return TargetDescriptor(**descriptor)


def _point_bounds(point: Any) -> tuple[int, int, int, int] | None:
    if isinstance(point, list | tuple) and len(point) == 2:
        x, y = int(point[0]), int(point[1])
        return x, y, x, y
    return None


def _no_params(verb: str, fields: Mapping[str, Any]) -> Params:
    return {}


def _swipe_params(verb: str, fields: Mapping[str, Any]) -> Params:
    direction = fields.get("direction") or fields.get("gesture")
    return {"direction": direction} if isinstance(direction, str) else {}


def _key_params(verb: str, fields: Mapping[str, Any]) -> Params:
    key = verb if verb == "back" else str(fields.get("key") or fields.get("keycode") or "")
    return {"key": key.removeprefix("KEYCODE_").lower()}


def _app_params(verb: str, fields: Mapping[str, Any]) -> Params:
    mode = {"launch_app": "launch", "stop_app": "stop"}.get(verb) or fields.get("action")
    return {"action": str(mode), "package": str(fields.get("app_name") or "")}


def _link_params(verb: str, fields: Mapping[str, Any]) -> Params:
    return {"host": urlparse(str(fields.get("url") or "")).netloc}


_KINDS: Mapping[str, ActionKind] = {kind.value: kind for kind in ActionKind}

_TARGETED = frozenset(
    {ActionKind.CLICK, ActionKind.LONG_PRESS, ActionKind.INPUT_TEXT, ActionKind.SWIPE}
)

_PARAMS: Mapping[ActionKind, Callable[[str, Mapping[str, Any]], Params]] = {
    ActionKind.CLICK: _no_params,
    ActionKind.LONG_PRESS: _no_params,
    ActionKind.INPUT_TEXT: _no_params,
    ActionKind.SWIPE: _swipe_params,
    ActionKind.PRESS_KEY: _key_params,
    ActionKind.MANAGE_APP: _app_params,
    ActionKind.OPEN_LINK: _link_params,
}
