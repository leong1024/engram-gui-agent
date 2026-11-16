import math
from collections import defaultdict
from dataclasses import dataclass

from artemis.app_memory.map_graph import GraphEdge, MapGraph
from artemis.app_memory.models import ActionSignature, EdgeId, StateId
from artemis.app_memory.routing.constants import (
    HOP_COST,
    OBSERVATION_WEIGHT,
    OPAQUE_COST,
    PRIOR_SUCCESSES,
    PRIOR_TRIALS,
)


@dataclass(frozen=True, slots=True)
class WeightedEdge:
    edge: GraphEdge
    probability: float
    cost: float


def edge_probability(edge_weight: float, action_weight: float) -> float:
    """p̂(e) under a Beta(1, 1) prior: `action_weight` counts every outcome of the action."""
    return (edge_weight + PRIOR_SUCCESSES) / (action_weight + PRIOR_TRIALS)


def edge_cost(probability: float, touches_opaque: bool) -> float:
    return -math.log(probability) + HOP_COST + (OPAQUE_COST if touches_opaque else 0.0)


def weigh(graph: MapGraph) -> dict[StateId, list[WeightedEdge]]:
    """Outgoing edges of each state with their probability and cost."""
    by_edge: dict[EdgeId, float] = defaultdict(float)
    by_action: dict[tuple[StateId, ActionSignature], float] = defaultdict(float)
    for tally in graph.tallies:
        weight = OBSERVATION_WEIGHT[tally.status] * tally.count
        by_action[tally.src, tally.signature] += weight
        if tally.edge_id is not None:
            by_edge[tally.edge_id] += weight
    adjacency: dict[StateId, list[WeightedEdge]] = defaultdict(list)
    for edge in graph.edges:
        probability = edge_probability(by_edge[edge.edge_id], by_action[edge.src, edge.signature])
        opaque = graph.states[edge.src].is_opaque or graph.states[edge.dst].is_opaque
        adjacency[edge.src].append(WeightedEdge(edge, probability, edge_cost(probability, opaque)))
    return adjacency
