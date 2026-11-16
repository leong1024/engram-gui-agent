from typing import Any

SETTINGS = "com.android.settings"
CLOCK = "com.google.android.deskclock"
IME = "com.google.android.inputmethod.latin"

Element = dict[str, Any]


def element(
    cls: str,
    bounds: tuple[int, int, int, int],
    *,
    rid: str = "",
    text: str = "",
    desc: str = "",
    package: str = SETTINGS,
    style: str = "uiautomator",
    **flags: bool,
) -> Element:
    left, top, right, bottom = bounds
    names = ("clickable", "scrollable", "checkable", "selected", "editable")
    values = {name: flags.get(name, False) for name in names}
    rendered: dict[str, Any] = (
        {k: str(v).lower() for k, v in values.items()} if style == "uiautomator" else values
    )
    return {
        "resource-id": rid,
        "text": text,
        "content-desc": desc,
        "class": cls,
        "package": package,
        "bounds": f"[{left},{top}][{right},{bottom}]",
        "parsed_bounds": {"left": left, "top": top, "right": right, "bottom": bottom},
        **rendered,
    }


def status_bar_parts(style: str) -> list[Element]:
    return [
        element(
            "android.widget.FrameLayout",
            (0, 0, 1080, 80),
            rid="com.android.systemui:id/status_bar",
            package="com.android.systemui",
            style=style,
        ),
        element(
            "android.widget.TextView",
            (40, 10, 200, 70),
            text="10:42",
            package="com.android.systemui",
            style=style,
        ),
    ]


def chrome_parts(title: str, style: str, package: str = SETTINGS) -> list[Element]:
    kw: dict[str, Any] = {"style": style, "package": package}
    return [
        element("android.widget.FrameLayout", (0, 0, 1080, 2340), rid="android:id/content", **kw),
        element("android.view.ViewGroup", (0, 80, 1080, 240), rid="app:id/toolbar", **kw),
        element(
            "android.widget.TextView", (120, 100, 800, 220), rid="app:id/title", text=title, **kw
        ),
        element(
            "android.widget.ImageButton",
            (0, 100, 120, 220),
            rid="app:id/nav_up",
            desc="Navigate up",
            clickable=True,
            **kw,
        ),
    ]


def rows_parts(labels: list[str], style: str, package: str = SETTINGS) -> list[Element]:
    rows: list[Element] = []
    for index, label in enumerate(labels):
        top = 400 + index * 160
        kw: dict[str, Any] = {"style": style, "package": package}
        rows.append(
            element(
                "android.widget.LinearLayout",
                (0, top, 1080, top + 150),
                rid="app:id/row",
                clickable=True,
                **kw,
            )
        )
        rows.append(
            element(
                "android.widget.TextView",
                (40, top + 10, 800, top + 80),
                rid="app:id/row_title",
                text=label,
                **kw,
            )
        )
    return rows


def list_parts(rows: list[Element], style: str, package: str = SETTINGS) -> list[Element]:
    container = element(
        "androidx.recyclerview.widget.RecyclerView",
        (0, 300, 1080, 2300),
        rid="app:id/list",
        scrollable=True,
        style=style,
        package=package,
    )
    return [container, *rows]


def search_bar_parts(style: str, text: str = "") -> list[Element]:
    field = element(
        "android.widget.EditText",
        (40, 260, 1040, 380),
        rid="app:id/search",
        text=text or "Search settings",
        editable=True,
        style=style,
    )
    return [{**field, "hint": "Search settings"}]


def keyboard_parts(style: str) -> list[Element]:
    return [
        element(
            "android.inputmethodservice.SoftInputWindow",
            (0, 1500, 1080, 2340),
            package=IME,
            style=style,
        ),
        element(
            "android.widget.FrameLayout",
            (0, 1500, 1080, 2340),
            rid=f"{IME}:id/keyboard_view",
            package=IME,
            style=style,
        ),
    ]


def dialog_parts(style: str) -> list[Element]:
    kw: dict[str, Any] = {"style": style}
    return [
        element(
            "android.app.AlertDialog", (100, 800, 980, 1500), rid="android:id/parentPanel", **kw
        ),
        element(
            "android.widget.TextView",
            (140, 840, 940, 940),
            rid="android:id/alertTitle",
            text="Turn on Wi-Fi?",
            **kw,
        ),
        element(
            "android.widget.Button",
            (140, 1380, 520, 1480),
            rid="android:id/button2",
            text="Cancel",
            clickable=True,
            **kw,
        ),
        element(
            "android.widget.Button",
            (560, 1380, 940, 1480),
            rid="android:id/button1",
            text="OK",
            clickable=True,
            **kw,
        ),
    ]
