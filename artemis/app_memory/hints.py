from collections.abc import Callable, Mapping

from artemis.app_memory.map_graph import StateCard
from artemis.app_memory.models import ActionKind, CanonicalAction, TargetDescriptor
from artemis.app_memory.routing.types import HintNote, Hop, Route, RouteKind

HEADER = "--- App Memory: Known Route (advisory) ---"
FOOTER = (
    "Check that each screen matches before taking the next hop. If the screen does not match,\n"
    "ignore this route and continue normally."
)
ARRIVED_LINE = "You are on the target screen for this milestone."
BORROWED_LINE = "Learned on an older app version (v{version}); screens may differ."
NOTE_LINES: Mapping[HintNote, str] = {
    HintNote.REROUTED: "Rerouted from the current screen.",
    HintNote.UNRECOGNISED: "Current screen not recognised; this route may not apply.",
}
LEAD_LINES: Mapping[RouteKind, str] = {
    RouteKind.FROM_STATE: 'From the current screen ("{source}"):',
    RouteKind.FROM_OUTSIDE: "From outside the app:",
    RouteKind.FROM_LAUNCH: "Not on a known screen; route from app launch:",
}
MAX_RENDERED_HOPS = 8
MAX_SIGNATURE_TOKENS = 3
MASK_MARK = "<"
ARROW = "→"


def render(route: Route) -> str:
    return "\n".join(RENDERERS[route.kind](route))


def _render_route(route: Route) -> list[str]:
    lead = LEAD_LINES[route.kind].format(source=route.source.title)
    lines = [*_target_lines(route), _seen_line(route), *_note_lines(route), lead]
    return [*lines, *_hop_lines(route.hops), FOOTER]


def _render_no_path(route: Route) -> list[str]:
    return [*_target_lines(route), *_note_lines(route)]


def _render_arrived(route: Route) -> list[str]:
    return [HEADER, f"Milestone: {route.milestone.text}", ARRIVED_LINE]


RENDERERS: Mapping[RouteKind, Callable[[Route], list[str]]] = {
    RouteKind.FROM_STATE: _render_route,
    RouteKind.FROM_OUTSIDE: _render_route,
    RouteKind.FROM_LAUNCH: _render_route,
    RouteKind.NO_PATH: _render_no_path,
    RouteKind.ARRIVED: _render_arrived,
}


def _target_lines(route: Route) -> list[str]:
    target, map_id = route.target, route.map_id
    purpose = f" — {target.purpose}" if target.purpose else ""
    app = f"{map_id.package} v{map_id.version_code}"
    return [
        HEADER,
        f"Milestone: {route.milestone.text}",
        f'Target screen: "{target.title}" ({app}){purpose}',
    ]


def _seen_line(route: Route) -> str:
    visits = route.target.visits
    return (
        f"Seen {visits} time{'' if visits == 1 else 's'}. Route confidence {route.confidence:.2f}."
    )


def _note_lines(route: Route) -> list[str]:
    borrowed = [BORROWED_LINE.format(version=route.map_id.version_code)] if route.borrowed else []
    return [*borrowed, *(NOTE_LINES[note] for note in route.notes)]


def _hop_lines(hops: tuple[Hop, ...]) -> list[str]:
    shown = hops[:MAX_RENDERED_HOPS]
    actions = [", then ".join(_action(a) for a in hop.actions) for hop in shown]
    width = max(len(text) for text in actions)
    lines = [
        f"  {index}. {text.ljust(width)} {ARROW} {_expectation(hop, last=index == len(hops))}"
        for index, (text, hop) in enumerate(zip(actions, shown, strict=True), start=1)
    ]
    hidden = len(hops) - len(shown)
    return [*lines, f"  (+{hidden} more)"] if hidden else lines


def _expectation(hop: Hop, last: bool) -> str:
    return "target reached" if last else f'expect "{hop.to_state.title}"{_signature(hop.to_state)}'


def _signature(state: StateCard) -> str:
    """The short activity name and a few fixed labels, to compare with the live screen."""
    activity = (state.activity or "").rsplit(".", 1)[-1]
    labels = [t for t in state.static_tokens if MASK_MARK not in t]
    labels.sort(key=lambda t: ("_" in t, t))
    quoted = ", ".join(f'"{t}"' for t in labels[:MAX_SIGNATURE_TOKENS])
    parts = "; ".join(part for part in (activity, quoted) if part)
    return f" [{parts}]" if parts else ""


def _action(action: CanonicalAction) -> str:
    return ACTION_PHRASES[action.kind](action)


def _target(action: CanonicalAction) -> str:
    """A label to find on the live screen. Coordinates are never shown."""
    target = action.target
    if target is None:
        return "the screen"
    label = target.text or target.content_desc
    if label:
        return f'"{label}"{_qualifier(target)}'
    if target.resource_id:
        return f"the element with id {_short_id(target.resource_id)}"
    return f'the element described as "{target.target_description}"'


def _qualifier(target: TargetDescriptor) -> str:
    if target.resource_id:
        return f" (id: {_short_id(target.resource_id)})"
    if target.class_name:
        return f" ({target.class_name.rsplit('.', 1)[-1].lower()})"
    return ""


def _short_id(resource_id: str) -> str:
    return resource_id.rsplit("/", 1)[-1]


def _param(action: CanonicalAction, name: str) -> str:
    return str(action.params.get(name, ""))


ACTION_PHRASES: Mapping[ActionKind, Callable[[CanonicalAction], str]] = {
    ActionKind.CLICK: lambda a: f"Tap {_target(a)}",
    ActionKind.LONG_PRESS: lambda a: f"Long-press {_target(a)}",
    ActionKind.INPUT_TEXT: lambda a: f"Type the {a.input_slot or 'text'} into {_target(a)}",
    ActionKind.SWIPE: lambda a: f"Swipe {_param(a, 'direction') or 'across'} on {_target(a)}",
    ActionKind.PRESS_KEY: lambda a: f"Press {_param(a, 'key')}",
    ActionKind.MANAGE_APP: lambda a: (
        f"{_param(a, 'action').title()} the app {_param(a, 'package')}"
    ),
    ActionKind.OPEN_LINK: lambda a: f"Open a link to {_param(a, 'host')}",
}
