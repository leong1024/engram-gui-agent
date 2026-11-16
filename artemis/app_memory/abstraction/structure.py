from collections.abc import Sequence
from dataclasses import dataclass

from artemis.app_memory.abstraction.constants import (
    IME_PACKAGE_HINTS,
    MIN_ELEMENT_SIZE_PX,
    OVERLAY_CLASS_HINTS,
    OVERLAY_PREFIX,
    SYSTEM_UI_PACKAGES,
    TAB_BAR_CLASS_HINTS,
)
from artemis.app_memory.abstraction.elements import Element
from artemis.app_memory.abstraction.masking import mask_text


@dataclass(frozen=True, slots=True)
class ScreenStructure:
    elements: tuple[Element, ...]
    list_containers: tuple[Element, ...]
    overlay_markers: tuple[str, ...]
    selected_tabs: tuple[str, ...]


def is_system_chrome(element: Element) -> bool:
    package = element.package.lower()
    return package in SYSTEM_UI_PACKAGES or any(hint in package for hint in IME_PACKAGE_HINTS)


def is_visible(element: Element, screen_size: tuple[int, int] | None) -> bool:
    bounds = element.bounds
    if bounds is None:
        return False
    if bounds.width <= MIN_ELEMENT_SIZE_PX or bounds.height <= MIN_ELEMENT_SIZE_PX:
        return False
    if bounds.right <= 0 or bounds.bottom <= 0:
        return False
    if screen_size is None:
        return True
    return bounds.left < screen_size[0] and bounds.top < screen_size[1]


def screen_elements(
    elements: Sequence[Element], screen_size: tuple[int, int] | None
) -> tuple[Element, ...]:
    return tuple(e for e in elements if not is_system_chrome(e) and is_visible(e, screen_size))


def split_list_items(elements: Sequence[Element]) -> tuple[list[Element], list[Element]]:
    """Return (kept, containers); items inside an earlier scrollable are dropped.

    Document order puts a parent before its children, so a nested scrollable with
    identical bounds is still recognised as the item rather than the container.
    """
    kept: list[Element] = []
    containers: list[Element] = []
    for element in elements:
        if _inside_any(element, containers):
            continue
        kept.append(element)
        if element.scrollable:
            containers.append(element)
    return kept, containers


def _inside_any(element: Element, containers: Sequence[Element]) -> bool:
    bounds = element.bounds
    return bounds is not None and any(
        c.bounds is not None and c.bounds.contains(bounds) for c in containers
    )


def overlay_markers(elements: Sequence[Element]) -> tuple[str, ...]:
    markers = {
        f"{OVERLAY_PREFIX}{hint.lower()}"
        for element in elements
        for hint in OVERLAY_CLASS_HINTS
        if hint in element.class_name
    }
    return tuple(sorted(markers))


def selected_tab_labels(elements: Sequence[Element]) -> tuple[str, ...]:
    bars = [e for e in elements if any(hint in e.class_name for hint in TAB_BAR_CLASS_HINTS)]
    labels = {
        mask_text(_tab_label(tab, elements))
        for tab in elements
        if tab.selected and not tab.scrollable and _inside_any(tab, bars)
    }
    return tuple(sorted(label for label in labels if label))


def _tab_label(tab: Element, elements: Sequence[Element]) -> str:
    if tab.label:
        return tab.label
    inner = (e.label for e in elements if e is not tab and e.label and _inside_any(e, [tab]))
    return next(inner, "")
