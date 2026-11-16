import pytest

from artemis.app_memory.abstraction import match
from artemis.app_memory.models import AbstractScreen, KnownState, StateId
from tests.unit.app_memory.fixtures import screens

STYLES = ["uiautomator", "helper"]
YOUTUBE = "com.google.android.youtube"
GAME = "com.example.game"


def _known(screen: AbstractScreen, name: str) -> KnownState:
    return KnownState(StateId(name), screen)


@pytest.mark.parametrize("style", STYLES)
def test_settings_at_two_scroll_positions_is_one_state(abstract_of, style):
    top = abstract_of(screens.settings("top", style=style))
    bottom = abstract_of(screens.settings("bottom", style=style))
    assert top.coarse_key == bottom.coarse_key
    assert match(bottom, [_known(top, "settings")]) == "settings"


def test_feed_with_different_items_is_one_state(abstract_of):
    first = abstract_of(screens.feed(["Cats 10 min", "Cooking 4K"]), package=YOUTUBE)
    second = abstract_of(screens.feed(["Rust talk", "News 2 hours ago"]), package=YOUTUBE)
    assert first.coarse_key == second.coarse_key
    assert match(second, [_known(first, "feed")]) == "feed"


def test_dialog_over_a_page_is_a_different_state(abstract_of):
    page = abstract_of(screens.settings())
    with_dialog = abstract_of(screens.settings(dialog=True))
    assert page.coarse_key != with_dialog.coarse_key
    assert match(with_dialog, [_known(page, "page")]) is None


def test_selected_tab_makes_a_different_state(abstract_of):
    alarm = abstract_of(screens.clock("Alarm"), package=screens.CLOCK)
    timer = abstract_of(screens.clock("Timer"), package=screens.CLOCK)
    assert alarm.coarse_key != timer.coarse_key
    assert match(timer, [_known(alarm, "alarm")]) is None
    assert match(timer, [_known(alarm, "alarm"), _known(timer, "timer")]) == "timer"


@pytest.mark.parametrize("style", STYLES)
def test_keyboard_open_or_closed_is_one_state(abstract_of, style):
    closed = abstract_of(screens.settings(style=style))
    opened = abstract_of(screens.settings(style=style, keyboard=True))
    assert closed == opened


def test_typed_text_does_not_change_the_state(abstract_of):
    empty = abstract_of(screens.settings())
    typed = abstract_of(screens.settings(query="wifi 5ghz secret@example.com"))
    assert empty == typed


def test_helper_and_uiautomator_dumps_agree(abstract_of):
    ui = abstract_of(screens.settings(style="uiautomator"))
    helper = abstract_of(screens.settings(style="helper"))
    assert ui == helper


def test_activity_is_part_of_the_state(abstract_of):
    elements = screens.settings()
    assert abstract_of(elements, activity=".A") != abstract_of(elements, activity=".B")


def test_a_different_screen_in_the_same_activity_does_not_match(abstract_of):
    stored = _known(abstract_of(screens.settings()), "stored")
    other = abstract_of(screens.clock("Alarm"), activity=".Settings")
    assert match(other, [stored]) is None


def test_fuzzy_match_accepts_a_near_identical_screen(abstract_of):
    base = abstract_of(screens.settings())
    divider = screens.element("android.view.View", (0, 2300, 1080, 2320), rid="app:id/divider")
    near = abstract_of(screens.settings() + [divider])
    assert near.coarse_key != base.coarse_key
    assert match(near, [_known(base, "stored")]) == "stored"


def test_thin_accessibility_tree_is_opaque_and_matches_by_dhash(abstract_of):
    kwargs = {"package": GAME}
    first = abstract_of(screens.flutter_canvas(), dhash="ffff0000ffff0000", **kwargs)
    nearby = abstract_of(screens.flutter_canvas(), dhash="ffff0000ffff0003", **kwargs)
    far = abstract_of(screens.flutter_canvas(), dhash="0000ffff0000ffff", **kwargs)
    assert first.is_opaque
    assert match(nearby, [_known(first, "game")]) == "game"
    assert match(far, [_known(first, "game")]) is None


def test_opaque_screens_never_match_structured_states(abstract_of):
    structured = abstract_of(screens.settings(), dhash="ffff0000ffff0000")
    opaque = abstract_of(screens.flutter_canvas(), dhash="ffff0000ffff0000")
    assert match(opaque, [_known(structured, "s")]) is None
    assert match(structured, [_known(opaque, "o")]) is None


def test_system_chrome_is_not_part_of_the_state(abstract_of):
    with_bar = screens.settings()
    without_bar = [e for e in with_bar if e["package"] != "com.android.systemui"]
    assert abstract_of(with_bar) == abstract_of(without_bar)
