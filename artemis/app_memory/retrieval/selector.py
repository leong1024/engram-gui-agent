from collections.abc import Callable, Sequence
from typing import Any, Protocol

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from artemis.app_memory.milestones import Milestone
from artemis.app_memory.retrieval.types import Candidate
from artemis.services.llm import acomplete_structured, raise_when_exhausted
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)

SELECTOR_NODE = "app_memory_selector"
SELECTOR_PROMPT = (
    "You pick the screen of an Android app that a task milestone is trying to reach. You get "
    "the task goal, the milestone, and candidate screens from maps of apps built in earlier "
    "runs. Reply with JSON only: "
    '{"state_id": "the state_id of the candidate that is the milestone\'s target screen, or '
    'null when none of them is", "confidence": "a number from 0 to 1", "reason": "one '
    'sentence"}.'
)


class Selection(BaseModel):
    state_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class Selector(Protocol):
    async def select(
        self, goal: str, milestone: Milestone, candidates: Sequence[Candidate]
    ) -> Selection | None: ...


def selector_messages(
    goal: str, milestone: Milestone, candidates: Sequence[Candidate]
) -> list[BaseMessage]:
    shown = "\n".join(_candidate_lines(candidate) for candidate in candidates)
    text = f"Task goal: {goal}\nMilestone: {milestone.query}\nCandidates:\n{shown}"
    return [SystemMessage(content=SELECTOR_PROMPT), HumanMessage(content=text)]


def _candidate_lines(candidate: Candidate) -> str:
    card, map_id = candidate.card, candidate.map_id
    lines = [
        f"- state_id: {card.state_id}",
        f"  app: {map_id.package} v{map_id.version_code}",
        f"  title: {card.title}",
        f"  purpose: {card.purpose}",
        f"  you can: {'; '.join(card.affordances)}",
        f"  visits: {card.visits}",
    ]
    if candidate.last_hop is not None and candidate.last_hop.description:
        lines.append(f"  last step there: {candidate.last_hop.description}")
    return "\n".join(lines)


class LLMSelector:
    """The `app_memory_selector` node. `llm` builds the model, at temperature 0."""

    def __init__(self, llm: Callable[[], Any]) -> None:
        self._llm = llm

    async def select(
        self, goal: str, milestone: Milestone, candidates: Sequence[Candidate]
    ) -> Selection | None:
        messages = selector_messages(goal, milestone, candidates)
        try:
            with raise_when_exhausted():
                return await acomplete_structured(self._llm(), messages, schema=Selection)
        except Exception as exc:
            logger.warning(f"App memory selector failed for milestone {milestone.key}: {exc!r}")
            return None
