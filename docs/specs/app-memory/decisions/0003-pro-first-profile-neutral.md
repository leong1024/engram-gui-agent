---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0003: Hints go to Pro first, through a profile-neutral interface

## Decision

Route hints are wired into the Pro graph in phase 1. The `AppMemory` interface takes plain
milestones and observations, so Flash can use it later without changes. Harvesting runs on both
profiles from the start.

## Options considered

- **Pro only.** The cleanest fit: the Planner already writes milestones before the Operator acts.
- **Both now.** Flash has no structured plan, only free-text milestones on turn 1
  (`flash_runner.md:11`), so it would need a new decomposition step.
- **Pro first, Flash in phase 2 (chosen).**

## Reason

Pro is the profile for long, deep flows, which is where the reliability gain is. Its milestones
are ready-made retrieval queries.

## Consequences

- Flash support needs a decomposition step that produces `Milestone` objects, and a prompt
  component in `FlashRunner._build_tail`.
- Flash runs feed the map from day one, so it will already have content when Flash hints arrive.
