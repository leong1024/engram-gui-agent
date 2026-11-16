import heapq
import itertools
import math
from collections.abc import Mapping, Sequence

from artemis.app_memory.models import StateId
from artemis.app_memory.routing.weights import WeightedEdge

Path = tuple[WeightedEdge, ...]
Adjacency = Mapping[StateId, Sequence[WeightedEdge]]


def shortest_path(
    adjacency: Adjacency, source: StateId, target: StateId, max_hops: int
) -> Path | None:
    """Cheapest path of at most `max_hops` edges. Ties go to fewer hops, then to the path
    whose stalest edge was seen most recently."""
    order = itertools.count()
    frontier: list[tuple[float, int, float, int, StateId, Path]] = [
        (0.0, 0, -math.inf, next(order), source, ())
    ]
    settled: set[StateId] = set()
    while frontier:
        cost, hops, staleness, _, state, path = heapq.heappop(frontier)
        if state == target:
            return path
        if state in settled or hops == max_hops:
            continue
        settled.add(state)
        for step in adjacency.get(state, ()):
            if step.edge.dst not in settled:
                entry = (
                    cost + step.cost,
                    hops + 1,
                    max(staleness, -step.edge.last_seen_at),
                    next(order),
                    step.edge.dst,
                    (*path, step),
                )
                heapq.heappush(frontier, entry)
    return None
