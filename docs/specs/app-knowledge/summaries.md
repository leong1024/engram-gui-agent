---
feature: app-knowledge
status: draft
depends_on:
  - interface.md
  - ../app-memory/data-model.md
code:
  - artemis/app_memory/knowledge/
  - artemis/app_memory/knowledge_queries.py
  - artemis/app_memory/knowledge_store.py
  - artemis/app_memory/store.py
  - artemis/app_memory/trace_reader.py
---

# Summaries

This note specifies how the overview and capability reports are built from `app_memory.db` and
`data_engine.db`.

## Behaviour

### Overview

One `AppSummary` per map, read in one pass over the store:

- `pages`: described, non-virtual states of the map.
- `routes`: edges of the map with at least one confirmed observation.
- `sessions`: distinct harvested sessions that observed the map.
- `last_seen_at`: the newest `last_seen_at` among the map's states.
- `recommended_profile`: `pro` when hints are enabled and the map has vectors for the current
  embedding model. Otherwise `either`.

Maps are sorted by `last_seen_at`, newest first. Only the newest version of each package is
listed. Older versions appear as `other_versions` in that package's capability report.

### Capabilities

For one package, the report uses the newest map:

1. **Pages.** Read the map's described pages with their visit counts. Rank by visits. The
   visit count is the number of confirmed and provisional arrivals by an edge, the same count
   the route hint uses. `states.visit_count` is not maintained, so it is not used. Keep the top 8.
2. **Capabilities.** Gather every affordance of every page. Normalize case and whitespace,
   drop duplicates, and rank each by the visits of the best page that offers it. Keep the top 20.
3. **Example goals.** Find sessions that observed the map and finished with outcome `completed`.
   Read each session's `initial_goal` from `data_engine.db` through `TraceReader`, which stays
   the only reader of that file. Mask each goal with the app-memory text masking rules.
   Drop duplicates, newest first, and keep 5.
4. **Coverage.** `sparse` below 10 pages. `partial` below 30 pages or when fewer than half the
   pages are described. `broad` otherwise. The thresholds are named constants.

## Contracts

- Every read is a read-only query. The module never writes either database.
- The summaries need no embedding provider and no LLM. They work with no API key.
- Pages whose description is `pending` or `failed` are counted for coverage but not listed.

## Failure handling

- **`data_engine.db` missing or unreadable**: `example_goals` is empty and the rest of the
  report still returns.
- **A map with no described pages**: the report lists no pages, coverage is `sparse`, and the
  text says descriptions are still pending.

## Implementation notes (K1)

K1 follows the code where this note was silent or did not match it. Each item keeps the intent
of the sections above.

- **Current embedding model.** The configured `provider`, `model` and `dimensions` select the
  newest matching row of `embedding_models`. A null `dimensions` matches any. This is the lookup
  enrichment already uses, so no provider is called and no key is needed. A map has vectors when
  any of its states or edges has an `embeddings` row under that model.
- **Newest version.** The newest map of a package is the one with the highest `version_code`.
  An unknown version, `-1`, sorts lowest. Retrieval orders older versions the same way. The
  overview then sorts these maps by `last_seen_at`.
- **`last_seen_at`.** A map with no real states falls back to `app_versions.last_seen_at`.
- **`routes`.** Edges whose stored `confirmed_n` is above zero.
- **Coverage.** A map with no described pages is `sparse` at any size, as the failure handling
  above says. That check runs before the page thresholds.
- **Capabilities and example goals.** Both drop duplicates the same way: by case, after
  whitespace is collapsed. The first text kept is shown as written, not lowercased. Goals are
  masked before that check.
- **Example goals read at most 50 sessions.** The newest 50 completed sessions of the map, by
  `harvested_sessions.finalized_at`, are read for the 5 goals. This bounds the reads of
  `data_engine.db`. A `sqlite3.Error` from those reads leaves `example_goals` empty.
- **Where the reads happen.** `summaries.py` holds pure functions that take the store reads as
  arguments. `Knowledge` in `service.py` does the reads. It picks the newest version and returns
  `NotMapped` when there is none. The interface in [interface](interface.md) is unchanged.
- **Read-only connections.** Both databases open with SQLite's `mode=ro`, and neither file
  changes. SQLite still creates empty `-wal` and `-shm` files next to a WAL database when no
  writer holds them, and a read-only connection cannot remove them. The `data_engine.db` reader
  already behaves this way. See [0004](decisions/0004-derived-read-only.md).
- **One `Knowledge` per request.** It holds its connections until `close()`, and it is a context
  manager. A database that was missing when it opened stays missing for it.
- **Report types.** `recommended_profile` is a `Profile` enum and `level` is a `Level` enum.
  `other_versions` is a list of `AppSummary`, newest version first. `version_name` is always
  null today, because nothing writes `app_versions.version_name`. The text shows it only when
  it is set.
- **No probe yet.** `KnowledgeResponse` has no `probe` level or field in K1. K2 adds both.
- **Text order.** The capability report lists capabilities, then example goals, then pages,
  then other versions. The cut drops list items from the end, so pages and other versions go
  before capabilities and goals. A cut text says so on the line before the next step.
