---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0007: In-process library; the graph injects routes

## Decision

App memory is an in-process package (`artemis/app_memory/`) used by the worker. Routes reach the
Operator automatically: a graph node starts retrieval after the Planner, and a prompt component
renders the route for the active milestone.

## Options considered

- **In-process, graph-injected (chosen).** Works in every run mode and adds no service. Routes
  arrive when a milestone becomes active.
- **An agent tool `recall_route(subgoal)`.** Leaves the graph untouched, but the agent has to
  decide to ask, and it rarely asks when it is lost, which is the case this feature targets.
- **A Daemon-hosted service.** A single writer, but standalone MCP and in-process SDK runs often
  have no Daemon.

## Reason

Reliability comes from the route arriving at the right moment, not on request.

## Consequences

- One new graph node and one new prompt component.
- A `recall_route` tool can be added later on top of the same library if it proves useful.
