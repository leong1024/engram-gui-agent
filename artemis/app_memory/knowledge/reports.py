from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class Coverage(StrEnum):
    SPARSE = "sparse"
    PARTIAL = "partial"
    BROAD = "broad"


class Profile(StrEnum):
    PRO = "pro"
    EITHER = "either"


class Level(StrEnum):
    OVERVIEW = "overview"
    CAPABILITIES = "capabilities"
    NOT_MAPPED = "not_mapped"
    PROBE = "probe"


class ProbeStatus(StrEnum):
    FOUND = "found"
    NO_MATCH = "no_match"
    NO_MAPS = "no_maps"
    NO_VECTORS = "no_vectors"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    EMPTY_QUERY = "empty_query"


class FrozenReport(BaseModel):
    model_config = ConfigDict(frozen=True)


class AppSummary(FrozenReport):
    """One map: a package at one `version_code`. `pages` counts described pages."""

    package: str
    version_code: int
    version_name: str | None
    pages: int
    routes: int
    sessions: int
    last_seen_at: float
    recommended_profile: Profile


class PageSummary(FrozenReport):
    title: str
    capabilities: tuple[str, ...]
    visits: int


class Overview(FrozenReport):
    """The newest map of each package, most recently seen first."""

    apps: tuple[AppSummary, ...]
    hints_enabled: bool


class Capabilities(FrozenReport):
    """What Engram has seen in the newest map of one package."""

    app: AppSummary
    coverage: Coverage
    pages: tuple[PageSummary, ...]
    capabilities: tuple[str, ...]
    example_goals: tuple[str, ...]
    other_versions: tuple[AppSummary, ...]


class NotMapped(FrozenReport):
    package: str
    reason: str


class ProbeCandidate(FrozenReport):
    """A page whose description is near the query. `similarity` is the vector search's cosine
    similarity, not a selector's confidence. `borrowed` marks an older version's map."""

    package: str
    version_code: int
    page: str
    similarity: float
    hops_from_launch: int | None
    borrowed: bool


class ProbeResult(FrozenReport):
    """`found` holds the closest pages, most similar first. Every other status holds none."""

    query: str
    status: ProbeStatus
    candidates: tuple[ProbeCandidate, ...] = ()

    @model_validator(mode="after")
    def _found_has_candidates(self) -> Self:
        if (self.status is ProbeStatus.FOUND) != bool(self.candidates):
            raise ValueError("only a found probe holds candidates, and it holds at least one")
        return self


KnowledgeReport = Overview | Capabilities | NotMapped | ProbeResult

LEVELS: dict[type[KnowledgeReport], Level] = {
    Overview: Level.OVERVIEW,
    Capabilities: Level.CAPABILITIES,
    NotMapped: Level.NOT_MAPPED,
    ProbeResult: Level.PROBE,
}


class KnowledgeResponse(FrozenReport):
    """Every report under one schema: the field named by `level` holds it, the rest are null."""

    level: Level
    overview: Overview | None = None
    capabilities: Capabilities | None = None
    not_mapped: NotMapped | None = None
    probe: ProbeResult | None = None

    @classmethod
    def of(cls, report: KnowledgeReport) -> "KnowledgeResponse":
        level = LEVELS[type(report)]
        return cls.model_validate({"level": level, level.value: report})

    @model_validator(mode="after")
    def _holds_its_level(self) -> Self:
        filled = {level for level in Level if getattr(self, level.value) is not None}
        if filled != {self.level}:
            raise ValueError(f"level {self.level.value} must hold exactly its own report")
        return self
