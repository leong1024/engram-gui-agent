---
feature: app-knowledge
status: draft
depends_on:
  - README.md
  - interface.md
  - summaries.md
  - probe.md
code: []
---

# App knowledge implementation plan

This plan builds the app knowledge feature specified in `docs/specs/app-knowledge/`. It adds one MCP tool, `mobile_get_knowledge`, that tells a calling agent which apps Engram knows, what it has seen in each, and whether it knows a route for a goal.
The program enforces one rule. Every report is derived from the databases at call time, and nothing in this feature writes to either database.
The work ships as three stacked pull requests in this order. K1 adds the knowledge module with the overview and capability reports. K2 adds the probe. K3 adds the MCP tool and the caller guidance.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `skills/poteto-mode/playbooks/autopilot-stack.md` from the installed plugin. The operator lands every PR. Each PR stops at merge-ready, and the operator merges the stack bottom-up. K3 is review-gated.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] On the operator's go, write this exact text into `notes.md` in the program's store under `~/.claude/orchestrate/app-knowledge/` and restate it in your todolist. "Plan `docs/specs/app-knowledge/implementation-plan.md`. PRs in order K1, K2, K3. Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. The operator merges every PR. Done when K3 is merge-ready with a clean verdict and the operator has reviewed K3."
- [ ] Read these from the installed plugin at program start. Re-read them at every tick.
  - [ ] `skills/poteto-mode/playbooks/autopilot-stack.md`
  - [ ] `skills/swarm/SKILL.md`
  - [ ] The built-in `run` skill, which drives the CLI and the MCP server. The repo has no project `verify` skill.
  - [ ] `skills/poteto-mode/playbooks/opening-a-pr.md`
  - [ ] `skills/principle-model-the-domain/SKILL.md`
  - [ ] `skills/principle-boundary-discipline/SKILL.md`
  - [ ] `skills/principle-test-behavior-not-implementation/SKILL.md`
  - [ ] `skills/principle-laziness-protocol/SKILL.md`
- [ ] Arm the hourly audit tick as a real `/loop` in dynamic mode, which schedules its own wake-up rather than blocking on a sleep. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from the installed plugin and the objective in the program store's `notes.md`. Audit the operation against both and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] K1 is first. It branches from `main`.
  - [ ] K2 after K1, stacked on the K1 branch.
  - [ ] K3 after K2, stacked on the K2 branch.
- [ ] Hold the file boundaries.
  - [ ] K1 touches only `artemis/app_memory/knowledge/`, `artemis/app_memory/knowledge_queries.py`, `artemis/app_memory/knowledge_store.py`, `artemis/app_memory/store.py`, `artemis/app_memory/trace_reader.py`, `docs/specs/app-knowledge/`, and `tests/unit/app_memory/`.
  - [ ] K2 touches only `artemis/app_memory/knowledge/`, `docs/specs/app-knowledge/`, and `tests/unit/app_memory/`.
  - [ ] K3 touches only `mcp_server/tools/knowledge.py`, `mcp_server/tools/__init__.py`, `mcp_server/server.py`, `mcp_server/rules.md`, `mcp_server/README.md`, `docs/specs/app-knowledge/`, and `tests/unit/`.
- [ ] Hold the size rules from `CLAUDE.md`. No new module over 200 lines. No new function over 100 lines. An edit inside an existing function over 100 lines adds at most a one-line call into a new helper.
- [ ] Hold the review gate. K3 changes an interaction, the tool list an IDE agent sees. It waits for the operator's review in chat with screenshots and a video before merge.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`; if `command -v origin` succeeds and Origin can resolve the repository, use `origin pr` for every PR operation. Record any fallback to `gh`. Never require `gt`. A cloud session without `gh` uses the GitHub MCP tools.
- [ ] Open the PR ready, never draft, per **Opening a PR**. Use the run's built-in PR tool when it has one, else `origin pr create --status open --base <base-branch>` or `gh pr create --base <base-branch>` according to the resolved forge. A stack child targets its parent branch.
- [ ] Run `make lint` and `make typecheck` once before the PR-facing push. Push with hooks on.
- [ ] Run `/deslop` before each commit and `/no-comments` before review.
- [ ] Triage every review-bot and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Before the code-ready report and babysit, and again after merge prep, record the base and head SHAs prepared by the topology owner under the execution playbook.

