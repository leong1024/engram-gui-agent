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

## Code standards

- No function longer than 100 lines. An edit inside an existing function that is already over
  100 lines adds at most a one-line call into a new helper.
- Keep modules small and single-purpose. Follow single responsibility, don't repeat yourself,
  and keep concerns separate.
- Match the conventions of the surrounding code. Absolute imports only (ruff bans relative
  imports).
- Before pushing, run `make lint` and `make typecheck`, and `uv run pytest tests/unit -q` for
  the areas you touched.

## pstack workflow

pstack (MIT, see `.claude/PSTACK_LICENSE`) is vendored into `.claude/skills/` and
`.claude/agents/` from pstack-claude 0.9.138, so cloud sessions without plugins can use it.

Invoke the `poteto-mode` skill and follow its instructions when a task meets any of these:

- it touches more than one file, or changes a signature other files call
- it involves a design or architecture choice
- it is a bug whose cause is not yet known, or a performance issue

It routes to the right pstack skill from there. For smaller tasks, such as a contained change
to one file with an obvious test, a question, or a one-line edit, work directly and verify on
the real artifact. When the intent is already specific, enter that skill directly: `tdd`,
`architect`, `how`, `why`, `arena`, `interrogate`.

The skills were written for the plugin install. Read them with these substitutions:

- A skill named `pstack:<name>` is the project skill `<name>`, for example `poteto-mode`.
- The subagent type `pstack:poteto-agent` is `poteto-agent`, defined in `.claude/agents/`.
- A path given as `skills/...` "from the installed plugin" is `.claude/skills/...` in this
  repo, for example `node .claude/skills/poteto-mode/scripts/check-plan.mjs <plan.md>`.

On a machine that also has the pstack plugin installed, both copies appear. Prefer the plugin's
`pstack:` names there.

## Current work

The app-memory feature is planned in `docs/specs/app-memory/implementation-plan.md` as six
stacked PRs, P1 to P6. Start each session there. Cloud sessions have no Android device, so they
can run unit tests and lint but not the plan's live device lanes. Leave those boxes unchecked
and say so in the PR.
