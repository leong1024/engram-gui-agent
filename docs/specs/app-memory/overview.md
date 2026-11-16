---
feature: app-memory
status: draft
depends_on:
  - ../shared/step-recording-fields.md
code: []
---

# Overview

## Problem

Each ARTEMIS task explores and plans from nothing. On a deep or unusual flow, for example a
setting four menus down, the agent can wander, take wrong branches and fail, even when an
earlier run already walked that exact path. Within one run the agent remembers well (transcript
compression, `search_history`), but nothing survives into the next run.

## Goal

**Reliability**: more tasks succeed on deep or obscure flows, because the agent starts each
milestone knowing where the target screen is and how it was reached before.

Speed and token savings are welcome side effects, not the goal.

## How it works, in one pass

1. **Harvest.** Every step the agent takes on any profile becomes a transition: the screen
   before, the action, the screen after. Screens are abstracted into states (see
   [state-abstraction](state-abstraction.md)) and written to a per-app-version map, provisionally
   during the run and confirmed after it (see [harvesting](harvesting.md)).
2. **Describe and embed.** In the background, each new state gets a short LLM description of
   what the screen is for and what can be done there. Each new edge gets a description of what
   the action does. Both are embedded (see [retrieval](retrieval.md)).
3. **Retrieve targets.** After the Pro Planner writes the plan, each milestone is searched in
   two tiers. Tier 1 runs vector search and an LLM rerank inside each candidate map. Tier 2 has
   an LLM choose among the maps' proposals. The installed app version is searched first, and
   older versions only as a fallback.
4. **Route.** When a milestone becomes active, the current screen is located in the map and
   Dijkstra finds the most reliable path to the target (see
   [routing-and-hints](routing-and-hints.md)).
5. **Hint.** The route goes into the Operator's prompt as advisory context, with the expected
   screen at each hop. The Operator still decides every action, and the Validator still checks
   it (see [integration-pro](integration-pro.md)).

## Scope (phase 1)

- Harvesting from Flash and Pro runs.
- Per-version maps with version columns, so maps can merge later.
- Retrieval and routing for Pro milestones.
- Route hints in the Pro Operator prompt.
- Config switches to disable harvesting and hints separately.
- The recording fix in [step-recording-fields](../shared/step-recording-fields.md).

## Non-goals (phase 1)

- **Self-exploration** (`artemis explore <app>`). The design leaves room for it: an exploration
  run is a session whose steps are harvested like any other.
- **Hints for Flash.** The interface is profile-neutral so Flash can be added later.
- **Executing routes without the LLM.** Hops are hints, never replayed directly.
- **Merging maps across versions.** Only borrowing a route from an older version.
- **Privacy masking beyond what state abstraction already drops.**
- **A measurement harness.** See [0009](decisions/0009-no-measurement-phase-1.md).
- **Human demonstrations by touch.** "Teaching" means a user prompting tasks, which harvest
  like any other run. The on-device helper does not change.

## Glossary

- **Map**: the states and edges of one app at one `versionCode`.
- **State**: an abstracted screen. Structure and static text are kept; variable content such as
  list items, numbers and typed text is masked out.
- **Virtual state**: `@outside`, one per app, meaning "not in this app". Launch and deep-link
  edges start there.
- **Edge**: an observed transition from one state to another through an action, or a burst of
  actions. It carries a target descriptor that can be found again on a later visit.
- **Observation**: one step's evidence for an edge. Provisional until its run ends, then
  confirmed, discounted or dropped.
- **Route**: a path of edges from the current state to a target state.
- **Hint**: a route rendered into the Operator prompt.
- **Borrowed route**: a route taken from an older version's map because the installed version's
  map had no target.

## Naming

The repo already has `artemis/memory/` and the `agent.memory` config section. Those are
**within-run** history compression. This feature is **cross-run** and is called `app_memory`
everywhere, in the package, config and prompt labels, so the two are never confused.