### Verdict and merge, for every PR

- [ ] A full swarm runs once, at the code-ready head. Another full swarm runs only for new behavior, a redesign, or a large new diff. A rebase, a merge-conflict resolution, or a minor fix gets a single verifier at the new head, and a wording-only change gets none. Run each full swarm per `skills/swarm/SKILL.md`. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] Judge every finding by the execution playbook's blocking rule. The verdict is clean when none blocks. A failure on trunk behavior in a lane marked `Regression lane against trunk.` is recorded against trunk and does not block the PR. A new head gets a fresh verdict, except for results that stay valid under the patch-id rule in `playbooks/shipping.md`.
- [ ] Hand each clean, merge-ready PR to the operator with its verdict and head SHA. The operator merges the stack bottom-up. A rebased PR whose patch-id is unchanged keeps its verdict under the patch-id rule in `playbooks/shipping.md`.

### Boot recipe, for every live lane

Each live lane runs in its own worktree at the PR head. Drive through the skill path or exact commands recorded in this boot recipe.

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] Run `uv sync --locked`. Point `ARTEMIS_TRACES_DIR` at a traces directory whose `app_memory.db` holds real maps. Build one with device Pro runs and `uv run artemis app-memory backfill --all`, which needs an Android device and `GEMINI_API_KEY`. Lanes that need no real map say so and use `tests/unit/app_memory/fixtures/maps.py` through a lane script.
- [ ] K1 and K2 lanes call the module through a lane script, `uv run python lane.py`, that opens `Knowledge` on the traces directory and prints the report and its rendered text. K3 lanes start `uv run python -m mcp_server` and call `mobile_get_knowledge` through an `mcp` stdio client script. Read state only through `sqlite3 <traces>/app_memory.db`, `uv run artemis app-memory stats`, and the tool itself.
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## Build the knowledge module with summaries (K1)

**Depends on.** None.

**Files.**

- [ ] Create `artemis/app_memory/knowledge/__init__.py`, exporting `Knowledge`, `open_knowledge`, and `render`.
- [ ] Create `artemis/app_memory/knowledge/reports.py`.
- [ ] Create `artemis/app_memory/knowledge/summaries.py`.
- [ ] Create `artemis/app_memory/knowledge/render.py`.
- [ ] Create `artemis/app_memory/knowledge/service.py`.
- [ ] Create `artemis/app_memory/knowledge_queries.py` and `artemis/app_memory/knowledge_store.py`.
- [ ] Edit `artemis/app_memory/store.py` to expose the read-only sub-store as `store.knowledge`.
- [ ] Edit `artemis/app_memory/trace_reader.py` to add a goal lookup for a list of session ids.
- [ ] Create `tests/unit/app_memory/test_knowledge_summaries.py` and `tests/unit/app_memory/test_knowledge_render.py`.

**Build.**

- [ ] Define the reports in `reports.py` as frozen pydantic models per **principle-model-the-domain**. `AppSummary`, `PageSummary`, `Overview`, `Capabilities`, `NotMapped`, `Coverage` as an enum, and the wrapper `KnowledgeResponse` keyed by `level` per `interface.md`.
- [ ] Write the read-only queries in `knowledge_queries.py` and `KnowledgeStore` in `knowledge_store.py`, on the store's existing connection, per `summaries.md`. Counts of pages, confirmed routes and sessions per map, page cards ranked by arrival visits, and completed sessions per map.
- [ ] Add `TraceReader.session_goals(session_ids)`, which returns each session's `initial_goal`. `TraceReader` stays the only reader of `data_engine.db`.
- [ ] Write `overview()` and `capabilities(package)` in `summaries.py` as pure functions over the store reads. Mask example goals with the app-memory masking rules in `artemis/app_memory/abstraction/masking.py`. Name every cap and coverage threshold as a constant at the top of the module.
- [ ] Write `render(report)` in `render.py` with one render function per report type, picked from a table. Cap the text at 3,000 characters at a list-item break.
- [ ] Write `Knowledge` and `open_knowledge(traces_dir)` in `service.py`. It opens `app_memory.db` read-only and returns an empty overview when the file does not exist.

