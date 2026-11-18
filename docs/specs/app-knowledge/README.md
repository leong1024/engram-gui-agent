---
feature: app-knowledge
status: draft
depends_on:
  - ../app-memory/README.md
  - ../app-memory/retrieval.md
code:
  - artemis/app_memory/knowledge/
  - mcp_server/tools/knowledge.py
  - mcp_server/rules.md
---

# App knowledge

Agents that call Engram through MCP cannot see what Engram has learned. They send vague goals,
pick the Flash profile for apps that only Pro routes well, and ask about apps that have no map.
Engram then looks worse than it is. App knowledge adds one MCP tool, `mobile_get_knowledge`,
that tells a calling agent which apps Engram knows, what it has seen done in each, and whether it
knows a route for a given goal. Every answer is read from the app-memory database at call time.

## Status

The code for K1 to K3 of the [implementation plan](implementation-plan.md) is merged on `main`
and covered by unit tests. The live device lanes and tuning on real maps are still pending, so
the spec stays a draft. Agreed in conversation on 2026-11-17.

## Reading order

1. [overview](overview.md): problem, goals, scope, non-goals, glossary.
2. [interface](interface.md): the tool's arguments, the three levels, and the response shape.
3. [summaries](summaries.md): how the overview and capability reports are built and ranked.
4. [probe](probe.md): the "can you do X" dry run.
5. [implementation-plan](implementation-plan.md): the PRs and their checks.

## Decisions

| # | Decision |
|---|---|
| [0001](decisions/0001-summarize-not-dump.md) | Return summaries, never a dump of the map. |
| [0002](decisions/0002-mcp-tool-structured-and-text.md) | One MCP tool with structured output and a text summary. Not an Obsidian vault. |
| [0003](decisions/0003-probe-vector-search-only.md) | The probe runs the vector search only, with no selector LLM call. |
| [0004](decisions/0004-derived-read-only.md) | Everything is derived from `app_memory.db` at call time. Nothing is stored. |

## Depends on

- [app-memory](../app-memory/README.md): the map, its descriptions and its vectors.
- [retrieval](../app-memory/retrieval.md): the vector search the probe reuses.

## Open questions

- **Is caller misuse a real failure?** Nobody has read real `mobile_run_task` calls from an IDE
  agent yet. Check that callers send vague or misplaced goals before building beyond the probe.
- **Example goals and privacy.** Goals are text a user typed. They are masked like screen text,
  but a short name can survive masking. Decide whether example goals ship on by default.
- **Coverage labels.** The `sparse`, `partial` and `broad` thresholds are guesses until real
  maps exist.
- **Optional vault.** A human-facing Obsidian export from the same summaries is out of scope
  here. Revisit after the tool ships.
