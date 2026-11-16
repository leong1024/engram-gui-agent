from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, NewType

StateId = NewType("StateId", str)
EdgeId = NewType("EdgeId", str)
ActionSignature = NewType("ActionSignature", str)

UNKNOWN_VERSION_CODE = -1
REL_BOUNDS_BUCKET = 50


@dataclass(frozen=True, slots=True)
class MapId:
    package: str
    version_code: int = UNKNOWN_VERSION_CODE


class ObservationStatus(StrEnum):
    PROVISIONAL = "provisional"
    CONFIRMED = "confirmed"
    DISCOUNTED = "discounted"
    DROPPED = "dropped"


class SessionOutcome(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DescriptionStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class ActionKind(StrEnum):
    CLICK = "click"
    LONG_PRESS = "long_press"
    INPUT_TEXT = "input_text"
    SWIPE = "swipe"
    PRESS_KEY = "press_key"
    MANAGE_APP = "manage_app"
    OPEN_LINK = "open_link"


@dataclass(frozen=True, slots=True)
class ScreenObservation:
    package: str
    activity: str | None
    version_code: int
    elements: tuple[Mapping[str, Any], ...]
    dhash: str | None = None
    ocr_tokens: frozenset[str] = frozenset()
    screen_size: tuple[int, int] | None = None

    @property
    def map_id(self) -> MapId:
        return MapId(self.package, self.version_code)


@dataclass(frozen=True, slots=True)
class AbstractScreen:
    activity: str | None
    coarse_key: str
    skeleton: tuple[str, ...]
    static_tokens: frozenset[str]
    is_opaque: bool
    dhash: str | None = None
    ocr_tokens: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class KnownState:
    state_id: StateId
    screen: AbstractScreen


@dataclass(frozen=True, slots=True)
class TargetDescriptor:
    resource_id: str | None = None
    text: str | None = None
    content_desc: str | None = None
    class_name: str | None = None
    rel_bounds: tuple[int, int, int, int] | None = None
    target_description: str | None = None

    def __post_init__(self) -> None:
        if all(value is None for value in self.as_dict().values()):
            raise ValueError("a target descriptor needs at least one field")
        if self.rel_bounds is not None:
            bucketed = tuple(_bucket(v) for v in self.rel_bounds)
            object.__setattr__(self, "rel_bounds", bucketed)

    @property
    def identity(self) -> str | None:
        described = " ".join((self.target_description or "").lower().split())
        return self.resource_id or self.text or self.content_desc or described or None

    def as_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "text": self.text,
            "content_desc": self.content_desc,
            "class": self.class_name,
            "rel_bounds": self.rel_bounds,
            "target_description": self.target_description,
        }


def _bucket(value: int) -> int:
    return round(value / REL_BOUNDS_BUCKET) * REL_BOUNDS_BUCKET


@dataclass(frozen=True, slots=True)
class CanonicalAction:
    kind: ActionKind
    target: TargetDescriptor | None = None
    params: Mapping[str, str | int | bool] = field(default_factory=dict)
    input_slot: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "target": self.target.as_dict() if self.target else None,
            "params": dict(self.params),
            "input_slot": self.input_slot,
        }

    def signature_key(self) -> list[Any]:
        identity = self.target.identity if self.target else None
        return [self.kind.value, identity, dict(self.params), self.input_slot]


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    session_id: str
    step_id: str
    src_state_id: StateId
    action_signature: ActionSignature
    status: ObservationStatus
    recorded_at: float
    edge_id: EdgeId | None = None


@dataclass(frozen=True, slots=True)
class EdgeCounts:
    confirmed: int
    discounted: int
    provisional: int


@dataclass(frozen=True, slots=True)
class EmbeddingModel:
    model_id: str
    provider: str
    model: str
    dim: int


@dataclass(frozen=True, slots=True)
class StateSample:
    session_id: str
    step_id: str
    image_sha: str | None


@dataclass(frozen=True, slots=True)
class Sighting:
    screen: ScreenObservation
    sample: StateSample


@dataclass(frozen=True, slots=True)
class HarvestStep:
    step_id: str
    recorded_at: float
    actions: tuple[CanonicalAction, ...]
    is_wait: bool
    sighting: Sighting | None


@dataclass(frozen=True, slots=True)
class Transition:
    step: HarvestStep
    source: Sighting
    destination: Sighting


@dataclass(frozen=True, slots=True)
class MapStats:
    map_id: MapId
    states: int
    edges: int
    confirmed: int
    discounted: int
    provisional: int
