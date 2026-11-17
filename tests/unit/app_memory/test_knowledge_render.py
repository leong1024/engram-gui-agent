import pydantic
import pytest

from artemis.app_memory.knowledge import render
from artemis.app_memory.knowledge.reports import (
    AppSummary,
    Capabilities,
    Coverage,
    KnowledgeResponse,
    Level,
    Overview,
    PageSummary,
    Profile,
)
from artemis.app_memory.knowledge.summaries import not_mapped

SETTINGS = AppSummary(
    package="com.android.settings",
    version_code=34,
    version_name="14",
    pages=12,
    routes=5,
    sessions=3,
    last_seen_at=1_700_000_000.0,
    recommended_profile=Profile.PRO,
)
CLOCK = AppSummary(
    package="com.google.android.deskclock",
    version_code=2,
    version_name=None,
    pages=1,
    routes=0,
    sessions=1,
    last_seen_at=1_699_000_000.0,
    recommended_profile=Profile.EITHER,
)
OLD_SETTINGS = CLOCK.model_copy(
    update={"package": SETTINGS.package, "version_code": 33, "pages": 4, "routes": 1}
)
NEXT_STEP = "Next: word the goal like a capability or a goal above. Use profile `pro`."


def report(**fields: object) -> Capabilities:
    defaults: dict[str, object] = {
        "app": SETTINGS,
        "coverage": Coverage.PARTIAL,
        "pages": (),
        "capabilities": (),
        "example_goals": (),
        "other_versions": (),
    }
    return Capabilities.model_validate(defaults | fields)


def test_overview_golden():
    assert render(Overview(apps=(SETTINGS, CLOCK), hints_enabled=True)) == (
        "# Apps Engram has mapped\n"
        "\n"
        "This covers only what Engram has seen in past runs, not everything an app can do.\n"
        "\n"
        "Maps, most recently seen first:\n"
        "- `com.android.settings` version_code 34 (14): 12 pages, 5 routes, 3 sessions, "
        "last seen 2023-11-14, profile `pro`\n"
        "- `com.google.android.deskclock` version_code 2: 1 page, 0 routes, 1 session, "
        "last seen 2023-11-03, profile `either`\n"
        "\n"
        "Next: pass `app` with a package above to see what Engram has seen in it. "
        "Use profile `pro`."
    )


def test_empty_overview_golden():
    assert render(Overview(apps=(), hints_enabled=True)) == (
        "# Apps Engram has mapped\n"
        "\n"
        "Engram has not mapped any app yet.\n"
        "This covers only what Engram has seen in past runs, not everything an app can do.\n"
        "\n"
        "Next: run tasks with profile `pro`. Engram maps each app those runs use."
    )


def test_capabilities_golden():
    display = PageSummary(
        title="Display", capabilities=("Turn on dark theme", "Change brightness"), visits=4
    )
    text = render(
        report(
            pages=(display, PageSummary(title="Home", capabilities=(), visits=0)),
            capabilities=("Turn on dark theme", "Change brightness"),
            example_goals=("Email my battery level to <EMAIL>",),
            other_versions=(OLD_SETTINGS,),
        )
    )
    assert text == (
        "# `com.android.settings` version_code 34 (14)\n"
        "\n"
        "Engram has seen 12 described pages and 5 routes in 3 sessions. Coverage: partial. "
        "Last seen 2023-11-14.\n"
        "This covers only what Engram has seen in past runs, not everything an app can do.\n"
        "\n"
        "Capabilities seen:\n"
        "- Turn on dark theme\n"
        "- Change brightness\n"
        "\n"
        "Goals of runs that completed:\n"
        "- Email my battery level to <EMAIL>\n"
        "\n"
        "Pages, most visited first:\n"
        "- Display (4 visits): Turn on dark theme, Change brightness\n"
        "- Home (0 visits)\n"
        "\n"
        "Other versions seen:\n"
        "- `com.android.settings` version_code 33: 4 pages, 1 route, 1 session, "
        "last seen 2023-11-03, profile `either`\n"
        "\n"
        f"{NEXT_STEP}"
    )


def test_not_mapped_golden():
    assert render(not_mapped("com.example.unknown")) == (
        "# `com.example.unknown` is not mapped\n"
        "\n"
        "Engram has no map of this package from any run it has harvested.\n"
        "This covers only what Engram has seen in past runs, not everything an app can do.\n"
        "\n"
        "Next: call with no arguments to list the apps Engram knows, "
        "or run a task in this app with profile `pro` to map it."
    )


def test_a_long_report_is_cut_after_the_last_list_item_that_fits():
    capabilities = tuple(f"capability {i} " + "word " * 18 for i in range(20))
    goals = tuple(f"goal {i} " + "longer word " * 15 for i in range(5))
    items = [f"- {' '.join(text.split())}" for text in (*capabilities, *goals)]

    text = render(report(capabilities=capabilities, example_goals=goals))

    shown = [line for line in text.splitlines() if line.startswith("- ")]
    assert 0 < len(shown) < len(items)
    assert shown == items[: len(shown)]
    assert len(text) <= 3_000
    assert len(text) + len(items[len(shown)]) + 1 > 3_000
    assert "cut" in text.splitlines()[-2]
    assert text.endswith(NEXT_STEP)


def test_the_response_holds_exactly_the_report_its_level_names():
    overview = Overview(apps=(SETTINGS,), hints_enabled=True)
    response = KnowledgeResponse.of(overview)
    assert (response.level, response.overview, response.capabilities) == (
        Level.OVERVIEW,
        overview,
        None,
    )
    with pytest.raises(pydantic.ValidationError):
        KnowledgeResponse(level=Level.CAPABILITIES, overview=overview)
