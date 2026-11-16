---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0009: No measurement harness in phase 1

## Decision

Phase 1 ships without a dedicated evaluation harness. Separate switches,
`agent.app_memory.harvest.enabled` and `agent.app_memory.hints.enabled`, let harvesting and hints
be turned off independently.

## Options considered

- **Build a with/without comparison on repeated tasks first.** It gives evidence, but delays the
  feature.
- **Ship with switches only (chosen).**

## Reason

The project owner expects the feature to improve reliability and chose to invest in the feature
rather than the harness.

## Consequences

- If a regression is suspected, turning `hints.enabled` off is the first diagnostic step, because
  it keeps harvesting running.
- `artemis app-memory stats` gives basic visibility into map growth.
- Revisit if hint quality is disputed. A with/without A/B run on repeated tasks would then be
  the next step.
