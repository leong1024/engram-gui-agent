---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0002: Harvest passively first; self-exploration later

## Decision

In phase 1 the map grows only from tasks users prompt, on any profile. A self-exploration mode
is out of scope, but nothing in the design blocks adding it.

## Options considered

- **Passive only.** Every edge comes from goal-directed use. Coverage grows slowly.
- **Passive plus `artemis explore <app>`.** Better up-front coverage, but it needs an exploration
  policy, and wandering adds noisy edges.
- **Passive now, with room for exploration (chosen).**

## Reason

Reliability depends on correct edges more than on many edges. An exploration policy is a design
of its own.

## Consequences

- An exploration run will be a session whose steps are harvested like any other, optionally
  weighted by an `ingress` marker.
- "Teaching" means a user prompting tasks. The on-device helper does not need to capture human
  touches.
