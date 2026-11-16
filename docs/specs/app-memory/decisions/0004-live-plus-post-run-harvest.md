---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0004: Write provisional edges live, confirm or discount them after the run

## Decision

Each step writes a provisional observation as it is recorded. When the session ends, its
observations are confirmed (completed runs) or discounted (other outcomes). Sessions that ended
without that pass are reconciled at the next run's `prepare_run`.

## Options considered

- **Post-run only.** Simplest, and pollution is filtered before edges enter the map. Nothing from
  a crashed run is kept.
- **Live only.** The map is always fresh, but edges go in before anyone knows whether the run went
  well.
- **Both (chosen).**

## Reason

The live writes keep evidence from runs that crash, and make it visible to concurrent runs on
other devices. The post-run pass still applies outcome-based confidence before any of it counts
fully.

## Consequences

- Provisional observations route with a weight of 0.5, below confirmed (1.0) and above
  discounted (0.25).
- Reconcile runs in each worker's `prepare_run`, not only at Daemon startup, because standalone
  MCP and in-process SDK runs often have no Daemon.
- Live writes run on the DataEngine's background scheduler. Descriptions and embeddings run in
  background jobs and never block the agent.
