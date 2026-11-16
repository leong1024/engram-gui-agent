---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0010: Dijkstra through rustworkx

## Decision

[routing](../routing-and-hints.md) finds the cheapest route with `rustworkx.dijkstra_shortest_paths`
instead of a hand-written search. The graph is built once per route planner and reused for every
query.

## Options considered

- **rustworkx (chosen).** A tested shortest-path implementation in Rust. It takes a per-edge
  weight function.
- **networkx.** Also takes a weight function, but it is pure Python and would add a dependency
  for no speed gain.
- **A hand-written Dijkstra on `heapq`.** It worked and was 29 lines, but it was our own
  algorithm to maintain.

## Reason

Both the hop cap and the tie-break order are not built into any of these libraries, so they stay
in our code in either case. The library removes the search itself.

## Consequences

- The hop cap of 15 is a check on the returned path. A cheaper path over 15 hops now gives
  "no path", where the hand-written version searched on for one within the cap.
- Tie-breaks are tiny additions to each edge's cost: one per hop, and one scaled by how long ago
  the edge was last seen, normalized over the map. Both are far smaller than any difference the
  cost function produces. The old rule compared the single stalest edge on a path. The new one
  sums over the path.
- Parallel edges between the same two states collapse to the cheapest one.
- A rough run on a random 2,000-state map with 4 edges each gave a query median of 0.5 ms,
  against 2.1 ms for the hand-written search. Building the graph once costs about 7 ms. This is
  one run, not a full benchmark, and not a real map.
