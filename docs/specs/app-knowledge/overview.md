---
feature: app-knowledge
status: draft
depends_on:
  - README.md
code: []
---

# Overview

## Problem

A calling agent, such as Claude Code or Cursor, drives Engram through the MCP server. It sends
a natural-language goal to `mobile_run_task` and waits. It has no way to learn:

- which apps and app versions Engram has mapped;
- which pages of an app Engram has seen, and what can be done on them;
- which goal wordings routed well in past runs;
- that only the Pro profile uses app-memory routes.

So it guesses. A vague goal misses the map, a Flash run ignores it, and a goal for an unmapped
app explores from scratch. Engram's memory is there, but the caller never benefits from it.

## Goal

Give the calling agent one cheap call that answers "what do you know?" before it spends a task.

## Scope

- One MCP tool, `mobile_get_knowledge`, on the IDE-facing server in `mcp_server/`.
- Three levels: an overview of mapped apps, a capability report for one app, and a probe that
  checks whether a goal has a known route.
- One module, `artemis/app_memory/knowledge/`, that builds the reports from `app_memory.db`.
- One line in `mcp_server/rules.md` telling IDE agents to call the tool before `mobile_run_task`.

## Non-goals

- No change to how Engram navigates. The tool reads the map and never writes it.
- No dump of every state or edge. See [0001](decisions/0001-summarize-not-dump.md).
- No Obsidian vault for agents. See [0002](decisions/0002-mcp-tool-structured-and-text.md).
- No device actions. The probe never touches the phone.
- No claim about what an app can do in general. Reports cover only what Engram has seen.

## Glossary

- **Calling agent**: the agent that uses Engram as a tool through MCP.
- **Map**: one app version in `app_memory.db`, keyed by package and `version_code`.
- **Page**: a described state that is not virtual. "Page" is the word the tool uses with
  callers. Inside `artemis/app_memory/` the word stays "state".
- **Capability**: an affordance from a page's description, such as "turn on dark theme".
- **Example goal**: the goal of a past session that touched a map and finished `completed`.
- **Coverage**: a coarse label for how much of an app Engram has seen.
- **Probe**: a dry run of target retrieval for one goal, with no device and no task.
