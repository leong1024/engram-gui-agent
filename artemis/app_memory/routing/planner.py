from dataclasses import replace

from artemis.app_memory.abstraction import abstract, match
from artemis.app_memory.map_graph import MapGraph
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import ScreenObservation, StateId
from artemis.app_memory.routing.constants import MAX_HOPS
from artemis.app_memory.routing.routing_map import RoutingMap
from artemis.app_memory.routing.types import (
    Arrived,
    AtState,
    Hop,
    InOtherApp,
    Location,
    Route,
    RouteKind,
    Unrecognised,
)


def locate(observation: ScreenObservation, graph: MapGraph, target: StateId) -> Location:
    """Where the current screen is in the target's map. The observation's own version is
    ignored, so a borrowed target localizes against the older map it came from."""
    if observation.package != graph.map_id.package:
        return InOtherApp(graph.outside)
    state_id = match(abstract(observation), graph.known)
    if state_id is None:
        return Unrecognised(graph.outside)
    return Arrived(state_id) if state_id == target else AtState(state_id)


class RoutePlanner:
    """Routes to one milestone's target over the shared map it is in. Deterministic for a
    RoutingMap."""

    def __init__(self, milestone: Milestone, target: StateId, borrowed: bool) -> None:
        self._milestone = milestone
        self._target = target
        self._borrowed = borrowed

    def locate(self, observation: ScreenObservation, routing_map: RoutingMap) -> Location:
        return locate(observation, routing_map.graph, self._target)

    def route(self, location: Location, routing_map: RoutingMap) -> Route:
        graph, states = routing_map.graph, routing_map.graph.states
        route = Route(
            milestone=self._milestone,
            kind=location.kind,
            map_id=graph.map_id,
            target=states[self._target],
            source=states[location.state_id],
            borrowed=self._borrowed,
        )
        if isinstance(location, Arrived):
            return route
        path = routing_map.paths.shortest(location.state_id, self._target, MAX_HOPS)
        if path is None:
            return replace(route, kind=RouteKind.NO_PATH)
        hops = tuple(
            Hop(states[step.edge.src], step.edge.actions, states[step.edge.dst], step.probability)
            for step in path
        )
        return replace(route, hops=hops)