**You see.**

- [ ] A lane script prints an overview that lists `com.android.settings` with its `version_code` and `recommended_profile: pro`, and its rendered text ends with "Use profile `pro`".

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/app_memory/test_knowledge_summaries.py` gains a missing database, an empty store, two packages with two versions each, pages ranked by visits, capability de-duplication, the coverage thresholds, `NotMapped` for an unknown package, and an example goal with an email address that comes back masked. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/app_memory/test_knowledge_render.py` gains one golden text per report type and a case where a long report is cut at a list item under 3,000 characters. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] A test opens the store, takes the database file's checksum, runs every report, and asserts the checksum is unchanged. Run `uv run pytest tests/unit/app_memory -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no knowledge module, so record that. At head, run `uv run artemis app-memory stats` and the overview on the same traces directory. Save `k1-regression.png`. Pass when every app and count in `stats` matches the overview and `stats` output is unchanged from trunk.
- [ ] Lane 2. Run the overview on a real traces directory. Save `k1-overview.png`. Pass when every listed app has a `version_code` and a `recommended_profile`.
- [ ] Lane 3. Run `capabilities("com.android.settings")`. Save `k1-capabilities.png`. Pass when the pages and capabilities match descriptions in `sqlite3 app_memory.db` and none repeats.
- [ ] Lane 4. Run `capabilities` for a package with no map. Save `k1-not-mapped.png`. Pass when the report is `NotMapped` with a reason.
- [ ] Lane 5. Point `ARTEMIS_TRACES_DIR` at an empty directory. Save `k1-empty.png`. Pass when the overview is empty, says to run Pro tasks, and no `app_memory.db` file is created.
- [ ] Lane 6. Read example goals for a package whose sessions include a goal with a phone number. Save `k1-masking.png`. Pass when the number is masked in the report.
- [ ] Lane 7. Rename `data_engine.db` and run `capabilities`. Save `k1-no-trace-db.png`. Pass when `example_goals` is empty and the rest of the report returns.
- [ ] Lane 8. Run the overview while a device Pro run is harvesting into the same database. Save `k1-concurrent.png`. Pass when both finish and neither logs `database is locked`.
- [ ] Lane 9. Compare checksums of `app_memory.db` and `data_engine.db` before and after all reports. Save `k1-read-only.png`. Pass when both checksums are unchanged.
- [ ] Lane 10. Render every report for the largest real map. Save `k1-size.png`. Pass when every text is at most 3,000 characters and ends at a list item.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Trunk has no knowledge module, so measure the diff-added work in absolute terms. The p95 time of `overview()` on a 50-map store, and of `capabilities()` on a 2,000-page map, plus the trunk `make test` wall time.
- [ ] Probe. A lane script builds the stores with `tests/unit/app_memory/fixtures/maps.py` and times 100 calls of each. Run it three times, interleaved with a trunk run of `make test`.
- [ ] Baseline. Record the trunk `make test` wall time first.
- [ ] Rule. Fail when `overview()` p95 exceeds 100 ms, when `capabilities()` p95 exceeds 300 ms, or when head `make test` time exceeds trunk by more than 10 percent.

**Review gate.** None. K1 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands K1 to the operator, who lands it first.

## Add the route probe (K2)

**Depends on.** K1.

**Files.**

