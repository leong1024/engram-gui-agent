import functools

from langgraph.graph import StateGraph

from artemis.app_memory.plan_routes import hints_enabled, request_plan_targets
from artemis.context import ArtemisContext
from artemis.graph.state import State
from artemis.utils.notes import get_note_file_path
from third_party.mobile_use.graph import CONVERGENCE_NODE

APP_MEMORY_NODE = "app_memory_targets"


def request_route_targets(ctx: ArtemisContext, state: State | None, plan_text: str) -> None:
    if hints_enabled():
        request_plan_targets(ctx.app_memory, state.initial_goal if state else "", plan_text)


async def app_memory_targets_node(state: State, ctx: ArtemisContext) -> dict:
    request_plan_targets(ctx.app_memory, state.initial_goal, _read_plan(ctx))
    return {}


def add_app_memory_node(graph_builder: StateGraph, ctx: ArtemisContext) -> str:
    """Adds the node when hints are on, and returns the node the planner hands over to."""
    if not hints_enabled():
        return CONVERGENCE_NODE
    graph_builder.add_node(APP_MEMORY_NODE, functools.partial(app_memory_targets_node, ctx=ctx))
    graph_builder.add_edge(APP_MEMORY_NODE, CONVERGENCE_NODE)
    return APP_MEMORY_NODE


def _read_plan(ctx: ArtemisContext) -> str:
    if ctx.data_engine is None:
        return ""
    path = get_note_file_path(ctx.data_engine.base_dir, "task_plan")
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
