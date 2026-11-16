import re
from dataclasses import replace

from artemis.app_memory import hints
from artemis.app_memory.map_graph import StateCard
from artemis.app_memory.milestones import Milestone
from artemis.app_memory.models import (
    ActionKind,
    CanonicalAction,
    MapId,
    StateId,
    TargetDescriptor,
)
from artemis.app_memory.routing.types import HintNote, Hop, Route, RouteKind
from tests.unit.app_memory.fixtures.maps import launch, tap
from tests.unit.app_memory.fixtures.parts import chrome_parts

HEADER = "--- App Memory: Known Route (advisory) ---\nMilestone: Turn on dark mode\n"
TARGET = 'Target screen: "Dark theme" (com.android.settings v34) — Switch the dark theme.\n'
FOOTER = (
    "Check that each screen matches before taking the next hop. If the screen does not match,\n"
    "ignore this route and continue normally."
)
HOPS = (
    '  1. Tap "Display" (id: display_settings) → expect "Display" '
    '[DisplaySettings; "Brightness level", "Dark theme", "Font size"]\n'
    '  2. Tap "Dark theme" (switch)            → target reached\n'
)


def card(title: str, **fields) -> StateCard:
    base = StateCard(StateId(title), title, "", (), None, (), False, False, 1)
    return replace(base, **fields)


HOME = card("Settings home")
DISPLAY = card(
    "Display",
    activity="com.android.settings.DisplaySettings",
    static_tokens=("<NUM> apps", "Brightness level", "Dark theme", "display_title", "Font size"),
)
DARK = card("Dark theme", purpose="Switch the dark theme.", visits=6)
TO_DISPLAY = Hop(HOME, (tap("Display", "com.android.settings:id/display_settings"),), DISPLAY, 0.84)
TO_DARK = Hop(DISPLAY, (tap("Dark theme", class_name="android.widget.Switch"),), DARK, 0.85)
ROUTE = Route(
    Milestone("m1", "Turn on dark mode"),
    RouteKind.FROM_STATE,
    MapId("com.android.settings", 34),
    DARK,
    HOME,
    (TO_DISPLAY, TO_DARK),
)


def test_a_route_from_a_known_screen_matches_the_spec_format():
    expected = (
        f"{HEADER}{TARGET}Seen 6 times. Route confidence 0.71.\n"
        f'From the current screen ("Settings home"):\n{HOPS}{FOOTER}'
    )
    assert hints.render(ROUTE) == expected


def test_a_route_from_launch_says_the_screen_is_not_known():
    outside = card("outside the app", is_virtual=True)
    opening = Hop(outside, (launch(),), HOME, 1.0)
    route = replace(ROUTE, kind=RouteKind.FROM_LAUNCH, source=outside, hops=(opening, *ROUTE.hops))
    text = hints.render(route)
    assert "\nNot on a known screen; route from app launch:\n" in text
    assert '  1. Launch the app com.android.settings  → expect "Settings home"\n' in text


def test_a_route_from_another_app_starts_outside_it():
    text = hints.render(replace(ROUTE, kind=RouteKind.FROM_OUTSIDE))
    assert "\nFrom outside the app:\n" in text


def test_a_borrowed_route_warns_that_screens_may_differ():
    expected = (
        f"{HEADER}{TARGET}Seen 6 times. Route confidence 0.71.\n"
        "Learned on an older app version (v34); screens may differ.\n"
        f'From the current screen ("Settings home"):\n{HOPS}{FOOTER}'
    )
    assert hints.render(replace(ROUTE, borrowed=True)) == expected


def test_a_target_with_no_path_shows_only_the_target_screen():
    route = replace(ROUTE, kind=RouteKind.NO_PATH, hops=())
    assert hints.render(route) == HEADER + TARGET.rstrip("\n")


def test_arrival_is_a_single_line():
    route = replace(ROUTE, kind=RouteKind.ARRIVED, source=DARK, hops=())
    assert hints.render(route) == HEADER + "You are on the target screen for this milestone."


def test_tracker_notes_are_shown_before_the_route():
    rerouted = hints.render(replace(ROUTE, notes=(HintNote.REROUTED,)))
    unknown = hints.render(replace(ROUTE, notes=(HintNote.UNRECOGNISED,)))
    assert "0.71.\nRerouted from the current screen.\nFrom the current" in rerouted
    assert "0.71.\nCurrent screen not recognised; this route may not apply.\nFrom" in unknown


def test_long_routes_show_the_next_eight_hops():
    hops = tuple(replace(TO_DISPLAY, probability=1.0) for _ in range(10))
    lines = hints.render(replace(ROUTE, hops=hops)).splitlines()
    numbered = [line for line in lines if re.match(r"  \d+\. ", line)]
    assert [line[:5] for line in numbered] == [f"  {i}. " for i in range(1, 9)]
    assert "  (+2 more)" in lines


def test_typed_text_names_the_slot_and_never_a_value():
    field = TargetDescriptor(text="Search")
    typing = CanonicalAction(ActionKind.INPUT_TEXT, field, input_slot="text")
    text = hints.render(replace(ROUTE, hops=(replace(TO_DARK, actions=(typing,)),)))
    assert '  1. Type the text into "Search" → target reached' in text


def test_coordinates_and_masked_values_never_appear(abstract_of):
    tokens = tuple(sorted(abstract_of(chrome_parts("Battery 87%", "uiautomator")).static_tokens))
    assert "Battery <PERCENT>" in tokens
    battery = card("Battery", static_tokens=tokens, activity=".Settings")
    pointed = TargetDescriptor(
        target_description="the gear icon", rel_bounds=(612, 1480, 612, 1480)
    )
    tap_point = CanonicalAction(ActionKind.CLICK, pointed)
    hops = (Hop(HOME, (tap_point,), battery, 0.9), TO_DARK)
    text = hints.render(replace(ROUTE, hops=hops))
    assert 'Tap the element described as "the gear icon"' in text
    for value in ("612", "1480", "87"):
        assert value not in text
