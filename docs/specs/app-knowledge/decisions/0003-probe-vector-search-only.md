---
feature: app-knowledge
status: accepted
date: 2026-11-17
supersedes: null
---

# 0003: The probe runs the vector search only

## Decision

The probe embeds the query once and runs tier-one retrieval. It does not call the selector LLM
and does not check which apps are installed.

## Options considered

- **Vector search only (chosen)**: one embedding call, no LLM call, and no device.
- **Full retrieval with the selector LLM**: matches a real run more closely, but costs an LLM
  call per probe. The MCP server process also has no agent context to build the selector from.
- **Full retrieval plus installed versions from the device**: closest to a real run, but the
  probe would need a device lock and adb.

## Reason

A calling agent may probe several goals before choosing one. The probe must be cheap and must
work with no device attached.

## Consequences

The probe reports similarity, not the selector's confidence, and can differ from what a real run
picks. The text summary says so. Revisit if callers rely on the probe and it disagrees with real
runs often.