- [ ] Create `artemis/app_memory/knowledge/probe.py`.
- [ ] Edit `artemis/app_memory/knowledge/reports.py`, `render.py`, `service.py`, and `__init__.py`.
- [ ] Create `tests/unit/app_memory/test_knowledge_probe.py`.

**Build.**

- [ ] Add `ProbeStatus` as an enum, `ProbeCandidate`, and `ProbeResult` to `reports.py`, and the `probe` level to `KnowledgeResponse`.
- [ ] Write `probe(query, package)` in `probe.py` per `probe.md`. Pick the maps, embed the query once with `open_provider`, run `find_candidates` per map with the default `RetrievalSettings`, keep the top 3 by similarity, and fall back to older versions as `borrowed` only when the newest maps return nothing.
- [ ] Measure `hops_from_launch` for each kept candidate with the existing router, from the map's `@outside` state to the candidate page. Load each map graph once per probe.
- [ ] Map each failure to its `ProbeStatus` per `probe.md`. Cap the embedding call at 10 seconds.
- [ ] Add the probe render function to the table in `render.py`. Its text says it reports similarity, not a promise that a task will succeed.
- [ ] Add `Knowledge.probe` in `service.py`. It makes no LLM call and never touches a device.

**You see.**

- [ ] A lane script probes "turn on dark theme" and prints `status: found` with the Display page of `com.android.settings` and a numeric `hops_from_launch`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/app_memory/test_knowledge_probe.py` gains, with the hash-based fake provider from `tests/unit/app_memory/fixtures/retrieval.py`, a found target with its hop count, no route from launch, a query under the floor, `no_maps`, `no_vectors`, `provider_unavailable`, a package filter, borrowed older versions, and the top-3 cap. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] A test with a selector that raises on any call proves the probe never calls it. Run `uv run pytest tests/unit/app_memory -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no probe, so record that. At head, run a device Pro task "Turn on dark theme" and a probe of the same text. Save `k2-regression.png`. Pass when the probe's top candidate is the target the real run's retrieval chose, read from the run's `app_memory` log line.
- [ ] Lane 2. Probe "turn on dark theme". Save `k2-found.png`. Pass when the status is `found` and the top page is Display.
- [ ] Lane 3. Probe "order a pizza". Save `k2-no-match.png`. Pass when the status is `no_match` with no candidates.
- [ ] Lane 4. Probe with `package` set to Settings. Save `k2-package.png`. Pass when every candidate is in `com.android.settings`.
- [ ] Lane 5. Relabel a map to an older `version_code` with no newer map, then probe. Save `k2-borrowed.png`. Pass when the candidate is `borrowed`.
- [ ] Lane 6. Unset `GEMINI_API_KEY` and probe. Save `k2-no-key.png`. Pass when the status is `provider_unavailable`.
- [ ] Lane 7. Block network access to the embedding host and probe. Save `k2-timeout.png`. Pass when the probe returns `provider_unavailable` within 12 seconds.
- [ ] Lane 8. Probe a page that has no inbound edge from the launch state. Save `k2-no-route.png`. Pass when `hops_from_launch` is null and the status is still `found`.
- [ ] Lane 9. Probe while no device is attached. Save `k2-no-device.png`. Pass when the probe returns and `adb` is never invoked, per the process log.
- [ ] Lane 10. Compare `app_memory.db` checksums before and after 20 probes. Save `k2-read-only.png`. Pass when the checksum is unchanged.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Trunk has no probe, so measure the diff-added work in absolute terms. The end-to-end p95 of one probe with the real provider, and the p95 of the probe with the embedding call excluded, on a store whose largest map has 2,000 pages.
- [ ] Probe. A lane script runs 30 probes with the real provider, and 100 probes with a fixed precomputed vector, against the same store. Run it three times, interleaved with a trunk run of `make test`.
- [ ] Baseline. Record the trunk `make test` wall time first.
- [ ] Rule. Fail when the end-to-end p95 exceeds 1,500 ms, when the p95 without the embedding call exceeds 800 ms, or when head `make test` time exceeds trunk by more than 10 percent.

