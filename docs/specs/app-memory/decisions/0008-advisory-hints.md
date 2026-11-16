---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0008: Routes are advisory, with a screen signature per hop

## Decision

A route is context for the Operator, never an instruction, and is never executed directly. Each
hop names the screen the agent should expect next, so the agent can tell when reality has
diverged. A per-milestone tracker advances, reroutes or hides the hint as the agent moves.

## Options considered

- **Plain path text.** Simple, but a stale route gets followed blindly.
- **Advisory with expected signatures and a tracker (chosen).**
- **Replaying known hops without the LLM.** The biggest speed win, but a wrong replay acts on the
  device with no judgement in the loop.

## Reason

ARTEMIS agents follow their prompts closely. A wrong hint without a way to detect divergence
would lower reliability, which is the opposite of the goal.

## Consequences

- Hints say "expect" and "check", never "must". Targets render as labels and ids, never
  coordinates, so the agent always grounds them on the live screen.
- Direct replay is a possible later phase, gated by the safety net and confirmed-edge confidence.
