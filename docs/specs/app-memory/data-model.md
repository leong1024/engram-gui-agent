---
feature: app-memory
status: draft
depends_on:
  - state-abstraction.md
  - decisions/0001-per-version-maps.md
  - decisions/0006-embedded-vector-index.md
code:
  - artemis/app_memory/store.py
  - artemis/app_memory/queries.py
  - artemis/app_memory/rows.py
  - artemis/app_memory/transaction.py
  - artemis/app_memory/document_store.py
  - artemis/app_memory/document_queries.py
---

# Data model

All map data lives in one SQLite file, `app_memory.db`, in the same traces directory as
`data_engine.db` (`settings.TRACES_PATH`). It runs in WAL mode, so several workers can write at
once, the same pattern `data_engine.db` uses. It is a separate file because it outlives
individual traces: `make clean` deletes `traces/`, and the map should survive. Implementation
should move it to the app data directory if `traces/` turns out to be cleaned routinely.

## Map identity

A map is the pair `(package, version_code)`. There is no `maps` table. Every state and edge row
carries both columns, and "the map" is a filter on them. Merging maps later means relaxing that
filter, with no migration (see [0001](decisions/0001-per-version-maps.md)).

`version_code` is `-1` when it was unknown at harvest time, for example on old records. That
bucket is searched last and never preferred over a real version.

## Tables

### `app_versions`

| Column | Type | Notes |
|---|---|---|
| `package` | TEXT | PK part |
| `version_code` | INTEGER | PK part |
| `version_name` | TEXT | nullable |
| `first_seen_at`, `last_seen_at` | REAL | epoch seconds |

### `states`

| Column | Type | Notes |
|---|---|---|
| `state_id` | TEXT PK | `sha1(package, version_code, coarse_key, cluster_ordinal)` |
| `package`, `version_code` | | map identity |
| `activity` | TEXT | nullable |
| `coarse_key` | TEXT | see [state-abstraction](state-abstraction.md) |
| `skeleton` | JSON | masked structural tokens, used for fuzzy matching |
| `static_tokens` | JSON | masked static text tokens |
| `is_opaque` | BOOL | tree too thin; identity from perceptual hash |
| `dhash` | TEXT | representative pre-image dHash |
| `title` | TEXT | short human label from the describer |
| `purpose`, `affordances` | TEXT, JSON | describer output |
| `description_status` | TEXT | `pending`, `ready` or `failed` |
| `sample_session_id`, `sample_step_id`, `sample_image_sha` | | a real occurrence, for screenshots and debugging |
| `visit_count` | INTEGER | confirmed and provisional observations |
| `first_seen_at`, `last_seen_at` | REAL | |
| `is_virtual` | BOOL | true for `@outside` |

One virtual `@outside` state exists per map. Its `state_id` is `sha1(package, version_code,
"@outside")`.

### `edges`

| Column | Type | Notes |
|---|---|---|
| `edge_id` | TEXT PK | `sha1(src_state_id, action_signature, dst_state_id)` |
| `package`, `version_code` | | map identity |
| `src_state_id`, `dst_state_id` | TEXT | FKs to `states`; `src != dst` |
| `action_signature` | TEXT | hash of the canonical action list; see [harvesting](harvesting.md) |
| `actions` | JSON | ordered list; more than one item is a burst (macro edge) |
| `description` | TEXT | describer output |
| `description_status` | TEXT | as for states |
| `confirmed_n`, `discounted_n`, `provisional_n` | INTEGER | cached observation counts |
| `last_seen_at` | REAL | |

Each item in `actions` holds:
- `kind`: canonical action name, for example `click`, `long_press`, `input_text`, `swipe`,
  `press_key`, `manage_app` or `open_link`.
- `target`: a descriptor that can be found again (below), or null for keys and launches.
- `params`: non-variable arguments, such as swipe direction, key name or package.
- `input_slot`: a placeholder name such as `"query"` when the action typed text, or null.
  Typed text is never stored.

A **target descriptor** holds `resource_id`, `text` (masked), `content_desc`, `class`,
`rel_bounds` (0-1000, bucketed to 50) and `target_description` (the model's own words for a
coordinate target). Every field is optional, but at least one must be set.

### `observations`

The per-step evidence. This table makes harvesting idempotent and lets the post-run pass
re-weight a whole session.

| Column | Type | Notes |
|---|---|---|
| `session_id`, `step_id` | TEXT | PK; one observation per step |
| `edge_id` | TEXT | nullable; null for no-effect observations |
| `src_state_id`, `action_signature` | TEXT | always set; denominator for edge probability |
| `status` | TEXT | `provisional`, `confirmed`, `discounted` or `dropped` |
| `recorded_at` | REAL | |

A **no-effect observation** is an action from a known state that left the agent on the same
state. It has no edge, but it counts against every edge sharing its `(src_state_id,
action_signature)`.

### `harvested_sessions`

| Column | Type | Notes |
|---|---|---|
| `session_id` | TEXT PK | DataEngine session id |
| `status` | TEXT | `live` or `finalized` |
| `outcome` | TEXT | nullable; `completed`, `partial`, `blocked`, `failed` or `cancelled` |
| `finalized_at` | REAL | nullable |

### Vectors

- `embedding_models(model_id TEXT PK, provider, model, dim)`.
- One sqlite-vec `vec0` table per embedding model, because `vec0` columns have a fixed
  dimension: `vec_<model_slug>(owner_kind TEXT, owner_id TEXT, embedding float[dim])`.
  `owner_kind` is `state` or `edge`.
- `embeddings(owner_kind, owner_id, model_id, text_hash, created_at)`, where PK is `owner_kind,
  owner_id, model_id`. `text_hash` detects a description change that needs re-embedding.

Changing the configured model creates a new `vec_` table. Old vectors are kept until a re-embed
job fills the new one. Retrieval only reads the current model's table.

## Implementation notes (P3)

- `put_state` takes an optional sample and writes `sample_session_id`, `sample_step_id` and
  `sample_image_sha` on first insert only. `visit_count` is not maintained yet.
- The observation of an entry edge has the step id with an `@entry` suffix, so a step that
  enters another app has two observations.
- `finalize_session` settles only `provisional` observations, refreshes the counts of the
  session's edges and keeps the first `outcome` and `finalized_at`.
- `map_stats` counts states and edges per `app_versions` row, and observations by the map of
  their source state, so no-effect observations count too.
- Row mapping lives in `rows.py`. `store.py` keeps every statement that touches the database.

## Contracts

- `store.py` is the only module that touches `app_memory.db`. Everything else goes through its
  functions.
- Writes are short transactions; no transaction spans an LLM call.
- `confirmed_n`, `discounted_n` and `provisional_n` are a cache of `observations` and can be
  rebuilt from it at any time.

## Testing

- Schema creation and idempotent re-creation on an existing file.
- Rebuilding edge counts from `observations` matches the cached counts.
- Two writer processes on one file, with no lost writes; the same pattern as the DataEngine
  storage tests.
