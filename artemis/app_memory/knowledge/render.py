from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from artemis.app_memory.knowledge.reports import (
    AppSummary,
    Capabilities,
    KnowledgeReport,
    NotMapped,
    Overview,
    PageSummary,
    Profile,
)

MAX_TEXT_CHARS = 3_000
ITEM = "- "
SCOPE = "This covers only what Engram has seen in past runs, not everything an app can do."
CUT_NOTE = "More items were cut to keep this summary short."
USE_PRO = "Use profile `pro`."
EITHER = "Either profile works."


@dataclass(frozen=True, slots=True)
class Text:
    """A summary in three parts. Only `body` is cut, and only after a list item."""

    head: tuple[str, ...]
    body: tuple[str, ...]
    next_step: str


def render(report: KnowledgeReport) -> str:
    return _fit(RENDERERS[type(report)](report))


def _overview(report: Overview) -> Text:
    if not report.apps:
        return Text(
            ("# Apps Engram has mapped", "", "Engram has not mapped any app yet.", SCOPE),
            (),
            "Next: run tasks with profile `pro`. Engram maps each app those runs use.",
        )
    hints = () if report.hints_enabled else ("Route hints are off, so no profile uses the maps.",)
    pro = any(app.recommended_profile is Profile.PRO for app in report.apps)
    return Text(
        ("# Apps Engram has mapped", "", SCOPE, *hints),
        _section("Maps, most recently seen first:", map(_app_line, report.apps)),
        "Next: pass `app` with a package above to see what Engram has seen in it. "
        + (USE_PRO if pro else EITHER),
    )


def _capabilities(report: Capabilities) -> Text:
    app = report.app
    pending = () if report.pages else ("Descriptions are still pending, so no pages are listed.",)
    seen = (
        f"Engram has seen {_count(app.pages, 'described page')} and "
        f"{_count(app.routes, 'route')} in {_count(app.sessions, 'session')}. "
        f"Coverage: {report.coverage.value}. Last seen {_date(app.last_seen_at)}."
    )
    return Text(
        (f"# {_app_name(app)}", "", seen, SCOPE, *pending),
        (
            *_section("Capabilities seen:", report.capabilities),
            *_section("Goals of runs that completed:", report.example_goals),
            *_section("Pages, most visited first:", map(_page_line, report.pages)),
            *_section("Other versions seen:", map(_app_line, report.other_versions)),
        ),
        "Next: word the goal like a capability or a goal above. "
        + (USE_PRO if app.recommended_profile is Profile.PRO else EITHER),
    )


def _not_mapped(report: NotMapped) -> Text:
    return Text(
        (f"# `{report.package}` is not mapped", "", report.reason, SCOPE),
        (),
        "Next: call with no arguments to list the apps Engram knows, "
        "or run a task in this app with profile `pro` to map it.",
    )


RENDERERS: dict[type[KnowledgeReport], Callable[[Any], Text]] = {
    Overview: _overview,
    Capabilities: _capabilities,
    NotMapped: _not_mapped,
}


def _fit(text: Text) -> str:
    whole = _join(text.head, text.body, ("", text.next_step))
    if len(whole) <= MAX_TEXT_CHARS:
        return whole
    tail = ("", CUT_NOTE, text.next_step)
    ends = [end for end in range(len(text.body), 0, -1) if text.body[end - 1].startswith(ITEM)]
    cuts = (_join(text.head, text.body[:end], tail) for end in (*ends, 0))
    return next(cut for cut in cuts if len(cut) <= MAX_TEXT_CHARS)


def _join(*parts: Sequence[str]) -> str:
    return "\n".join(line for part in parts for line in part)


def _section(heading: str, items: Iterable[str]) -> tuple[str, ...]:
    lines = tuple(ITEM + " ".join(item.split()) for item in items)
    return ("", heading, *lines) if lines else ()


def _app_line(app: AppSummary) -> str:
    return (
        f"{_app_name(app)}: {_count(app.pages, 'page')}, {_count(app.routes, 'route')}, "
        f"{_count(app.sessions, 'session')}, last seen {_date(app.last_seen_at)}, "
        f"profile `{app.recommended_profile.value}`"
    )


def _app_name(app: AppSummary) -> str:
    name = f" ({app.version_name})" if app.version_name else ""
    return f"`{app.package}` version_code {app.version_code}{name}"


def _page_line(page: PageSummary) -> str:
    offers = f": {', '.join(page.capabilities)}" if page.capabilities else ""
    return f"{page.title} ({_count(page.visits, 'visit')}){offers}"


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).date().isoformat()
