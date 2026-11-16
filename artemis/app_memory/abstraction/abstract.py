import hashlib

from artemis.app_memory.abstraction.constants import MIN_NON_LIST_ELEMENTS, TAB_PREFIX
from artemis.app_memory.abstraction.elements import Element, parse_elements
from artemis.app_memory.abstraction.masking import mask_element
from artemis.app_memory.abstraction.structure import (
    overlay_markers,
    screen_elements,
    selected_tab_labels,
    split_list_items,
)
from artemis.app_memory.models import AbstractScreen, ScreenObservation

OPAQUE_MARKER = "@opaque"
LIST_FLAG = "list"


def abstract(observation: ScreenObservation) -> AbstractScreen:
    visible = screen_elements(parse_elements(observation.elements), observation.screen_size)
    overlays = overlay_markers(visible)
    tabs = selected_tab_labels(visible)
    kept, containers = split_list_items([mask_element(e) for e in visible])
    is_opaque = len(kept) < MIN_NON_LIST_ELEMENTS
    skeleton = _skeleton(kept, containers, overlays, tabs)
    return AbstractScreen(
        activity=observation.activity,
        coarse_key=_coarse_key(observation, kept, overlays, tabs, is_opaque),
        skeleton=skeleton,
        static_tokens=_static_tokens(kept),
        is_opaque=is_opaque,
        dhash=observation.dhash,
        ocr_tokens=observation.ocr_tokens,
    )


def _flags(element: Element) -> str:
    pairs = (
        ("c", element.clickable),
        ("s", element.scrollable),
        ("e", element.editable),
        ("k", element.checkable),
        ("x", element.selected),
    )
    return "".join(code for code, on in pairs if on)


def _skeleton(
    kept: list[Element],
    containers: list[Element],
    overlays: tuple[str, ...],
    tabs: tuple[str, ...],
) -> tuple[str, ...]:
    ids = {id(c) for c in containers}
    tokens = [
        f"{e.class_name}|{e.resource_id}|{LIST_FLAG if id(e) in ids else _flags(e)}" for e in kept
    ]
    tokens += overlays
    tokens += (f"{TAB_PREFIX}{label}" for label in tabs)
    return tuple(sorted(tokens))


def _static_tokens(kept: list[Element]) -> frozenset[str]:
    tokens: set[str] = set()
    for element in kept:
        tokens.update(t for t in (element.text, element.content_desc) if t)
        if element.resource_id:
            tokens.add(element.resource_id.rsplit("/", 1)[-1])
    return frozenset(tokens)


def _coarse_key(
    observation: ScreenObservation,
    kept: list[Element],
    overlays: tuple[str, ...],
    tabs: tuple[str, ...],
    is_opaque: bool,
) -> str:
    if is_opaque:
        parts = [observation.package, observation.activity or "", OPAQUE_MARKER]
    else:
        pairs = sorted(f"{e.class_name}:{e.resource_id}" for e in kept)
        parts = [
            observation.package,
            observation.activity or "",
            ",".join(pairs),
            ",".join(overlays),
            ",".join(tabs),
        ]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()
