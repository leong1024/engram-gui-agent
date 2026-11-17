---
feature: app-knowledge
status: accepted
date: 2026-11-17
supersedes: null
---

# 0004: Everything is derived from the databases at call time

## Decision

App knowledge stores nothing of its own. Every report is computed from `app_memory.db` and
`data_engine.db` when the tool is called.

## Options considered

- **Derived at call time (chosen)**: one source of truth, so nothing can drift.
- **A cached summary file or vault refreshed after each run**: faster reads, but a second copy
  that can go stale and must be kept in step with the database.

## Reason

The map changes after every harvested run. A summary that is rebuilt on each call cannot
disagree with the map. Summaries are small aggregates, so building them per call is cheap.

## Consequences

Each call pays its read cost. The probe also pays one embedding call and up to three map-graph
loads. Revisit with a cache only if measured call times are too slow for callers.
