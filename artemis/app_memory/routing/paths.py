from collections.abc import Mapping, Sequence

import rustworkx as rx

from artemis.app_memory.models import StateId
from artemis.app_memory.routing.weights import WeightedEdge

Path = tuple[WeightedEdge, ...]
Adjacency = Mapping[StateId, Sequence[WeightedEdge]]
Arc = tuple[WeightedEdge, float]

HOP_TIEBREAK = 1e-6
STALENESS_TIEBREAK = 1e-9


class PathFinder:
    """Cheapest paths over one map's weighted edges. The rustworkx graph is built once and
    reused for every query. Equal costs go to fewer hops, then to more recently seen edges.
    Both tie-breaks are added to each edge's cost, and are far smaller than any difference
    the cost function produces."""

    def __init__(self, adjacency: Adjacency) -> None:
        steps = [step for outgoing in adjacency.values() for step in outgoing]
        self._graph: rx.PyDiGraph = rx.PyDiGraph()
        self._nodes: dict[StateId, int] = {}
        for (src, dst), arc in sorted(_best_arcs(steps).items(), key=lambda item: item[0]):
            self._graph.add_edge(self._node(src), self._node(dst), arc)

    def shortest(self, source: StateId, target: StateId, max_hops: int) -> Path | None:
        """The cheapest path, or None when there is none or it is longer than `max_hops`."""
        if source not in self._nodes or target not in self._nodes:
            return None
        found = rx.dijkstra_shortest_paths(
            self._graph, self._nodes[source], target=self._nodes[target], weight_fn=_arc_weight
        )
        if self._nodes[target] not in found:
            return None
        node_path = list(found[self._nodes[target]])
        if len(node_path) - 1 > max_hops:
            return None
        arcs = (
            self._graph.get_edge_data(a, b) for a, b in zip(node_path, node_path[1:], strict=False)
        )
        return tuple(step for step, _ in arcs)

    def _node(self, state: StateId) -> int:
        if state not in self._nodes:
            self._nodes[state] = self._graph.add_node(state)
        return self._nodes[state]


def _best_arcs(steps: Sequence[WeightedEdge]) -> dict[tuple[StateId, StateId], Arc]:
    newest = max((s.edge.last_seen_at for s in steps), default=0.0)
    span = (newest - min((s.edge.last_seen_at for s in steps), default=0.0)) or 1.0
    best: dict[tuple[StateId, StateId], Arc] = {}
    for step in steps:
        age = (newest - step.edge.last_seen_at) / span
        arc = (step, step.cost + HOP_TIEBREAK + STALENESS_TIEBREAK * age)
        key = (step.edge.src, step.edge.dst)
        if key not in best or arc[1] < best[key][1]:
            best[key] = arc
    return best


def _arc_weight(arc: Arc) -> float:
    return arc[1]
