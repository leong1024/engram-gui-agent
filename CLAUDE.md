# CLAUDE.md

## Design specs

Feature design specs live in `docs/specs/`, an Obsidian vault grouped by feature.

- Before working on a feature, read `docs/specs/README.md`, then that feature's
  `docs/specs/<feature>/README.md`, then only the section notes you need.
- Decisions in `docs/specs/<feature>/decisions/` are settled. Do not reopen one without new
  evidence. A changed decision gets a new note that supersedes the old one.
- New features get their own folder, built from `docs/specs/_templates/`. Changes that several
  features depend on go in `docs/specs/shared/`.
- Use relative markdown links, not `[[wikilinks]]`, and keep each note's frontmatter (`feature`,
  `status`, `depends_on`, `code`) accurate.
