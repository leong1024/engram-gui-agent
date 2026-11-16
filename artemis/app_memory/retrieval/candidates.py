from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from artemis.app_memory.documents import OwnerKind, VectorHit
from artemis.app_memory.map_graph import GraphEdge
from artemis.app_memory.models import (
    UNKNOWN_VERSION_CODE,
    EdgeId,
    EmbeddingModel,
    MapId,
    StateId,
)
from artemis.app_memory.retrieval.types import Candidate, CandidateMaps, RetrievalSettings
from artemis.app_memory.store import MapStore


def candidate_maps(
    installed: Mapping[str, int], maps: Iterable[MapId], fallback_versions: int
) -> CandidateMaps:
    """Maps of packages that are installed. Never a map of a package that is not."""
    versions: dict[str, list[int]] = defaultdict(list)
    for map_id in maps:
        if map_id.package in installed:
            versions[map_id.package].append(map_id.version_code)
    primary, older, unknown = [], [], []
    for package, codes in sorted(versions.items()):
        current = installed[package]
        if current in codes:
            primary.append(MapId(package, current))
        known = sorted((c for c in codes if UNKNOWN_VERSION_CODE < c < current), reverse=True)
        older += [MapId(package, code) for code in known[:fallback_versions]]
        if UNKNOWN_VERSION_CODE in codes:
            unknown.append(MapId(package))
    return CandidateMaps(tuple(primary), (*older, *unknown))


def find_candidates(
    store: MapStore,
    model: EmbeddingModel,
    map_id: MapId,
    vector: Sequence[float],
    settings: RetrievalSettings,
) -> tuple[Candidate, ...]:
    """One map's nearest states, or none when its best hit is under the similarity floor."""
    hits = store.documents.nearest(model, map_id, vector, settings.top_k)
    if not hits or hits[0].similarity < settings.similarity_floor:
        return ()
    edge_ids = [EdgeId(hit.owner.owner_id) for hit in hits if hit.owner.kind is OwnerKind.EDGE]
    edges = store.graph.edges(edge_ids)
    nominated: dict[StateId, tuple[float, EdgeId | None]] = {}
    for hit in hits:
        state_id, last_hop = _nominee(hit, edges)
        nominated.setdefault(state_id, (hit.similarity, last_hop))
    cards = store.graph.cards(list(nominated))
    return tuple(
        Candidate(map_id, cards[state_id], similarity, edges[hop] if hop else None)
        for state_id, (similarity, hop) in nominated.items()
        if not cards[state_id].is_virtual
    )


def _nominee(hit: VectorHit, edges: Mapping[EdgeId, GraphEdge]) -> tuple[StateId, EdgeId | None]:
    owner_id = hit.owner.owner_id
    if hit.owner.kind is OwnerKind.STATE:
        return StateId(owner_id), None
    edge = edges[EdgeId(owner_id)]
    return edge.dst, edge.edge_id
