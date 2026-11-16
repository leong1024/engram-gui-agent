---
feature: app-memory
status: draft
depends_on:
  - state-abstraction.md
  - retrieval.md
  - data-model.md
  - decisions/0008-advisory-hints.md
code:
  - artemis/app_memory/routing/constants.py
  - artemis/app_memory/routing/types.py
  - artemis/app_memory/routing/weights.py
  - artemis/app_memory/routing/paths.py
  - artemis/app_memory/routing/planner.py
  - artemis/app_memory/routing/tracker.py
  - artemis/app_memory/hints.py
  - artemis/app_memory/map_graph.py
  - artemis/app_memory/graph_store.py
  - artemis/app_memory/graph_queries.py
---

# Routing and hints

This note covers turning a `TargetResolution` and the current screen into a route, rendering it
for the Operator, and keeping it honest as the agent moves. Nothing here calls an LLM. It is
graph search over SQLite rows, cheap enough to run every Operator turn.

## Localization

`locate(observation, map) -> Source` runs the matcher from
[state-abstraction](state-abstraction.md) on the current perception: package, activity, cached
`version_code`, elements and dHash.

| Situation | Source |
|---|---|
| The current package is the target's package, and the screen matches a state | That state |
| The current package differs from the target's | The target map's `@outside` |
| The current package is the target's, but the screen matches no state | The target map's `@outside`, flagged `from_launch` |
| The current state is the target | Arrived |

For a borrowed target, localization runs against the older version's map. If the screen
doesn't match there, the source is that map's `@outside`, also flagged `from_launch`.

## Edge weights

For an edge `e` from `src` through action signature `a`:

- Each observation's weight is 1.0 if confirmed, 0.25 if discounted, 0.5 if provisional and 0
  if dropped.
- `w(e)` is the weight of `e`'s observations.
- `W(src, a)` is the weight of **every** observation with that source and action. That includes
  observations that reached other destinations, and no-effect observations.
- `p̂(e) = (w(e) + 1) / (W(src, a) + 2)`, a Beta(1,1) prior. One confirmed observation gives
  0.67; an action that works 9 times out of 10 gives about 0.83.
- `cost(e) = −ln p̂(e) + 0.1 + 0.3 · [src or dst is opaque]`

So the cheapest route is the one most likely to work, with a small per-hop cost so that, between
equally reliable routes, the shorter one wins. All constants are named in `routing.py`.

## Path search

- Dijkstra from the source to the target over that map's edges, with at most **15** hops.
- Edges from `@outside` exist only for launch and deep-link actions (see
  [harvesting](harvesting.md)), so every `from_launch` route starts by opening the app.
- **No path:** the hint still describes the target screen, because knowing what the destination
  looks like is useful on its own.
- Ties are broken by fewer hops, then by more recent `last_seen_at`.

The result is a `Route`:
- `milestone_key`, `target`, `source_kind` (`state`, `outside` or `from_launch`)
- `hops: list[Hop]`, where each hop holds `from_state`, `actions` and `to_state`
- `confidence = Π p̂` along the path
- `borrowed`, `version_code`

## Hint format

`hints.render(route) -> str` produces an ephemeral block in the Operator prompt:

```
--- App Memory: Known Route (advisory) ---
Milestone: Turn on dark mode
Target screen: "Display" (com.android.settings v34) — adjust brightness, theme and font size.
Seen 6 times. Route confidence 0.71.
From the current screen ("Settings home"):
  1. Tap "Display" (id: display_settings) → expect "Display" [DisplaySettings; "Brightness level", "Dark theme"]
  2. Tap "Dark theme" (switch)            → target reached
Check that each screen matches before taking the next hop. If the screen does not match,
ignore this route and continue normally.
```

- **Signature per hop:** the destination's title, the short activity name, and up to 3 static
  tokens. This is what the agent compares against what it actually sees.
- **Targets** render from the descriptor: text or `content_desc` first, then `resource_id`, then
  `target_description`. Coordinates are never shown, so the agent always grounds the target on
  the live screen.
