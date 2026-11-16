import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from artemis.app_memory.models import MapId

MAX_DOCUMENT_LABELS = 20
OUTSIDE_TITLE = "outside the app"
UNNAMED_TITLE = "an unnamed screen"


class OwnerKind(StrEnum):
    STATE = "state"
    EDGE = "edge"


@dataclass(frozen=True, slots=True)
class Owner:
    """A described row: a state or an edge. `key` is its describer job key."""

    kind: OwnerKind
    owner_id: str

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.owner_id}"

    @classmethod
    def parse(cls, key: str) -> "Owner":
        kind, owner_id = key.split(":", 1)
        return cls(OwnerKind(kind), owner_id)


@dataclass(frozen=True, slots=True)
class PendingState:
    state_id: str
    package: str
    activity: str | None
    skeleton: tuple[str, ...]
    static_tokens: tuple[str, ...]
    image_sha: str | None


@dataclass(frozen=True, slots=True)
class PendingEdge:
    edge_id: str
    src_title: str
    dst_title: str
    actions: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class EmbeddingDoc:
    owner: Owner
    map_key: str
    text: str

    @property
    def text_hash(self) -> str:
        return hashlib.sha1(self.text.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class VectorHit:
    owner: Owner
    similarity: float


def vector_map_key(map_id: MapId) -> str:
    return f"{map_id.package}:{map_id.version_code}"


def endpoint_title(title: str | None, is_virtual: bool) -> str:
    return OUTSIDE_TITLE if is_virtual else title or UNNAMED_TITLE


def state_document(
    title: str, purpose: str, affordances: Sequence[str], labels: Sequence[str]
) -> str:
    shown = ", ".join(labels[:MAX_DOCUMENT_LABELS])
    return f"{title}. {purpose} You can: {', '.join(affordances)}. Labels: {shown}"


def edge_document(description: str, src_title: str, dst_title: str) -> str:
    return f"{description} (from {src_title} to {dst_title})"


def loads_list(raw: str | None) -> tuple[Any, ...]:
    value = json.loads(raw) if raw else []
    return tuple(value) if isinstance(value, list) else ()
