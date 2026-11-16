---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0011: One shared routing map per app map per run, kept current from harvest writes

## Decision

A run holds one `RoutingMap` per `MapId` in a `MapGraphCache`: the loaded `MapGraph` and its
weighted `PathFinder`. Every milestone whose target is in that map routes over it. After each
live harvest pass and each finalize, the store worker re-reads only the rows that the session
touched in each loaded map, merges them into the map, rebuilds weights and the `PathFinder` in
memory, and swaps the new `RoutingMap` in by reference. `route_for` reads only memory.

This supersedes the "the map is a snapshot" note in [routing](../routing-and-hints.md): a screen
harvested earlier in the run is now localized and routed in the same run.

## Measurements

One container with 4 cores, Python 3.13, `app_memory.db` on local disk in WAL mode. A synthetic
map of 2,000 states and 7,999 edges with 11,958 observations, written through `MapBuilder`.
Medians over 20 runs, in ms. The lane scripts were throwaway and are not in the repository.

| Step | 2,000 states | 200 states |
|---|---|---|
| `GraphStore.map_graph` (SQL and row decoding) | 173 to 217 | 12 |
| `weigh` | 19 to 23 | 0.9 |
| `PathFinder` build | 15 to 17 | 0.5 |
| One `shortest` query | 0.5 to 0.65 | 0.04 |
| Full reload and rebuild | 257 to 313 | 25 |
| Refresh, session touched 10 sources | 52 | |
| Refresh, session touched 50 sources | 65 | 8 |
| Refresh, session touched 100 sources | 75 to 88 | |
| Refresh, nothing changed | 0.01 to 0.08 | 0.03 |

What limits each number:

- **Reload.** A profile of `map_graph` puts about half of it in Python row decoding: each of the
  8,000 edges parses its action JSON into `CanonicalAction` and `TargetDescriptor` objects. The
  four SQL statements take about 88 ms together, led by the tally `GROUP BY` and the per-state
  arrival count. One thread does all of it, so it scales with the map, not with the change.
- **Refresh.** The slice is the session's rows, so its SQL and decoding scale with the states
  the session observed from (2 ms for 10, 21 ms for 100, where the per-card arrival count
  leads). What is left is the in-memory rebuild, about 40 ms at 8,000 edges: one Python object
  per edge in `weigh` and one `add_edge` call per arc in the `PathFinder`.
- **Unchanged.** One indexed `GROUP BY` over the session's own observations.

## Options considered

- **Reload on change.** Simple, and it cannot drift from the database. It costs 257 to 313 ms
  per change on a 2,000-state map, against a budget of about 30 ms, and the cost is in work
  that does not depend on what changed. Rejected for large maps. At 200 states it is 25 ms and
  would have done.
- **Fully incremental (chosen in part).** Re-read only the rows that a session touched. Rows
  are the expensive part, so this is where the change is incremental.
- **Incremental weights and paths.** Re-weigh only the touched sources and patch the
  rustworkx graph. Not done. The staleness tie-break is normalized over the whole map. A newly
  seen edge is usually the newest one, which moves the tie-break of every arc, so the
  `PathFinder` would be rebuilt anyway. A
  full re-weigh also recomputes every edge that shares a source and action with a new
  observation, with no rule to get wrong.

## How a change is found

- `GraphStore.session_marks(session_id)` gives, per map, how many observations the session has
  there and how many are still provisional. A session only adds observations or settles them,
  so any write it makes moves its mark. The cache keeps the last mark per session and map, and
  skips a map whose mark did not move.
- `GraphStore.session_slice(map_id, session_id)` reads every tally and edge of the states the
  session observed from, and the cards and screens of both ends of those edges.
  `MapGraph.merged` swaps them in and sorts rows the way a fresh load does, so a merged map
  equals a reload. A test checks this after a live pass and after finalize.
- `observations` gains the index `idx_observations_src` on `src_state_id`, so the slice does
  not scan every observation in the database.

## Concurrency

The store worker is the only thread that writes to the cache: it loads maps and swaps in
rebuilt ones. The event loop only reads. A `RoutingMap` is immutable and replaced by reference,
so a reader gets the old map or the new one and needs no lock. A tracker takes the current map
on each step. Its route from an older map keeps advancing because state ids are stable, and the
next reroute uses the newer map.

## Consequences

- Three milestones in one map load and weigh it once.
- A refresh costs up to about 90 ms of worker time on a 2,000-state map, and about 8 ms on a
  200-state map, each time a harvest pass writes to a loaded map. It never runs on the event
  loop, though its Python work shares the GIL with it.
- Only this run's own writes are picked up. A write by another process, such as a backfill or
  a second worker, reaches the map at the next run.
- A description written by the background describer reaches a card only when a later harvest
  pass touches that state again, or at the next run.
