---
feature: app-knowledge
status: accepted
date: 2026-11-17
supersedes: null
---

# 0002: One MCP tool with structured output and a text summary

## Decision

App knowledge is one MCP tool on the IDE-facing server. Each response carries structured content
that matches a report schema, and a short markdown summary of the same report.

## Options considered

- **One MCP tool with structured and text content (chosen)**: one call per question, reaches
  callers on other machines, and gives both code and the model what they need.
- **An Obsidian vault of notes**: good for humans, but a calling agent cannot open Obsidian. It
  would read files one by one through extra tool calls, the files may not be reachable from a
  remote caller, and the notes have no schema.
- **MCP resources only, one per app**: browsable, but there is no way to ask "do you know a route
  for this goal".

## Reason

The consumer is an agent talking over MCP. A tool response always reaches it, and is built from
the database at call time. The in-process action server already returns typed results as
structured content, so this follows an existing pattern.

## Consequences

The markdown renderer can later write the same reports as an Obsidian-style vault for humans.
That vault would be a second output of the same code, never an input to any agent.
