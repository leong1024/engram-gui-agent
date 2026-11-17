---
feature: app-knowledge
status: draft
depends_on:
  - interface.md
  - ../app-memory/data-model.md
code:
  - artemis/app_memory/knowledge/
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
