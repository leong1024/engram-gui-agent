---
feature: app-memory
status: draft
depends_on:
  - ../shared/step-recording-fields.md
  - state-abstraction.md
  - data-model.md
  - decisions/0002-passive-harvesting-first.md
  - decisions/0004-live-plus-post-run-harvest.md
code:
  - artemis/app_memory/harvester.py
  - artemis/app_memory/describer.py
  - artemis/data_engine/engine.py
  - artemis/sdk/agent.py
---

# Harvesting

This note covers how recorded steps become states, edges and observations. It runs in three
phases: **live** during a run (cheap and provisional), **post-run** when the session ends
(confirm or discount), and **reconcile** for runs that ended without the post-run phase.
Descriptions and embeddings are made by background jobs in every phase.

Harvesting covers **both profiles**. Only routing is Pro-only in phase 1.

## Which steps become observations

A step contributes an observation when all of these hold:

- It executed at least one **device action**: click, long press, input text, swipe, key, app
  launch or stop, or open link. Steps with no executed action, steps the Planner rejected, and
  steps whose action was blocked by the safety net or failed to dispatch contribute nothing.
- Its pre-action screen and the **next** step's pre-action screen, in the same session, both
  abstract successfully. The screen after step N is what step N+1 observed before acting.
- Its `foreground_app` is not on the excluded package list: the launcher (resolved once per run
  from the HOME intent), `com.android.systemui`, and anything in config
  `agent.app_memory.harvest.exclude_packages`.

### Waits merge into the previous edge

If step N+1 is only `wait_for_delay`, step N's observation stays open. It closes at the first
following step that is not a wait, and that step's pre-screen is the destination. A loading
screen between an action and its result therefore never becomes a state.

### Bursts are macro edges

A Pro step that fired several actions back to back has unobserved intermediate screens. It
becomes one edge whose `actions` list holds the whole burst.

### Crossing apps

Maps are per app, so a transition between apps is split:

- **Leaving app A** (the destination's package differs from the source's): an edge from the
  source state to A's `@outside`.
- **Entering app B** through `manage_app` launch or `open_link`: an edge from B's `@outside` to
  the destination state.
- **Entering app B any other way**, for example a link tapped inside A: no entry edge, because
  the action means nothing from B's side.

### No-effect actions

If the destination matches the source state, the step records a **no-effect observation**: no
edge, but it counts against the reliability of edges with the same source and action (see
[data-model](data-model.md)).

## Action canonicalization

Each executed action is reduced to a `kind`, a `target` descriptor, non-variable `params` and an
optional `input_slot` (fields defined in [data-model](data-model.md)):

