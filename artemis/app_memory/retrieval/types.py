from dataclasses import dataclass
from enum import StrEnum

from artemis.app_memory.map_graph import GraphEdge, StateCard
from artemis.app_memory.models import EdgeId, MapId, StateId


@dataclass(frozen=True, slots=True)
class RetrievalSettings:
    top_k: int = 20
    similarity_floor: float = 0.35
    min_confidence: float = 0.5
    fallback_versions: int = 2
    map_concurrency: int = 3


class NoTargetReason(StrEnum):
    NO_MAPS = "no_maps"
    NO_VECTORS = "no_vectors"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    NO_MATCH = "no_match"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TargetResolution:
    milestone_key: str
    state_id: StateId
    map_id: MapId
    borrowed: bool
    confidence: float
    reason: str
    last_hop_edge_id: EdgeId | None = None


@dataclass(frozen=True, slots=True)
class NoTarget:
    milestone_key: str
    reason: NoTargetReason


Resolution = TargetResolution | NoTarget


@dataclass(frozen=True, slots=True)
class CandidateMaps:
    """Maps of installed packages: their installed version, then older ones to borrow from."""

    primary: tuple[MapId, ...]
    fallback: tuple[MapId, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A state that one map's vector search nominated. An edge hit nominates its
    destination and keeps the edge as the suggested last hop."""

    map_id: MapId
    card: StateCard
    similarity: float
    last_hop: GraphEdge | None = None


@dataclass(frozen=True, slots=True)
class Proposal:
    candidate: Candidate
    confidence: float
    reason: str
    borrowed: bool
