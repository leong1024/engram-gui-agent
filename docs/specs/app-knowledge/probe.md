---
feature: app-knowledge
status: draft
depends_on:
  - interface.md
  - decisions/0003-probe-vector-search-only.md
  - ../app-memory/retrieval.md
  - ../app-memory/routing-and-hints.md
code:
  - artemis/app_memory/knowledge/
  - artemis/app_memory/retrieval/candidates.py
  - artemis/app_memory/routing/
---

# Probe

The probe answers "does Engram know a route for this goal?" without a device and without a
task. It reuses the first tier of app-memory retrieval and the router.

## Behaviour

1. **Pick maps.** With `package`, use that package's newest map, then up to two older versions as
   borrowed fallbacks. Without `package`, use the newest map of every package. The probe does not
   check which apps are installed, because it never touches a device.
2. **Embed the query.** One call to the configured embedding provider, the same provider and
   model the maps were embedded with.
3. **Search each map.** Run the existing tier-one search, `find_candidates`, with the existing
   `RetrievalSettings`: top 20 per map and the 0.35 similarity floor. A map under the floor
   contributes nothing.
4. **Rank across maps.** Sort candidates by similarity and keep the top 3. Older versions are
   searched only when the newest versions return nothing, and their candidates are marked
   `borrowed`.
5. **Measure the route.** For each kept candidate, load its map graph and plan a route from the
   app's `@outside` state, which stands for the app launch, to the candidate page. Report the
   hop count, or null when no route exists.
6. **Set the status.** `found` with at least one candidate. Otherwise the most specific reason:
   `no_maps`, `no_vectors`, `provider_unavailable` or `no_match`.

## Contracts

- The probe makes one embedding call and no LLM call.
- The probe never writes to the database and never touches the device.
- `similarity` is the cosine similarity from the vector search. It is not the selector's
  confidence that a real run uses, and the text summary says so.
- A probe result can differ from what a real run picks. A real run also checks installed
  versions and asks the selector LLM to choose.

## Failure handling

- **No embedding key**: status `provider_unavailable`, with no candidates.
- **No vector table for the current model**: status `no_vectors`.
- **Embedding call fails or times out after 10 seconds**: status `provider_unavailable`.
- **A map graph fails to load**: that candidate keeps `hops_from_launch` null.

## Implementation notes (K2)

K2 follows the code where this note was silent or did not match it. Each item keeps the intent
of the sections above.

- **`probe` is async.** `Knowledge.probe(query, package=None)` is a coroutine, because the
  embedding call is async and the MCP tools in `mcp_server/tools/` are async. A tool awaits it
  on the thread that opened `Knowledge`. A lane script runs it with `asyncio.run`.
- **Empty query.** A query that is empty after whitespace is stripped returns the extra status
  `empty_query`, with no candidates. It reads nothing and makes no embedding call. An empty
  `package` is treated as absent, as [interface](interface.md) says for the tool's arguments.
- **Status order.** `empty_query`, then `no_maps`, then `no_vectors`, then
  `provider_unavailable`, then `no_match`. `no_vectors` is checked before the embedding call,
  so a store with no vectors costs no network call.
- **Current embedding model.** The probe uses K1's lookup: the configured `provider`, `model`
  and `dimensions` select the newest matching row of `embedding_models`, with no provider call.
  See [summaries](summaries.md#implementation-notes-k1). When the query vector's size differs
  from that row's `dim`, the status is `no_vectors`, because no stored vector can be compared.
- **The provider.** `Knowledge` takes an `embedder`, a function that returns the
  `EmbeddingProvider`. By default it calls `open_provider` on the configured embedding, and only
  when a probe reaches the embedding step. A missing key raises there and reads as
  `provider_unavailable`, like any other failure or the 10-second timeout.
- **The floor applies to every candidate.** `find_candidates` drops a map whose best hit is
  under 0.35 but keeps that map's lower hits. The probe also drops each candidate under 0.35,
  so the top 3 never show a page far from the goal.
- **No package, no borrowing.** Without `package`, only the newest map of each package is
  searched, as step 1 says. Older versions are borrowed only with `package`.
- **Ties.** Candidates with equal similarity sort by package, then newest version, then page
  title.
- **Hops.** The probe builds one `RoutingMap` per kept map and asks its path finder for the
  cheapest path from `@outside` to the page, within the router's `MAX_HOPS`. This is the path
  `RoutePlanner` plans from outside the app. A `sqlite3.Error` while loading a map keeps that
  map's candidates at null hops.
- **Report rule.** `ProbeResult` holds candidates only when its status is `found`, and a
  `found` result holds at least one. The validator rejects any other shape.
- **`__init__.py` is unchanged.** It already exports `Knowledge`, `open_knowledge` and
  `render`, which is all a caller needs.
