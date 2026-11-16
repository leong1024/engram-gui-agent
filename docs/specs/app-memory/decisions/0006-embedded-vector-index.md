---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0006: Vectors in SQLite with sqlite-vec, no server

## Decision

Vectors are stored in `app_memory.db` as sqlite-vec `vec0` tables, alongside the graph tables.
There is no separate vector database service.

## Options considered

- **sqlite-vec in the same file (chosen).** One file, transactional together with the graph,
  and the same storage pattern as `data_engine.db`.
- **An embedded library** such as Chroma or LanceDB. Capable, but a second storage system with
  its own files and lifecycle.
- **A vector database server.** Unnecessary at this scale: a map holds thousands of vectors, not
  millions.

## Reason

At thousands of vectors per map, a k-nearest-neighbour search over an embedded index takes
milliseconds. Keeping graph and vectors in one SQLite file avoids keeping two stores in sync.

## Consequences

- `vec0` columns have a fixed dimension, so there is one table per embedding model.
- If sqlite-vec wheels are unavailable on a platform ARTEMIS supports, `store.py` falls back to
  brute-force cosine similarity in numpy over vectors stored as BLOBs. Same interface, no other
  change.
