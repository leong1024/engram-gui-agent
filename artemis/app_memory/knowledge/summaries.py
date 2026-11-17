from collections.abc import Iterable, Sequence

from artemis.app_memory.abstraction.masking import mask_text
from artemis.app_memory.knowledge.reports import (
    AppSummary,
    Capabilities,
    Coverage,
    NotMapped,
    Overview,
    PageSummary,
    Profile,
)
from artemis.app_memory.knowledge_store import MapCounts
from artemis.app_memory.map_graph import StateCard

MAX_APPS = 30
MAX_PAGES = 8
MAX_CAPABILITIES = 20
MAX_EXAMPLE_GOALS = 5
# Completed sessions read for example goals: enough for five distinct ones, never every run.
GOAL_SESSIONS = 50
SPARSE_BELOW_PAGES = 10
PARTIAL_BELOW_PAGES = 30
MIN_DESCRIBED_SHARE = 0.5
NOT_MAPPED_REASON = "Engram has no map of this package from any run it has harvested."


def overview(maps: Iterable[MapCounts], hints_enabled: bool) -> Overview:
    newest = sorted(_newest_versions(maps), key=lambda m: (-m.last_seen_at, m.map_id.package))
    apps = tuple(app_summary(counts, hints_enabled) for counts in newest[:MAX_APPS])
    return Overview(apps=apps, hints_enabled=hints_enabled)


def versions_of(maps: Iterable[MapCounts], package: str) -> list[MapCounts]:
    """The package's maps, newest version first."""
    versions = (counts for counts in maps if counts.map_id.package == package)
    return sorted(versions, key=lambda counts: counts.map_id.version_code, reverse=True)


def capabilities(
    versions: Sequence[MapCounts],
    pages: Iterable[StateCard],
    goals: Iterable[str],
    hints_enabled: bool,
) -> Capabilities:
    """`versions` newest first, `pages` and `goals` (newest first) of the newest version."""
    newest, *older = versions
    ranked = sorted(pages, key=lambda card: (-card.visits, card.title, card.state_id))
    offered = (affordance for card in ranked for affordance in card.affordances)
    return Capabilities(
        app=app_summary(newest, hints_enabled),
        coverage=coverage(newest.states, newest.described),
        pages=tuple(_page(card) for card in ranked[:MAX_PAGES]),
        capabilities=_distinct(offered, MAX_CAPABILITIES),
        example_goals=_distinct(map(mask_text, goals), MAX_EXAMPLE_GOALS),
        other_versions=tuple(app_summary(counts, hints_enabled) for counts in older),
    )


def not_mapped(package: str) -> NotMapped:
    return NotMapped(package=package, reason=NOT_MAPPED_REASON)


def coverage(states: int, described: int) -> Coverage:
    if states < SPARSE_BELOW_PAGES or described == 0:
        return Coverage.SPARSE
    if states < PARTIAL_BELOW_PAGES or described < states * MIN_DESCRIBED_SHARE:
        return Coverage.PARTIAL
    return Coverage.BROAD


def app_summary(counts: MapCounts, hints_enabled: bool) -> AppSummary:
    profile = Profile.PRO if hints_enabled and counts.has_vectors else Profile.EITHER
    return AppSummary(
        package=counts.map_id.package,
        version_code=counts.map_id.version_code,
        version_name=counts.version_name,
        pages=counts.described,
        routes=counts.routes,
        sessions=counts.sessions,
        last_seen_at=counts.last_seen_at,
        recommended_profile=profile,
    )


def _newest_versions(maps: Iterable[MapCounts]) -> Iterable[MapCounts]:
    newest: dict[str, MapCounts] = {}
    for counts in sorted(maps, key=lambda counts: counts.map_id.version_code):
        newest[counts.map_id.package] = counts
    return newest.values()


def _page(card: StateCard) -> PageSummary:
    return PageSummary(title=card.title, capabilities=card.affordances, visits=card.visits)


def _distinct(texts: Iterable[str], limit: int) -> tuple[str, ...]:
    """The first of each text that differs only in case or whitespace, in order."""
    shown: dict[str, str] = {}
    for text in texts:
        collapsed = " ".join(text.split())
        if collapsed:
            shown.setdefault(collapsed.casefold(), collapsed)
    return tuple(shown.values())[:limit]
