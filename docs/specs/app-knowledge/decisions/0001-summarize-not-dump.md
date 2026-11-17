---
feature: app-knowledge
status: accepted
date: 2026-11-17
supersedes: null
---

# 0001: Return summaries, never a dump of the map

## Decision

`mobile_get_knowledge` returns ranked, capped summaries of what Engram has seen. It never returns
every state and edge of a map.

## Options considered

- **Summaries with caps (chosen)**: small enough to read in one call, and they say what to ask.
- **Every state of every app**: complete, but hundreds or thousands of entries that a calling
  agent cannot read and that do not say what to ask.

## Reason

A calling agent needs to know what it can ask, not how the map is stored. A dump costs context
and still leaves the agent to work out the useful parts.

## Consequences

Ranking and caps decide what a caller sees. Pages that rank low never appear, so every report
states its coverage. Revisit if callers ask for pages the summaries drop.
