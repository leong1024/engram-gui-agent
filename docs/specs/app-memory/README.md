---
feature: app-memory
status: draft
depends_on:
  - ../shared/step-recording-fields.md
code:
  - artemis/app_memory/
  - artemis/graph/graph.py
  - artemis/agents/operator/operator.py
  - artemis/agents/operator/prompts.py
  - artemis/sdk/agent.py
  - artemis/config/agent.py
  - config/artemis.jsonc
---

# App memory

ARTEMIS starts every task from scratch: nothing it learned about an app in earlier runs carries
over. App memory builds a map of each app version from what the agent actually observes. The
map's states are screens with variable content masked out, and its edges are the actions that
moved between them. For each plan milestone, the agent searches the map for the target screen,
finds a route from the current screen with Dijkstra, and passes the route to the Pro Operator as
an advisory hint. Execution itself is unchanged.

## Status

Draft. Design agreed in conversation on 2026-11-16. The
[implementation plan](implementation-plan.md) splits the build into six stacked PRs, P1 to P6,
and waits for the operator's go.

## Reading order

1. [overview](overview.md): problem, goal, scope, non-goals, glossary.
2. [data-model](data-model.md): the map database, tables, versioning, vectors.
3. [state-abstraction](state-abstraction.md): turning a screen into a state, and matching it.
4. [harvesting](harvesting.md): live provisional writes, post-run confirmation, reconcile.
5. [retrieval](retrieval.md): descriptions, embeddings, two-tier target search.
6. [routing-and-hints](routing-and-hints.md): localization, Dijkstra, hint format, divergence.
7. [integration-pro](integration-pro.md): graph node, Operator prompt component, config.
8. [implementation-plan](implementation-plan.md): the six PRs, their checks, and the
   corrections to this spec found while planning.

## Decisions

| # | Decision |
|---|---|
| [0001](decisions/0001-per-version-maps.md) | One map per app version, with version columns so maps can merge later. |
| [0002](decisions/0002-passive-harvesting-first.md) | Harvest from tasks users prompt; self-exploration later. |
| [0003](decisions/0003-pro-first-profile-neutral.md) | Hints go to Pro first, through a profile-neutral interface. |
| [0004](decisions/0004-live-plus-post-run-harvest.md) | Write provisional edges live, confirm or discount them after the run. |
| [0005](decisions/0005-configurable-embeddings.md) | Embedding provider set in config, Gemini by default. |
| [0006](decisions/0006-embedded-vector-index.md) | Vectors in SQLite with sqlite-vec, no server. |
| [0007](decisions/0007-in-process-graph-injected.md) | In-process library; the graph injects routes, not an agent tool. |
| [0008](decisions/0008-advisory-hints.md) | Routes are advisory, with a screen signature per hop. |
| [0009](decisions/0009-no-measurement-phase-1.md) | No measurement harness in phase 1; an on/off switch only. |

## Depends on

- [step-recording-fields](../shared/step-recording-fields.md): the structured pre-action tree,
  activity and `versionCode` on every step. Harvesting cannot identify states without it.

## Open questions

- **Default on or off.** Harvesting makes one describer LLM call per new state and edge. The
  draft defaults both harvesting and hints to on. Confirm.
- **Thresholds.** The match, similarity and weight constants in
  [state-abstraction](state-abstraction.md) and [routing-and-hints](routing-and-hints.md) are
  starting values, to be tuned on real traces.
- **Opaque screens.** Flutter, game and Canvas screens with almost no accessibility tree fall
  back to perceptual hashes (see [state-abstraction](state-abstraction.md)). Whether that is good
  enough is unknown until tried.
- **sqlite-vec on all CI platforms.** It must install from wheels on Ubuntu and Windows with
  Python 3.12. If not, retrieval falls back to brute-force numpy (see
  [0006](decisions/0006-embedded-vector-index.md)).
