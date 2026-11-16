---
feature: app-memory
status: draft
depends_on:
  - harvesting.md
  - retrieval.md
  - routing-and-hints.md
  - decisions/0003-pro-first-profile-neutral.md
  - decisions/0007-in-process-graph-injected.md
code:
  - artemis/app_memory/__init__.py
  - artemis/app_memory/service.py
  - artemis/context.py
  - artemis/sdk/agent.py
  - artemis/data_engine/engine.py
  - artemis/graph/graph.py
  - artemis/agents/operator/operator.py
  - artemis/agents/operator/prompts.py
  - artemis/config/agent.py
  - artemis/config/llm.py
  - config/artemis.jsonc
  - artemis/interfaces/cli/main.py
---

# Integration (Pro)

This note covers where app memory plugs into the existing system: the service object, the run
lifecycle, the Pro graph, the Operator prompt, config and the CLI.

## Package layout

```
artemis/app_memory/
  __init__.py       AppMemory facade, open_app_memory(ctx)
  service.py        AppMemory: the profile-neutral interface below
  store.py          the only module that touches app_memory.db
  abstraction.py    state abstraction and matching
  harvester.py      live, post-run and reconcile
  describer.py      background description jobs
  embeddings.py     EmbeddingProvider and providers
  retrieval.py      two-tier target search
  routing.py        localization, weights, Dijkstra, RouteTracker
  hints.py          rendering a Route into prompt text
```

## Profile-neutral interface

```python
class AppMemory:
    async def prepare_run(self, *, device_serial: str) -> None: ...
    def on_step_recorded(self, step: StepRecord, observation: ScreenObservation) -> None: ...
    async def finalize_session(self, session_id: str, outcome: str) -> None: ...
    def request_targets(self, goal: str, milestones: list[Milestone]) -> None: ...
    def route_for(self, milestone_key: str, observation: ScreenObservation) -> Route | None: ...
    async def close(self) -> None: ...
```

- **Harvesting** uses `prepare_run`, `on_step_recorded`, `finalize_session` and `close`. It runs
  for every profile.
- **Hints** use `request_targets` and `route_for`. Only the Pro graph calls them in phase 1.
- **Flash later** calls the same two methods, with milestones from its own decomposition step.
  No change to this interface is needed.

## Run lifecycle

The wiring lives in [sdk/agent.py](../../../artemis/sdk/agent.py) and the shared base in
`third_party/mobile_use/sdk/agent.py`:

1. **Open.** After the DataEngine session starts (`_prepare_tracing`), set
   `ctx.app_memory = open_app_memory(ctx)`. This returns a no-op instance when
   `agent.app_memory.enabled` is false. `ArtemisContext` ([context.py](../../../artemis/context.py))
   gains the `app_memory` attribute.
2. **Prepare.** Call `await ctx.app_memory.prepare_run(device_serial=...)`. This happens inside
   the device lock, before the agent loop. It loads installed versions, reconciles stale
   sessions and re-queues pending descriptions.
3. **Listen.** Register `ctx.data_engine.add_step_listener(ctx.app_memory.on_step_recorded)`.
   The listener hook is new in the DataEngine and runs on its background scheduler.
4. **Finalize.** In `_finalize_tracing_safely`, once the task status is resolved, call
   `await ctx.app_memory.finalize_session(session_id, outcome)` and then `close()`. `close`
   waits at most 5 s for in-flight description jobs; the rest stay `pending`.

Every call is wrapped so that an app memory error is logged and never changes the task result.

## Pro graph

The wiring is in `get_graph()` ([graph.py](../../../artemis/graph/graph.py)).

**New node `app_memory_targets`** between `planner` and the convergence node:

```
START → planner → app_memory_targets → convergence → …   (rest unchanged)
```

The node reads `task_plan` with `parse_plan` and calls `ctx.app_memory.request_targets(goal,
top-level milestones)`. It returns immediately, without writing to `State`, because retrieval
runs in the background. If app memory is disabled the node is not added, and `planner` connects
to the convergence node directly, as today.

