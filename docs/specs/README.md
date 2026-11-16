---
status: living
---

# ARTEMIS feature specs

This folder is an Obsidian vault of design specs, grouped by feature. Each feature is a
self-contained module folder. Start here, open the feature's `README.md`, then read only the
section notes you need.

## Features

| Feature | Status | Summary |
|---|---|---|
| [app-memory](app-memory/README.md) | draft | Cross-run map of app screens and transitions; gives the Pro Operator a known route per milestone. |

Cross-feature changes live in [shared/](shared/):

| Note | Status | Used by |
|---|---|---|
| [step-recording-fields](shared/step-recording-fields.md) | draft | app-memory |

## Layout

```
docs/specs/
  README.md                 this index
  _templates/               copy these to start a new note
  <feature>/
    README.md               feature index: goal, status, reading order, links
    overview.md             brief: problem, scope, non-goals, glossary
    <section>.md            one design area per note
    decisions/NNNN-*.md     one decision per note, numbered within the feature
  shared/                   changes that several features depend on
```

## Conventions

- **One feature, one folder.** A feature never edits another feature's notes. Shared changes go
  in `shared/` and features link to them.
- **Links are relative markdown links**, for example `[retrieval](retrieval.md)` or
  `[recording fields](../shared/step-recording-fields.md)`. Do not use `[[wikilinks]]`. In
  Obsidian, set Settings → Files & links → "Use [[Wikilinks]]" off and "New link format" to
  "Relative path to file".
- **Code references** use repo-relative links, for example
  `[graph.py](../../../artemis/graph/graph.py)`.
- **Frontmatter** on every note:
  - `feature`: the folder name, or `shared`.
  - `status`: `draft`, `approved`, `implemented` or `superseded`.
  - `depends_on`: notes this one relies on, as relative paths.
  - `code`: source paths the note describes or changes.
- **Decisions** record the choice, the options rejected and the reason, so later work does not
  reopen them without new evidence. A changed decision gets a new note that supersedes the old one.

## Adding a feature

1. Create `docs/specs/<feature>/` and copy [feature-index](_templates/feature-index.md) to its
   `README.md`.
2. Add section notes from [spec-section](_templates/spec-section.md) and decisions from
   [decision](_templates/decision.md).
3. Add a row to the Features table above.
