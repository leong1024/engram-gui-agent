from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from artemis.app_memory import hints
from artemis.app_memory.interface import AppMemoryService
from artemis.app_memory.live_screen import current_screen
from artemis.app_memory.milestones import plan_milestones
from artemis.config.agent import load_agent_config
from artemis.utils.plan_grammar import parse_plan

if TYPE_CHECKING:
    from artemis.data_engine.engine import DataEngine


def hints_enabled() -> bool:
    try:
        return load_agent_config().app_memory.hints_on
    except ValueError:
        return False


def request_plan_targets(memory: AppMemoryService, goal: str, plan_text: str) -> None:
    """Starts retrieval for the plan's milestones in the background and returns at once. An empty
    plan requests nothing, because a request drops the milestones it does not name."""
    milestones = plan_milestones(parse_plan(plan_text))
    if milestones:
        memory.request_targets(goal, milestones)


def route_hint(
    memory: AppMemoryService,
    engine: "DataEngine | None",
    plan_text: str | None,
    perception: Mapping[str, Any] | None,
) -> str | None:
    """The rendered route for the active milestone, or None until one is known."""
    milestone = parse_plan(plan_text).active_milestone()
    screen = current_screen(engine, perception) if milestone else None
    route = memory.route_for(milestone.key, screen) if milestone and screen else None
    return hints.render(route) if route else None
