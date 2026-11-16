from dataclasses import replace

from artemis.app_memory.models import ScreenObservation
from artemis.app_memory.routing.constants import HIDE_AFTER_UNKNOWN_TURNS
from artemis.app_memory.routing.planner import RoutePlanner
from artemis.app_memory.routing.routing_map import RoutingMap
from artemis.app_memory.routing.types import Arrived, HintNote, Location, Route, Unrecognised


class RouteTracker:
    """Keeps one milestone's route in step with the screen, once per Operator turn: it
    advances along the route, reroutes from a known screen off it, and hides the route
    after repeated unknown screens."""

    def __init__(self, planner: RoutePlanner) -> None:
        self._planner = planner
        self._route: Route | None = None
        self._unknown_turns = 0

    def step(self, observation: ScreenObservation, routing_map: RoutingMap) -> Route | None:
        """`routing_map` may be newer than the one the current route was found on. State ids
        are stable across maps, so the route still advances, and a reroute uses the newer map."""
        location = self._planner.locate(observation, routing_map)
        route = self._route
        if isinstance(location, Unrecognised) and route is not None:
            return self._unknown(route)
        self._unknown_turns = 0
        if isinstance(location, Arrived):
            return self._planner.route(location, routing_map)
        if route is not None and (ahead := _advance(route, location)) is not None:
            self._route = ahead
            return ahead
        self._route = self._planner.route(location, routing_map)
        return self._route if route is None else replace(self._route, notes=(HintNote.REROUTED,))

    def _unknown(self, route: Route) -> Route | None:
        self._unknown_turns += 1
        if self._unknown_turns >= HIDE_AFTER_UNKNOWN_TURNS:
            return None
        return replace(route, notes=(HintNote.UNRECOGNISED,))


def _advance(route: Route, location: Location) -> Route | None:
    """The rest of `route` when the screen is the start of one of its hops, or `route`
    itself when the screen is still its source."""
    starts = [hop.from_state.state_id for hop in route.hops]
    if location.state_id not in starts:
        return route if location.state_id == route.source.state_id else None
    remaining = route.hops[starts.index(location.state_id) :]
    return replace(route, kind=location.kind, source=remaining[0].from_state, hops=remaining)
