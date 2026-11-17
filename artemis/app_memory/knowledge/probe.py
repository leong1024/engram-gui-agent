import asyncio
import sqlite3
from collections.abc import Callable, Iterable, Sequence

from artemis.app_memory.embeddings import EmbeddingProvider
from artemis.app_memory.knowledge.reports import ProbeCandidate, ProbeResult, ProbeStatus
from artemis.app_memory.models import EmbeddingModel, MapId, StateId
from artemis.app_memory.retrieval import RetrievalSettings
from artemis.app_memory.retrieval.candidates import find_candidates
from artemis.app_memory.retrieval.types import Candidate
from artemis.app_memory.routing import RoutingMap
from artemis.app_memory.routing.constants import MAX_HOPS
from artemis.app_memory.store import MapStore
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)

MAX_CANDIDATES = 3
EMBED_TIMEOUT_SECONDS = 10.0
SETTINGS = RetrievalSettings()

Embedder = Callable[[], EmbeddingProvider]


async def probe(
    store: MapStore | None,
    model: EmbeddingModel | None,
    embedder: Embedder,
    query: str,
    package: str | None,
) -> ProbeResult:
    """The pages nearest `query` by vector search, with the hops to each from the app's launch.
    `model` is the stored embedding model the maps were embedded with, or None. One embedding
    call at most, no LLM call, and no write."""
    query = query.strip()
    if not query:
        return ProbeResult(query=query, status=ProbeStatus.EMPTY_QUERY)
    newest, older = _pick_maps(store.graph.maps() if store else (), package or None)
    if store is None or not newest:
        return ProbeResult(query=query, status=ProbeStatus.NO_MAPS)
    if model is None:
        return ProbeResult(query=query, status=ProbeStatus.NO_VECTORS)
    vector = await _embed(embedder, query)
    if vector is None:
        return ProbeResult(query=query, status=ProbeStatus.PROVIDER_UNAVAILABLE)
    if len(vector) != model.dim:
        return ProbeResult(query=query, status=ProbeStatus.NO_VECTORS)
    found, borrowed = _search(store, model, newest, vector), False
    if not found:
        found, borrowed = _search(store, model, older, vector), True
    if not found:
        return ProbeResult(query=query, status=ProbeStatus.NO_MATCH)
    candidates = _measure(store, found, borrowed)
    return ProbeResult(query=query, status=ProbeStatus.FOUND, candidates=candidates)


def _pick_maps(maps: Iterable[MapId], package: str | None) -> tuple[list[MapId], list[MapId]]:
    """The maps to search first, and the older ones to borrow from when those find nothing.
    With `package`, its newest version then up to two older ones. Without, the newest version
    of every package and nothing to borrow."""
    by_version = sorted(maps, key=lambda map_id: map_id.version_code)
    if package is None:
        newest = {map_id.package: map_id for map_id in by_version}
        return list(newest.values()), []
    versions = [map_id for map_id in reversed(by_version) if map_id.package == package]
    return versions[:1], versions[1 : 1 + SETTINGS.fallback_versions]


async def _embed(embedder: Embedder, query: str) -> list[float] | None:
    try:
        provider = embedder()
        return await asyncio.wait_for(provider.embed_query(query), EMBED_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning(f"App knowledge probe has no query vector: {exc!r}")
        return None


def _search(
    store: MapStore, model: EmbeddingModel, maps: Sequence[MapId], vector: Sequence[float]
) -> list[Candidate]:
    found = (
        candidate
        for map_id in maps
        for candidate in find_candidates(store, model, map_id, vector, SETTINGS)
        if candidate.similarity >= SETTINGS.similarity_floor
    )
    return sorted(found, key=_rank)[:MAX_CANDIDATES]


def _rank(candidate: Candidate) -> tuple[float, str, int, str]:
    map_id = candidate.map_id
    return -candidate.similarity, map_id.package, -map_id.version_code, candidate.card.title


def _measure(
    store: MapStore, found: Sequence[Candidate], borrowed: bool
) -> tuple[ProbeCandidate, ...]:
    routing = {map_id: _routing_map(store, map_id) for map_id in {c.map_id for c in found}}
    return tuple(
        ProbeCandidate(
            package=candidate.map_id.package,
            version_code=candidate.map_id.version_code,
            page=candidate.card.title,
            similarity=candidate.similarity,
            hops_from_launch=_hops(routing[candidate.map_id], candidate.card.state_id),
            borrowed=borrowed,
        )
        for candidate in found
    )


def _routing_map(store: MapStore, map_id: MapId) -> RoutingMap | None:
    try:
        return RoutingMap.build(store.graph.map_graph(map_id))
    except sqlite3.Error as exc:
        logger.warning(f"App knowledge probe measures no hops in {map_id}: {exc!r}")
        return None


def _hops(routing: RoutingMap | None, target: StateId) -> int | None:
    """Hops from `@outside`, which stands for the app launch, as the router plans them."""
    if routing is None:
        return None
    path = routing.paths.shortest(routing.graph.outside, target, MAX_HOPS)
    return None if path is None else len(path)
