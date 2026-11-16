from typing import Any

from tests.unit.app_memory.fixtures.parts import (
    CLOCK,
    Element,
    IME,
    SETTINGS,
    chrome_parts,
    dialog_parts,
    element,
    keyboard_parts,
    list_parts,
    rows_parts,
    search_bar_parts,
    status_bar_parts,
)

SCROLL_TOP = ["Network & internet", "Connected devices", "Apps", "Notifications"]
SCROLL_BOTTOM = ["Battery 87%", "Storage 12.4 GB used", "Sound & vibration", "About phone"]


def settings(
    scroll: str = "top",
    *,
    style: str = "uiautomator",
    keyboard: bool = False,
    dialog: bool = False,
    query: str = "",
) -> list[Element]:
    labels = SCROLL_TOP if scroll == "top" else SCROLL_BOTTOM
    elements = (
        status_bar_parts(style) + chrome_parts("Settings", style) + search_bar_parts(style, query)
    )
    elements += list_parts(rows_parts(labels, style), style)
    if keyboard:
        elements += keyboard_parts(style)
    if dialog:
        elements += dialog_parts(style)
    return elements


def feed(items: list[str], *, style: str = "uiautomator") -> list[Element]:
    package = "com.google.android.youtube"
    elements = status_bar_parts(style) + chrome_parts("YouTube", style, package)
    elements += [
        element(
            "android.widget.EditText",
            (200, 100, 900, 220),
            rid="yt:id/search",
            text="Search YouTube",
            package=package,
            editable=True,
            style=style,
        )
    ]
    return elements + list_parts(rows_parts(items, style, package), style, package)


def clock(tab: str, *, style: str = "uiautomator") -> list[Element]:
    kw: dict[str, Any] = {"style": style, "package": CLOCK}
    elements = chrome_parts("Clock", style, CLOCK)
    elements.append(
        element(
            "com.google.android.material.bottomnavigation.BottomNavigationView",
            (0, 2100, 1080, 2340),
            rid="clock:id/nav",
            **kw,
        )
    )
    for index, name in enumerate(["Alarm", "Clock", "Timer", "Stopwatch"]):
        left = index * 270
        elements.append(
            element(
                "android.widget.FrameLayout",
                (left, 2100, left + 270, 2340),
                rid=f"clock:id/nav_{name.lower()}",
                desc=name,
                clickable=True,
                selected=name == tab,
                **kw,
            )
        )
    return elements


def messages(people: dict[str, str], *, style: str = "uiautomator") -> list[Element]:
    package = "com.google.android.apps.messaging"
    rows = rows_parts([f"{name}: {body}" for name, body in people.items()], style, package)
    header = chrome_parts("Messages", style, package)
    return header + list_parts(rows, style, package)


def flutter_canvas(*, style: str = "uiautomator") -> list[Element]:
    return [
        element(
            "android.widget.FrameLayout",
            (0, 0, 1080, 2340),
            package="com.example.game",
            style=style,
        ),
        element("android.view.View", (0, 0, 1080, 2340), package="com.example.game", style=style),
    ]