**Review gate.** None. K2 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands K2 to the operator, who lands it after K1.

## Expose the tool to calling agents (K3)

**Depends on.** K2.

**Files.**

- [ ] Create `mcp_server/tools/knowledge.py`.
- [ ] Edit `mcp_server/tools/__init__.py` or `mcp_server/server.py`, whichever registers the other tools.
- [ ] Edit `mcp_server/rules.md` and `mcp_server/README.md`.
- [ ] Create `tests/unit/test_mcp_knowledge_tool.py`.

**Build.**

- [ ] Write `mobile_get_knowledge(app: str | None = None, query: str | None = None)` in `mcp_server/tools/knowledge.py` as a thin adapter per `interface.md`. It picks the level from the arguments, calls one `Knowledge` method, and returns `Annotated[CallToolResult, KnowledgeResponse]` with the rendered text and the structured report.
- [ ] Treat empty strings as absent. Return an MCP error result with the reason when the database is unreadable.
- [ ] Resolve the traces directory the way `mcp_server/tools/inspect_trace.py` does, so both tools read the same files.
- [ ] Add one line to `mcp_server/rules.md` telling IDE agents to call `mobile_get_knowledge` before `mobile_run_task`, and to probe a goal before running it.
- [ ] Add the tool to the tool list in `mcp_server/README.md`.

**You see.**

