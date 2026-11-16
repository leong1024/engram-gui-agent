from collections.abc import Callable, Iterator
from dataclasses import replace

import pytest

from artemis.app_memory.map_graph import MapGraph
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import ScreenObservation, StateId
from artemis.app_memory.routing import Route, RouteKind, RoutePlanner, RoutingMap
from tests.unit.app_memory.fixtures.maps import NOW, SETTINGS_MAP, MapBuilder, launch, page, tap

MILESTONE = Milestone("m1", "Turn on dark theme")


@pytest.fixture
def build(tmp_path) -> Iterator[MapBuilder]:
    builder = MapBuilder.open(tmp_path / "app_memory.db")
    yield builder
    builder.store.close()


def router(
    build: MapBuilder, target: StateId, graph: MapGraph | None = None
) -> Callable[[ScreenObservation], Route]:
    routing_map = RoutingMap.build(graph or build.store.graph.map_graph(SETTINGS_MAP))
    plan = RoutePlanner(MILESTONE, target, borrowed=False)
    return lambda screen: plan.route(plan.locate(screen, routing_map), routing_map)


def route_from(build: MapBuilder, name: str, target: StateId) -> Route:
    return router(build, target)(page(name))


def test_one_confirmed_observation_gives_two_thirds(build):
    home, display = build.state("Home"), build.state("Display")
    build.edge(home, display, tap("Display"))
    assert route_from(build, "Home", display).confidence == pytest.approx(2 / 3)


def test_an_action_that_works_nine_times_in_ten_gives_five_sixths(build):
    home, display = build.state("Home"), build.state("Display")
    build.edge(home, display, tap("Display"), confirmed=9, no_effect=1)
    assert route_from(build, "Home", display).confidence == pytest.approx(10 / 12)


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ({"discounted": 1, "confirmed": 0}, 1.25 / 2.25),
        ({"provisional": 1, "confirmed": 0}, 1.5 / 2.5),
        ({"dropped": 1, "confirmed": 0}, 1 / 2),
        ({"confirmed": 1, "discounted": 1}, 2.25 / 3.25),
    ],
)
def test_weaker_observations_lower_the_edge_probability(build, counts, expected):
    home, display = build.state("Home"), build.state("Display")
    build.edge(home, display, tap("Display"), **counts)
    assert route_from(build, "Home", display).confidence == pytest.approx(expected)


def test_an_action_seen_reaching_another_screen_counts_against_the_edge(build):
    home, display, sound = build.state("Home"), build.state("Display"), build.state("Sound")
    build.edge(home, display, tap("Display"))
    build.edge(home, sound, tap("Display"))
    assert route_from(build, "Home", display).confidence == pytest.approx(2 / 4)


def test_the_reliable_long_path_beats_an_unreliable_short_one(build):
    home, menu, display = build.state("Home"), build.state("Menu"), build.state("Display")
    build.edge(home, display, tap("Shortcut"), no_effect=8)
    build.edge(home, menu, tap("Menu"), confirmed=5)
    build.edge(menu, display, tap("Display"), confirmed=5)
    route = route_from(build, "Home", display)
    assert [hop.to_state.title for hop in route.hops] == ["Menu", "Display"]


def test_between_equally_reliable_routes_the_shorter_wins(build):
    home, menu, display = build.state("Home"), build.state("Menu"), build.state("Display")
    build.edge(home, display, tap("Shortcut"), confirmed=3, no_effect=4)
    build.edge(home, menu, tap("Menu"))
    build.edge(menu, display, tap("Display"))
    assert route_from(build, "Home", display).confidence == pytest.approx(4 / 9)
    assert [hop.to_state.title for hop in route_from(build, "Home", display).hops] == ["Display"]


def test_an_opaque_screen_on_the_way_costs_more(build):
    home, dim, clear, display = (build.state(n) for n in ("Home", "Dim", "Clear", "Display"))
    for via, confirmed in ((dim, 2), (clear, 1)):
        build.edge(home, via, tap("Via"), confirmed=confirmed)
        build.edge(via, display, tap("Display"), confirmed=confirmed)
    graph = build.store.graph.map_graph(SETTINGS_MAP)
    opaque = replace(
        graph, states={**graph.states, dim: replace(graph.states[dim], is_opaque=True)}
    )
    for map_graph, expected in ((graph, "Dim"), (opaque, "Clear")):
        assert router(build, display, map_graph)(page("Home")).hops[0].to_state.title == expected


def test_ties_go_to_the_more_recently_seen_route(build):
    home, old, new, display = (build.state(n) for n in ("Home", "Old", "New", "Display"))
    build.edge(home, old, tap("Old"), seen_at=NOW - 100)
    build.edge(old, display, tap("Display"), seen_at=NOW - 100)
    build.edge(home, new, tap("New"))
    build.edge(new, display, tap("Display"))
    assert route_from(build, "Home", display).hops[0].to_state.title == "New"


def test_recency_never_outweighs_reliability(build):
    home, stale, fresh, display = (build.state(n) for n in ("Home", "Stale", "Fresh", "Display"))
    build.edge(home, stale, tap("Stale"), confirmed=9, seen_at=NOW - 10_000_000)
    build.edge(stale, display, tap("Display"), confirmed=9, seen_at=NOW - 10_000_000)
    build.edge(home, fresh, tap("Fresh"), confirmed=1, no_effect=1)
    build.edge(fresh, display, tap("Display"), confirmed=1, no_effect=1)
    assert route_from(build, "Home", display).hops[0].to_state.title == "Stale"


@pytest.mark.parametrize(("length", "kind"), [(15, RouteKind.FROM_STATE), (16, RouteKind.NO_PATH)])
def test_routes_stop_at_fifteen_hops(build, length, kind):
    chain = [build.state(f"Page {chr(97 + i)}") for i in range(length + 1)]
    for src, dst in zip(chain, chain[1:]):
        build.edge(src, dst, tap("Next"))
    route = router(build, chain[-1])
    assert route(page("Page a")).kind is kind


def test_localization_covers_each_situation(build):
    home, display = build.state("Home"), build.state("Display")
    build.edge(build.outside(), home, launch())
    build.edge(home, display, tap("Display"))
    route = router(build, display)
    cases = {
        "known screen": (page("Home"), RouteKind.FROM_STATE, 1),
        "another app": (page("Inbox", package="com.example.mail"), RouteKind.FROM_OUTSIDE, 2),
        "unknown screen": (page("Bluetooth"), RouteKind.FROM_LAUNCH, 2),
        "on the target": (page("Display"), RouteKind.ARRIVED, 0),
    }
    for label, (screen, kind, hops) in cases.items():
        found = route(screen)
        assert (found.kind, len(found.hops)) == (kind, hops), label
    assert route(page("Bluetooth")).hops[0].actions == (launch(),)


def test_a_borrowed_target_localizes_against_the_older_map(build):
    home, display = build.state("Home"), build.state("Display")
    build.edge(home, display, tap("Display"))
    route = router(build, display)
    newer_screen = page("Home", version_code=35)
    assert route(newer_screen).kind is RouteKind.FROM_STATE


def test_a_target_with_no_path_still_names_the_target(build):
    build.state("Home")
    display = build.state("Display")
    route = route_from(build, "Home", display)
    assert (route.kind, route.target.title, route.hops) == (RouteKind.NO_PATH, "Display", ())
