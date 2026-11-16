from dataclasses import dataclass

from artemis.app_memory.map_graph import MapGraph
from artemis.app_memory.routing.paths import PathFinder
from artemis.app_memory.routing.weights import weigh


@dataclass(frozen=True, slots=True)
class RoutingMap:
    """One map with its weighted path finder, built once and shared by every milestone that
    routes over the map. Immutable: a changed map is a new RoutingMap."""

    graph: MapGraph
    paths: PathFinder

    @classmethod
    def build(cls, graph: MapGraph) -> "RoutingMap":
        return cls(graph, PathFinder(weigh(graph)))