- **Typed input** renders as `Type the search query into "Search"`, naming the slot, never a
  value.
- **Variants:**
  - `from_launch` adds "Not on a known screen; route from app launch:".
  - `borrowed` adds "Learned on an older app version (vX); screens may differ.".
  - "No path" shows only the Target screen line.
  - "Arrived" shows a single line: "You are on the target screen for this milestone."
- **Length:** at most 8 hop lines. Longer routes show the next 8 and "(+N more)".

## Keeping the route honest

A `RouteTracker` per active milestone runs once per Operator turn, before the prompt is built:

1. **Localize the current screen.**
2. **On hop k of the route** (k ahead of the current pointer): advance the pointer, and render
   only the remaining hops.
3. **On a known state that isn't on the route:** recompute Dijkstra from it (this is cheap) and
   mark the hint "rerouted".
4. **On an unknown screen:** keep the last route with "Current screen not recognised; this route
   may not apply." After **2** consecutive unknown turns, hide the hint until a known screen
   reappears.
5. **On the target:** render "Arrived". Once the milestone is marked done in the plan, the
   tracker is discarded.

## Implementation notes (P5)

- **Modules.** `routing.py` became the package `routing/`. The constants are in
  `constants.py`, as in the abstraction package. `weights.py` computes `p̂` and the cost,
  `paths.py` holds Dijkstra, `planner.py` holds `locate` and `RoutePlanner`, and `tracker.py`
  holds `RouteTracker`.
- **The map is a snapshot.** When a target is found, `GraphStore.map_graph` loads its map once:
  states with their descriptions, edges, and observation counts grouped by source, action,
  edge and status. `route_for` then reads only memory and never waits on the database. States
  harvested later in the same run are not localized until the next run.
- **Localization** returns one of `AtState`, `InOtherApp`, `Unrecognised` or `Arrived`. Each
  carries the state the route starts from, which is the map's `@outside` for the middle two,
  and the route kind it gives.
- **Route.** `Route.kind` is one enum, `from_state`, `from_outside`, `from_launch`, `no_path` or
  `arrived`, in place of `source_kind`. A route also carries the milestone, the map, and the
  state cards the hint needs. `confidence` is computed from the hops.
- **Hop cap.** Dijkstra settles each state once, so a cheapest path longer than 15 hops is
  dropped instead of searching for a costlier path within 15 hops. Ties go to fewer hops, then
  to the path whose oldest edge was seen most recently.
- **Tracker.** The hint hides on the second consecutive unknown turn. "Rerouted" shows only on
  the turn of the reroute. On the first turn, an unknown screen gives the route from launch
  without the "not recognised" note. A screen that is still the route's source keeps the route
  as it is.
- **Hint text.** "Arrived" renders the header, the milestone and the single arrival line. "No
  path" renders the header, the milestone and the target screen line. A route from another app
  leads with "From outside the app:". Borrowed, rerouted and not-recognised lines follow the
  "Seen" line. Actions render from a table keyed by action kind, and a burst joins its actions
  with ", then ". The per-hop signature skips tokens that contain a masking placeholder and
  prefers labels over resource id segments. Harvesting records typed text under the slot
  `text`, so typed input reads `Type the text into "Search"`. "Seen N times" uses the arrival
  count described in [retrieval](retrieval.md).

## Contracts

- `route_for(milestone_key, observation) -> Route | None` is deterministic for a given database
  state.
- The hint never instructs: it says "expect" and "check", never "you must". The Operator prompt
  stays the authority (see [0008](decisions/0008-advisory-hints.md)).
- The rendered hint never contains a value that state abstraction masked.

## Testing

- **Weights:** a hand-built map has known `p̂` values, and Dijkstra picks the reliable long path
  over an unreliable short one.
- **Discounting:** discounted and provisional observations lower `p̂` as specified.
- **Localization:** each row of the table above has a test.
- **Tracker:** advancing, rerouting, hiding after 2 unknown turns, and arrival.
- **Rendering:** golden text for each variant. Coordinates and masked values never appear.
