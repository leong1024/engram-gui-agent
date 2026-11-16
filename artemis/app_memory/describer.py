import base64
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from artemis.app_memory.document_store import DocumentStore
from artemis.app_memory.documents import Owner, OwnerKind, PendingEdge, PendingState
from artemis.memory.step_memory import JobKey, StepLens, StepMemoryService
from artemis.services.llm import acomplete_structured, raise_when_exhausted

DESCRIBER_CONCURRENCY = 2
NO_SPECIFICS = (
    "Describe it in general terms that hold every time it is shown. Never name specific "
    "content seen in the screenshot or the elements: no names of people or contacts, no "
    "message, email or typed text, no numbers, amounts, dates, times, addresses or accounts."
)
STATE_PROMPT = (
    "You name one screen of an Android app for a map of the app. You get a screenshot and the "
    "screen's elements, with variable content masked. Reply with JSON only: "
    '{"title": "2 to 5 words naming the screen", "purpose": "one or two sentences on what '
    'the screen is for", "affordances": ["short phrases of what the user can do there"]}. '
    + NO_SPECIFICS
)
EDGE_PROMPT = (
    "You describe one action in an Android app for a map of the app. You get the title of the "
    "screen before, the title of the screen after, and the actions taken. Reply with JSON "
    'only: {"description": "one sentence on what the action does, naming both screens"}. '
    + NO_SPECIFICS
)


class StateDescription(BaseModel):
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    affordances: list[str]

    def save(self, documents: DocumentStore, owner_id: str) -> None:
        documents.describe_state(owner_id, self.title, self.purpose, self.affordances)


class EdgeDescription(BaseModel):
    description: str = Field(min_length=1)

    def save(self, documents: DocumentStore, owner_id: str) -> None:
        documents.describe_edge(owner_id, self.description)


DESCRIPTIONS: dict[OwnerKind, tuple[str, type[StateDescription] | type[EdgeDescription]]] = {
    OwnerKind.STATE: (STATE_PROMPT, StateDescription),
    OwnerKind.EDGE: (EDGE_PROMPT, EdgeDescription),
}


def save_description(documents: DocumentStore, key: JobKey, summary: str) -> None:
    owner = Owner.parse(str(key))
    _, schema = DESCRIPTIONS[owner.kind]
    schema.model_validate_json(summary).save(documents, owner.owner_id)


def state_job(state: PendingState, image_path: Callable[[str], Path]) -> tuple[str, dict[str, Any]]:
    text = "\n".join(
        (
            f"App package: {state.package}",
            f"Activity: {state.activity or 'unknown'}",
            f"Elements (masked): {' | '.join(state.skeleton)}",
            f"Fixed labels: {', '.join(state.static_tokens)}",
        )
    )
    image = image_path(state.image_sha) if state.image_sha else None
    return Owner(OwnerKind.STATE, state.state_id).key, {"text": text, "image": image}


def edge_job(edge: PendingEdge) -> tuple[str, dict[str, Any]]:
    text = "\n".join(
        (
            f"Screen before: {edge.src_title}",
            f"Screen after: {edge.dst_title}",
            f"Actions: {json.dumps(list(edge.actions), sort_keys=True)}",
        )
    )
    return Owner(OwnerKind.EDGE, edge.edge_id).key, {"text": text, "image": None}


def _messages(prompt: str, payload: dict[str, Any]) -> list[BaseMessage]:
    content: list[str | dict[str, Any]] = [{"type": "text", "text": payload["text"]}]
    image: Path | None = payload["image"]
    if image is not None and image.is_file():
        encoded = base64.b64encode(image.read_bytes()).decode()
        url = f"data:image/jpeg;base64,{encoded}"
        content.append({"type": "image_url", "image_url": {"url": url}})
    return [SystemMessage(content=prompt), HumanMessage(content=content)]


class DescriptionLens(StepLens):
    """Describes one state or edge. `llm` builds the `app_memory_describer` model."""

    name = "app_memory_describer"

    def __init__(self, llm: Callable[[], Any]) -> None:
        self._llm = llm

    async def render(self, key: JobKey, payload: dict[str, Any]) -> str | None:
        prompt, schema = DESCRIPTIONS[Owner.parse(str(key)).kind]
        with raise_when_exhausted():
            parsed = await acomplete_structured(
                self._llm(), _messages(prompt, payload), schema=schema
            )
        return parsed.model_dump_json()


class DescriberService(StepMemoryService):
    """Runs description jobs in the background and hands each result, or each job that ran
    out of retries, to the callbacks."""

    def __init__(
        self,
        lens: StepLens,
        on_ready: Callable[[JobKey, str], None],
        on_failed: Callable[[JobKey], None],
        retry_limit: int = 3,
    ) -> None:
        super().__init__(
            None, lens=lens, max_concurrency=DESCRIBER_CONCURRENCY, retry_limit=retry_limit
        )
        self._ready = on_ready
        self._failed_job = on_failed

    def _on_ready(self, key: JobKey, summary: str) -> None:
        self._ready(key, summary)

    def _on_status(self, key: JobKey, status: str) -> None:
        if status == "failed":
            self._failed_job(key)
