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
    ProbeCandidate,
    ProbeResult,
    ProbeStatus,
    Profile,
)

MAX_TEXT_CHARS = 3_000
ITEM = "- "
SCOPE = "This covers only what Engram has seen in past runs, not everything an app can do."
CUT_NOTE = "More items were cut to keep this summary short."
USE_PRO = "Use profile `pro`."
EITHER = "Either profile works."
SIMILARITY = (
    "Similarity is how close a page's description is to the goal in a vector search. "
    "It is not a promise that a task will succeed, and a real run can pick another page."
)
NO_ROUTE_NEEDED = "A task can still run without a known route."
PROBE_TEXT: dict[ProbeStatus, tuple[str, str]] = {
    ProbeStatus.FOUND: (
        "Engram has seen pages close to this goal.",
        "Next: run the task with the goal worded like the top page. "
        "Pass `app` with its package to see what else Engram has seen there.",
    ),
    ProbeStatus.NO_MATCH: (
        "No page Engram has seen is close enough to this goal.",
        "Next: call with no arguments to list the apps Engram knows, and word the goal like "
        f"what they offer. {NO_ROUTE_NEEDED}",
    ),
    ProbeStatus.NO_MAPS: (
        "Engram has no map to search.",
        "Next: run tasks with profile `pro`. Engram maps each app those runs use.",
    ),
    ProbeStatus.NO_VECTORS: (
        "Engram's maps have no vectors for the configured embedding model, so it cannot "
        "search them.",
        "Next: check that the configured embedding model is the one the maps were embedded "
        f"with. {NO_ROUTE_NEEDED}",
    ),
    ProbeStatus.PROVIDER_UNAVAILABLE: (
        "The embedding provider did not answer, so Engram could not search its maps.",
        f"Next: check the embedding API key and network, then probe again. {NO_ROUTE_NEEDED}",
    ),
    ProbeStatus.EMPTY_QUERY: (
        "The query is empty, so there is nothing to search for.",
        'Next: pass `query` with the goal in a few words, such as "turn on dark theme".',
    ),
}


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


def _probe(report: ProbeResult) -> Text:
    summary, next_step = PROBE_TEXT[report.status]
    similarity = (SIMILARITY,) if report.candidates else ()
    return Text(
        (f'# Route probe for "{" ".join(report.query.split())}"', "", summary, *similarity, SCOPE),
        _section("Closest pages, most similar first:", map(_candidate_line, report.candidates)),
        next_step,
    )


RENDERERS: dict[type[KnowledgeReport], Callable[[Any], Text]] = {
    Overview: _overview,
    Capabilities: _capabilities,
    NotMapped: _not_mapped,
    ProbeResult: _probe,
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


def _candidate_line(candidate: ProbeCandidate) -> str:
    hops = candidate.hops_from_launch
    route = "no known route from launch" if hops is None else f"{_count(hops, 'hop')} from launch"
    borrowed = (
        ", from an older version because the newest had no match" if candidate.borrowed else ""
    )
    return (
        f"{candidate.page} in `{candidate.package}` version_code {candidate.version_code}: "
        f"similarity {candidate.similarity:.2f}, {route}{borrowed}"
    )


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).date().isoformat()