**Plan edits.** In `_process_plan_write`, after a write is accepted (where `milestones_changed`
is evaluated today, [graph.py:714](../../../artemis/graph/graph.py#L714)), call
`request_targets` again with the new plan. The service runs retrieval only for milestone keys it
has not seen and drops keys that disappeared.

**State.** Nothing is added to `State`. It is `extra="forbid"` and checkpointed, and the route
cache is per-run service data held on `ctx.app_memory`.

## Operator prompt component

**New `AppMemoryRoutePromptComponent`** in
[prompts.py](../../../artemis/agents/operator/prompts.py):

1. Read the active milestone from the plan with `PlanSnapshot.active_milestone()`. If there is
   none, render nothing.
2. Build a `ScreenObservation` from `state.operator_raw_data`, the current perception output.
   Activity and version come from the recording fields in
   [step-recording-fields](../shared/step-recording-fields.md).
3. Call `ctx.app_memory.route_for(milestone_key, observation)`. This runs the `RouteTracker` step
   from [routing-and-hints](routing-and-hints.md).
4. If a route exists, add the rendered hint with `builder.add_human_content(text,
   ephemeral=True)`. Ephemeral blocks are scrubbed from older observations by the transcript's
   existing ephemeral-block handling, so stale routes never pile up in context.
5. If retrieval for the milestone has not finished yet, render nothing this turn. The hint
   appears on a later turn once it is ready.

**Placement** is directly after `PlanRecitationPromptComponent`, in both component lists in
[operator.py](../../../artemis/agents/operator/operator.py): the transcript path
(`_build_prompt_transcript`, around line 419) and the legacy path (around line 246). The route
reads as part of the plan context.

**Static prompt.** One sentence goes into the Operator system template, gated on app memory
being enabled, so the model knows what the block means. It reads roughly: "An 'App Memory: Known
Route' block, when present, is a route learned from earlier runs. Use it as a guide and verify
each screen; your own observation always wins."

## Config

**New section `agent.app_memory`** in `config/artemis.jsonc`, with a matching
`AppMemoryConfig` model in [config/agent.py](../../../artemis/config/agent.py):

```jsonc
"app_memory": {
  "enabled": true,                 // master switch: false disables harvesting and hints
  "harvest": {
    "enabled": true,
    "exclude_packages": []         // in addition to the launcher and systemui
  },
  "hints": {
    "enabled": true,               // Pro only in phase 1
    "max_hops": 15,
    "max_rendered_hops": 8
  },
  "retrieval": {
    "top_k": 20,
    "similarity_floor": 0.35,
    "min_confidence": 0.5,
    "fallback_versions": 2,
    "budget_seconds": 20
  },
  "embedding": {
    "provider": "gemini",          // gemini | openai | ollama
    "model": "<current Gemini embedding model>",
    "dimensions": null
  }
}
```

**Two new LLM nodes** in the existing per-node config ([config/llm.py](../../../artemis/config/llm.py)
and the `nodes` section of `artemis.jsonc`):

- `app_memory_describer`: needs vision, and defaults to the run's default model.
- `app_memory_selector`: text only, defaults to the run's default model, temperature 0.

Both go through `get_llm(ctx, name)`, so they inherit the existing retry, fallback and pause
handling in [services/llm.py](../../../artemis/services/llm.py).

## CLI

`artemis app-memory` is a new Typer sub-app in
[interfaces/cli/main.py](../../../artemis/interfaces/cli/main.py):

- `backfill [--session ID | --all]`: harvest existing sessions (see
  [harvesting](harvesting.md)).
- `stats`: states, edges and observations per map.

## Failure handling

- **Disabled:** `open_app_memory` returns a no-op object, so call sites need no checks.
- **Any exception inside app memory:** logged with the session id, and the run continues
  without hints.
- **Database locked or corrupt:** app memory disables itself for the run with one warning.

## Testing

- **Graph wiring:** with app memory enabled, `planner` routes through `app_memory_targets`;
  with it disabled, the graph is identical to today's.
- **Prompt component:** it renders nothing with no active milestone, nothing before retrieval
  finishes, and the golden hint once it has.
- **Isolation:** with app memory raising on every call, a scripted Pro run against
  `MockDeviceDriver` still completes with the same result.
- **Lifecycle:** a scripted run with `FakeModel` creates and finalizes a `harvested_sessions` row
  and its observations.