- [ ] An MCP client lists six tools, `mobile_get_knowledge` among them with an output schema, and a call with no arguments returns the overview text and the structured report.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/test_mcp_knowledge_tool.py` uses an in-memory MCP client session and gains the tool's output schema, each of the four levels, empty-string arguments, an unreadable database as an error result, and text and structured content that describe the same report. Run `uv run pytest tests/unit/test_mcp_knowledge_tool.py -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. List tools on `python -m mcp_server` at trunk and head. Save `k3-regression.png`. Pass when head lists the five trunk tools unchanged plus `mobile_get_knowledge`.
- [ ] Lane 2. Call the tool with no arguments. Save `k3-overview.png`. Pass when the text names each app with a version and the structured content validates against the output schema.
- [ ] Lane 3. Call it with `app="com.android.settings"`. Save `k3-capabilities.png`. Pass when the text lists pages and capabilities and states that it covers only what Engram has seen.
- [ ] Lane 4. Call it with `query="turn on dark theme"`. Save `k3-probe.png`. Pass when the status is `found` and the text says it reports similarity.
- [ ] Lane 5. Call it with an unknown package. Save `k3-not-mapped.png`. Pass when the level is `not_mapped` and the call is not an error.
- [ ] Lane 6. Lock `app_memory.db` with an exclusive transaction past the timeout, then call the tool. Save `k3-locked.png`. Pass when the result is an MCP error with a reason.
- [ ] Lane 7. In Claude Code with the MCP server installed by `uv run artemis mcp --install claude`, ask "what apps can you control on my phone?". Save `k3-claude-code.png`. Pass when Claude Code calls `mobile_get_knowledge` and answers from it.
- [ ] Lane 8. In the same Claude Code session, ask it to turn on dark theme. Save `k3-guided-run.png`. Pass when it probes first, then calls `mobile_run_task` with profile Pro.
- [ ] Lane 9. Call the tool from an `mcp` SSE client against `uv run artemis mcp --transport sse`. Save `k3-sse.png`. Pass when the result matches the stdio result.
- [ ] Lane 10. Call the tool 50 times in a row. Save `k3-repeat.png`. Pass when every call succeeds and the server's memory stays within 10 percent of its first reading.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The round-trip time of `tools/list` at trunk and head, and the extra time a tool call adds over a direct `Knowledge` call at head.
- [ ] Probe. An `mcp` stdio client lists tools 50 times per side, interleaved trunk then head, then calls each level 50 times at head while a lane script times the same `Knowledge` calls directly.
- [ ] Baseline. Record the trunk `tools/list` median first.
- [ ] Rule. Fail when the head `tools/list` median exceeds trunk by more than 20 ms, or when the tool call adds more than 50 ms at p95 over the direct call.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 7 and lane 8 screenshots into `/tmp/swarm-k3/media/k3-review-ask.png` and `/tmp/swarm-k3/media/k3-review-guided.png`.
- [ ] Record a 30 to 60 second video of Claude Code asking what Engram knows, probing a goal, and running it with profile Pro. Save it as `/tmp/swarm-k3/media/k3-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands K3 to the operator, who lands it last.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

One open question was settled by a run on 2026-11-17, before this plan was written. The question was whether a FastMCP tool in this repo's `mcp` 1.29.0 can return an advertised output schema, structured content, and a custom markdown summary in one response.

- A tool annotated `-> Overview`, a pydantic model, with `structured_output=True` advertises an output schema and returns structured content. Its text content is the same report as indented JSON, not a summary.
- A tool annotated `-> CallToolResult` returns custom text and structured content, but advertises no output schema.
- A tool annotated `-> Annotated[CallToolResult, Overview]` advertises the model's output schema and returns both the custom text and the structured content. K3 uses this form.

The scripts were throwaway files run against an in-memory client session. They are not committed.

Two questions stay unproven.

- Whether calling agents send vague or misplaced goals today. Nobody has read real `mobile_run_task` calls from an IDE agent. K3 lanes 7 and 8 are the first evidence.
- Whether the probe's top candidate matches what a real run picks. K2 lane 1 measures it on one task.

## Appendix B. Alternatives rejected

- **An Obsidian vault for calling agents.** A calling agent cannot open Obsidian, reads files one by one, may not reach the files from another machine, and gets no schema. See decision `0002`.
- **A dump of every state.** Too large to read and says nothing about what to ask. See decision `0001`.
- **A probe that calls the selector LLM and checks installed apps.** Closer to a real run, but costs an LLM call, needs an agent context the MCP server does not have, and needs a device. See decision `0003`.
- **A cached summary file.** Faster reads, but a second copy that can drift from the map. See decision `0004`.
- **One `know(request)` method taking a union of request types.** Every caller and test would build request objects for no gain over three named methods.

## Appendix C. Risks

- **Example goals leak private text.** K1. Goals are typed by users, and masking can miss a short name. The owner masks with the app-memory rules and tests an email and a phone number. The operator decides whether example goals ship on by default.
- **The probe disagrees with real runs.** K2. The probe skips the selector and installed-version checks. The owner keeps the similarity wording, and lane 1 measures agreement on one task.
- **Map graph loads are slow on large maps.** K2. A 2,000-state map took 173 to 217 ms to load in an earlier measurement. Up to three loads per probe fit the 800 ms budget with little margin. The owner loads each map once per probe.
- **Callers ignore the new tool.** K3. The rules line in `mcp_server/rules.md` is the only nudge. Lanes 7 and 8 check that Claude Code uses it.
- **No live lanes in a cloud session.** All PRs. Cloud sessions have no Android device and no maps, so they run unit tests and lint only. The operator runs the live lanes, and the PR body says so.

## Appendix D. Links and reading list

- `docs/specs/app-knowledge/README.md`, then `overview.md`, `interface.md`, `summaries.md`, and `probe.md`.
- `docs/specs/app-memory/data-model.md`, `retrieval.md`, and `routing-and-hints.md` for the tables, the vector search, and the router the probe reuses.
- `mcp_server/tools/inspect_trace.py` for how an MCP tool resolves the traces directory.
- K2 gets `skills/how/SKILL.md` over `artemis/app_memory/retrieval/` before editing. K3 gets `skills/interrogate/SKILL.md` on the tool's wording, because calling agents act on it.
- Keep a decision trail per `skills/show-me-your-work/SKILL.md` in the program store.
