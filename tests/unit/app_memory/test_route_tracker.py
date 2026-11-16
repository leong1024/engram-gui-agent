from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import ScreenObservation
from artemis.app_memory.routing import RouteKind, RoutePlanner, RouteTracker, RoutingMap
from artemis.app_memory.routing.types import HintNote, Route
from tests.unit.app_memory.fixtures.maps import SETTINGS_MAP, MapBuilder, launch, page, tap


@dataclass
class Tracking:
    tracker: RouteTracker
    routing_map: RoutingMap

    def step(self, observation: ScreenObservation) -> Route | None:
        return self.tracker.step(observation, self.routing_map)


@pytest.fixture
def tracker(tmp_path) -> Iterator[Tracking]:
    """Launch → Home → Menu → Display, plus Sound → Display off the route."""
    build = MapBuilder.open(tmp_path / "app_memory.db")
    home, menu, display, sound = (build.state(n) for n in ("Home", "Menu", "Display", "Sound"))
    build.edge(build.outside(), home, launch())
    build.edge(home, menu, tap("Menu"))
    build.edge(menu, display, tap("Display"))
    build.edge(sound, display, tap("Display"))
    routing_map = RoutingMap.build(build.store.graph.map_graph(SETTINGS_MAP))
    build.store.close()
    milestone = Milestone("m1", "Turn on dark theme")
    yield Tracking(RouteTracker(RoutePlanner(milestone, display, borrowed=False)), routing_map)


def path(route: Route | None) -> list[str]:
    assert route is not None
    return [route.source.title, *(hop.to_state.title for hop in route.hops)]


def test_the_route_advances_as_the_agent_follows_it(tracker):
    assert path(tracker.step(page("Home"))) == ["Home", "Menu", "Display"]
    assert path(tracker.step(page("Home"))) == ["Home", "Menu", "Display"]
    assert path(tracker.step(page("Menu"))) == ["Menu", "Display"]


def test_a_known_screen_off_the_route_reroutes(tracker):
    tracker.step(page("Home"))
    rerouted = tracker.step(page("Sound"))
    assert path(rerouted) == ["Sound", "Display"]
    assert rerouted is not None and rerouted.notes == (HintNote.REROUTED,)
    assert tracker.step(page("Sound")).notes == ()


def test_the_hint_hides_after_two_unknown_turns_until_a_known_screen_returns(tracker):
    tracker.step(page("Home"))
    first = tracker.step(page("Wifi"))
    assert first is not None and first.notes == (HintNote.UNRECOGNISED,)
    assert path(first) == ["Home", "Menu", "Display"]
    assert tracker.step(page("Bluetooth")) is None
    assert tracker.step(page("Wifi")) is None
    assert path(tracker.step(page("Menu"))) == ["Menu", "Display"]


def test_an_unknown_screen_between_known_ones_resets_the_count(tracker):
    tracker.step(page("Home"))
    assert tracker.step(page("Wifi")) is not None
    tracker.step(page("Home"))
    assert tracker.step(page("Wifi")) is not None


def test_reaching_the_target_reports_arrival(tracker):
    tracker.step(page("Home"))
    arrived = tracker.step(page("Display"))
    assert arrived is not None
    assert (arrived.kind, arrived.hops) == (RouteKind.ARRIVED, ())


def test_a_first_turn_on_an_unknown_screen_routes_from_launch(tracker):
    route = tracker.step(page("Wifi"))
    assert route is not None
    assert (route.kind, route.notes) == (RouteKind.FROM_LAUNCH, ())
    assert path(route) == ["outside the app", "Home", "Menu", "Display"]
    assert path(tracker.step(page("Home"))) == ["Home", "Menu", "Display"]