- **Index targets.** Both profiles already record the target's observed fields: Flash puts
  `target_semantics` at top level of `action_taken`, in the shape Pro records
  ([runner.py:663-695](../../../artemis/agents/flash/runner.py#L663-L695)). Those become the
  descriptor, with text masked by the rules in
  [state-abstraction](state-abstraction.md).
- **Coordinate targets.** The model's required `target_description` becomes the descriptor,
  plus `rel_bounds` from the coordinates.
- **Text input.** The typed text is discarded and `input_slot` is set to `"text"`. The describer
  may give it a better name, such as `"search query"`.

`action_signature = sha1(canonical JSON of [(kind, target identity, params, input_slot) ...])`.
Target identity is the first non-empty field of `resource_id`, masked `text`, `content_desc`
and normalized `target_description`. `rel_bounds` is left out of the signature, because layouts
shift between devices and screen sizes; it is kept only as a descriptor field.

## Phase 1: live

A **step listener** on the DataEngine calls `AppMemory.on_step_recorded(step, observation)`
after each `record_step`. The listener hook is new: `DataEngine.add_step_listener(callback)`. It
runs on the DataEngine's background scheduler, never on the agent's hot path.

On each call the harvester:

1. **Closes the previous step's observation, if one is open.** It matches or creates the
   destination state, upserts the edge, and inserts the observation with
   `status = provisional`.
2. **Opens an observation for this step,** if this step qualifies.
3. **Queues describer jobs** for any new state or edge.

The first call in a session inserts a `harvested_sessions` row with `status = live`.

## Phase 2: post-run

`AppMemory.finalize_session(session_id, outcome)` is called once the task status is known, from
`Agent._finalize_tracing_safely` ([sdk/agent.py:342](../../../artemis/sdk/agent.py#L342)). The
outcome is the DataEngine session status, refined by Pro's `run_outcome.json` when it exists. In
one transaction it sets every provisional observation of the session:

| Outcome | Observations become | Weight in routing |
|---|---|---|
| `completed` | `confirmed` | 1.0 |
| `partial`, `blocked`, `failed`, `cancelled` | `discounted` | 0.25 |

Then it recomputes the cached counts on the affected edges and marks the session `finalized`.

Transitions from a failed run were still seen on screen, so they are discounted, not dropped.
Failed runs are more often disturbed by popups, unexpected states or a wrongly identified
screen, which is why they count for less.

`dropped` is for observations that later turn out to be invalid. In phase 1 that means only
observations whose source or destination state was deleted by maintenance. The 0.25 weight is a
named constant.

## Phase 3: reconcile

`AppMemory.prepare_run()` runs at the start of every worker run, inside the device lock and
before the agent loop. It finds `harvested_sessions` rows still `live` whose DataEngine session
is terminal, or has no row at all and is more than 6 hours old. Each one is finalized with that
outcome, and with `failed` when there is no outcome.

This differs from the earlier idea of reconciling at Daemon startup. Standalone MCP runs and
in-process SDK runs often have no Daemon, so reconciling in `prepare_run` covers every mode.

`prepare_run` also re-queues up to 50 states and edges whose `description_status` is `pending`.

## Background description jobs

- A bounded job queue (concurrency 2), modeled on `StepMemoryService` in
  [step_memory.py](../../../artemis/memory/step_memory.py), runs the describer and then the
  embedding call. Jobs never block the run, and jobs unfinished at exit stay `pending`.
- The **state describer** is LLM node `app_memory_describer` (see
  [integration-pro](integration-pro.md)). Its input is the sample screenshot and the **masked**
  element list. It returns `title`, `purpose` (one or two sentences on what the screen is for)
  and `affordances` (what the user can do there). Its prompt forbids naming specific content
  seen in the screenshot, such as names, messages or numbers.
- The **edge describer** gets the source and destination titles and the canonical actions, and
  returns one sentence on what the action does. It needs no screenshot.
- After a description is written, the embedding job embeds it (see [retrieval](retrieval.md)).

## Backfill

`artemis app-memory backfill [--session ID | --all]` runs live and post-run harvesting over
sessions already in `data_engine.db`, using their recorded outcome. It is idempotent: an
existing `(session_id, step_id)` observation is skipped. Old Pro sessions harvest without
activity or version, and land in the `version_code = -1` bucket. Old Flash sessions lack a
structured pre-action tree and are skipped.

`artemis app-memory stats` prints states, edges and observation counts per map.

## Contracts

- **Harvesting never raises into the agent.** Every entry point catches, logs and continues.
- **Harvesting is idempotent per `(session_id, step_id)`.**
- **Self-exploration can be added later** as a session whose steps are harvested like any other.
  The only planned difference is an `ingress` marker it could be weighted by.

## Testing

All tests are hermetic, in `tests/unit/app_memory/`, using recorded step fixtures and
`FakeModel` ([fake_model.py](../../../artemis/llm/fake_model.py)) for the describer:

- **Transitions:** a scripted session of five steps gives the expected states, edges and
  provisional observations.
- **Filtering:** waits merge, a burst becomes one macro edge, and a no-effect step creates no
  edge.
- **Cross-app splitting:** the leave and launch-entry edges.
- **Outcomes:** finalizing `completed` confirms and `failed` discounts, and edge counts update.
- **Reconcile:** finalizes a `live` session whose DataEngine row is terminal.
- **Idempotence:** running backfill twice gives an identical database.
- **Isolation:** a harvester exception does not change the task's result.
