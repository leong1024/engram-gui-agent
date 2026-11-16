---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0001: One map per app version

## Decision

Each `(package, version_code)` is its own map in phase 1. Every state and edge row carries both
columns, so maps can be merged later by changing the query filter, with no migration.

## Options considered

- **One map per version (chosen).** Clean separation, and screens from different builds never mix.
  An app update starts with an empty map for the new version.
- **One map per app, rows tagged with the versions they were seen in.** Learning carries across
  updates, but deciding which old evidence still holds is a harder design problem.

## Reason

Separating first is simpler and keeps the merge cheap, because the version columns are there
from day one. The cold start after an update is softened by borrowing routes from older versions
(tier 2 fallback in [retrieval](../retrieval.md)).

## Consequences

- Retrieval searches the installed version's map first and older versions only as a fallback,
  marking those routes `borrowed`.
- Revisit when fresh-update cold starts visibly hurt. The next step is a per-app map with
  version-tagged rows.
