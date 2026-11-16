from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from artemis.app_memory.abstraction.constants import EDITABLE_CLASS_HINTS


@dataclass(frozen=True, slots=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def contains(self, other: "Bounds") -> bool:
        return (
            self.left <= other.left
            and self.top <= other.top
            and self.right >= other.right
            and self.bottom >= other.bottom
        )


@dataclass(frozen=True, slots=True)
class Element:
    resource_id: str
    text: str
    content_desc: str
    hint: str
    class_name: str
    package: str
    bounds: Bounds | None
    clickable: bool
    scrollable: bool
    editable: bool
    checkable: bool
    selected: bool

    @property
    def label(self) -> str:
        return self.text or self.content_desc

    def with_labels(self, text: str, content_desc: str) -> "Element":
        return replace(self, text=text, content_desc=content_desc)


def parse_elements(raw_elements: Iterable[Mapping[str, Any]]) -> tuple[Element, ...]:
    return tuple(_parse_element(raw) for raw in raw_elements)


def _parse_element(raw: Mapping[str, Any]) -> Element:
    class_name = _text(raw.get("class"))
    return Element(
        resource_id=_text(raw.get("resource-id")),
        text=_text(raw.get("text")),
        content_desc=_text(raw.get("content-desc")),
        hint=_text(raw.get("hint") or raw.get("hint-text")),
        class_name=class_name,
        package=_text(raw.get("package")),
        bounds=_parse_bounds(raw.get("parsed_bounds")),
        clickable=_flag(raw.get("clickable")),
        scrollable=_flag(raw.get("scrollable")),
        editable=_flag(raw.get("editable")) or _is_editable_class(class_name),
        checkable=_flag(raw.get("checkable")),
        selected=_flag(raw.get("selected")),
    )


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return isinstance(value, str) and value.strip().lower() == "true"


def _is_editable_class(class_name: str) -> bool:
    return any(hint in class_name for hint in EDITABLE_CLASS_HINTS)


def _parse_bounds(raw: Any) -> Bounds | None:
    if not isinstance(raw, Mapping):
        return None
    try:
        return Bounds(int(raw["left"]), int(raw["top"]), int(raw["right"]), int(raw["bottom"]))
    except (KeyError, TypeError, ValueError):
        return None
