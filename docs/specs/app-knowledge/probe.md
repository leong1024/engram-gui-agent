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
