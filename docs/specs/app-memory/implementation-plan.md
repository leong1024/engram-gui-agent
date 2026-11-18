---
feature: app-memory
status: draft
depends_on:
  - README.md
  - ../shared/step-recording-fields.md
code: []
---

# App memory implementation plan

This plan builds the app memory feature specified in `docs/specs/app-memory/` of `leong1024/engram-gui-agent`.
App memory gives the Pro Operator a route, learned in earlier runs, to each plan milestone's target screen.
The program enforces one rule. No function in new code exceeds 100 lines, and the quality check fails the build if one does.
The work ships as six stacked pull requests in this order. P1 adds the step recording fields. P2 adds the core store and the state abstraction.
P3 adds harvesting, the run lifecycle hooks, and the CLI. P4 adds descriptions and embeddings. P5 adds retrieval, routing, and hint text. P6 wires everything into the Pro graph.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `skills/poteto-mode/playbooks/autopilot-stack.md` from the installed plugin. The operator lands every PR. Each PR stops at merge-ready, and the operator merges the stack bottom-up. P3 and P6 are review-gated.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] On the operator's go, write this exact text into `notes.md` in the program's store under `~/.claude/orchestrate/app-memory/` and restate it in your todolist. "Plan `docs/specs/app-memory/implementation-plan.md`. PRs in order P1, P2, P3, P4, P5, P6. Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. The operator merges every PR. Done when P6 is merge-ready with a clean verdict and the operator has reviewed P3 and P6."
- [ ] Read these from the installed plugin at program start. Re-read them at every tick.
  - [ ] `skills/poteto-mode/playbooks/autopilot-stack.md`
  - [ ] `skills/swarm/SKILL.md`
  - [ ] The built-in `run` skill, which drives the CLI. The repo has no project `verify` skill.
  - [ ] `skills/poteto-mode/playbooks/opening-a-pr.md`
  - [ ] `skills/principle-model-the-domain/SKILL.md`
  - [ ] `skills/principle-boundary-discipline/SKILL.md`
  - [ ] `skills/principle-make-operations-idempotent/SKILL.md`
  - [ ] `skills/principle-test-behavior-not-implementation/SKILL.md`
  - [ ] `skills/architect/SKILL.md`
- [ ] Arm the hourly audit tick as a real `/loop` in dynamic mode, which schedules its own wake-up rather than blocking on a sleep. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from the installed plugin and the objective in the program store's `notes.md`. Audit the operation against both and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] P1 and P2 are independent and first. Both branch from `docs/app-memory-spec`, or from `main` once the spec PR merges.
  - [ ] P3 after P1 and P2 both merge, because P3 builds on both.
  - [ ] P4 after P3, stacked on the P3 branch.
  - [ ] P5 after P4, stacked on the P4 branch.
  - [ ] P6 after P5, stacked on the P5 branch.
- [ ] Hold the file boundaries.
  - [ ] P1 touches only `artemis/clients/`, `artemis/drivers/base.py`, `artemis/controllers/device_controller.py`, `third_party/mobile_use/clients/ui_automator_client.py`, `third_party/mobile_use/controllers/unified_controller.py`, `artemis/runtime/app_versions.py`, `artemis/data_engine/engine.py`, `artemis/graph/graph.py`, `artemis/agents/flash/runner.py`, `docs/specs/`, and `tests/unit/`.
  - [ ] P2 touches only `artemis/app_memory/{models,store,abstraction}.py`, `scripts/quality_ratchet.py`, `.quality-baseline.json`, `pyright-core.json`, `pyproject.toml`, `uv.lock`, and `tests/unit/app_memory/`.
  - [ ] P3 through P6 touch only the files their **Files** block names.
- [ ] Hold the function size rule. A new function stays at or under 100 lines. An edit inside an existing function over 100 lines adds at most a one-line call into a new helper.
- [ ] Hold the review gate. P3 and P6 change an interaction. They wait for the operator's review in chat with screenshots and a video before merge.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`; if `command -v origin` succeeds and Origin can resolve the repository, use `origin pr` for every PR operation. Record any fallback to `gh`. Never require `gt`. `gh` is not installed on the operator's machine today, so install it and run `gh auth login`, or hand the operator a compare URL and a PR body file for each PR.
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
- [ ] Run `uv sync --locked`. Device lanes also need `adb devices` to list one device in the `device` state and a `.env` with `GEMINI_API_KEY`. Offline lanes set `ARTEMIS_MOCK_DRIVER=1` and `ARTEMIS_FAKE_LLM=1` and need neither.
- [ ] Start runs with `uv run artemis run "<goal>" --profile <flash|pro> --standalone` through the `run` skill. Read state only through `sqlite3 <traces>/data_engine.db`, `sqlite3 <traces>/app_memory.db`, `uv run artemis app-memory stats`, and the `mobile_inspect_trace` MCP tool.
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## Record the screen identity on every step (P1)

**Depends on.** None.

**Files.**

- [ ] Edit `artemis/clients/accessibility_client.py`.
- [ ] Edit `artemis/clients/screen_client_factory.py`.
- [ ] Edit `third_party/mobile_use/clients/ui_automator_client.py`.
- [ ] Edit `artemis/drivers/base.py`.
- [ ] Edit `artemis/controllers/device_controller.py`.
- [ ] Edit `third_party/mobile_use/controllers/unified_controller.py`.
- [ ] Create `artemis/runtime/app_versions.py`.
- [ ] Edit `artemis/data_engine/engine.py`.
- [ ] Edit `artemis/graph/graph.py`.
- [ ] Edit `artemis/agents/flash/runner.py`.
- [ ] Edit `docs/specs/shared/step-recording-fields.md`, `docs/specs/app-memory/harvesting.md`, and `docs/specs/app-memory/integration-pro.md`.
- [ ] Create `tests/unit/runtime/test_app_versions.py` and `tests/unit/clients/test_accessibility_activity.py`.

**Build.**

- [ ] Add an optional `activity` field to `UIAutomatorScreenData`, `ScreenData`, and `ScreenDataResponse`. Read it from the helper snapshot in `AccessibilityClient.get_screen_data`. Pass it through `FallbackScreenClient` unchanged.
- [ ] Fill `activity` on the UIAutomator backend from `parse_foreground_task` in `artemis/utils/app_launch_utils.py`, with a 1 second cap.
- [ ] Create `AppVersionCache` in `artemis/runtime/app_versions.py`. It loads `pm list packages --show-versioncode` once per run, reads `versionName` with `dumpsys package <pkg>` on first use of a package, and invalidates a package after an adb command that contains `install` or `uninstall`.
- [ ] Add `activity`, `version_code`, `version_name`, and `ui_backend` to `extra_metadata` in a new `DataEngine._stamp_screen_identity` helper. `record_step` calls it in one line. Missing values are `None`.
- [ ] Stop Flash passing the post-action text as `ui_tree` at `artemis/agents/flash/runner.py:737`. Pass the structured pre-action list instead.
- [ ] Correct the spec notes with three facts found while planning.
  - [ ] Flash pre-action image rows already hold the structured tree, because `observe` saves it first and `get_or_create_image` keeps the first tree. Old Flash traces can be backfilled.
  - [ ] `async with context` exits before `_finalize_tracing_safely`, so the DataEngine is already shut down there. Finalize the app memory session from the DataEngine `session_ended` event, and flush app memory in `ArtemisContext.__aexit__` before the DataEngine shuts down.
  - [ ] `DataEngine.subscribe` already delivers `step_recorded` events. Reuse it rather than add a new listener hook. Live harvesting is best-effort, and the post-run pass sweeps the whole session idempotently.

**You see.**

- [ ] A Flash step row on a device run has `extra_metadata` with `"activity": "com.android.settings.Settings"`, a numeric `version_code`, and `"ui_backend": "helper"`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/runtime/test_app_versions.py` gains cases for one `pm list` call per run and invalidation after `install`. Run `uv run pytest tests/unit/runtime -q`.
- [ ] `tests/unit/clients/test_accessibility_activity.py` parses `activity` from a recorded snapshot fixture. Run `uv run pytest tests/unit/clients -q`.
- [ ] `tests/unit/data_engine/test_engine.py` gains a case where a recorded step carries the four new keys and `None` for unknown values. Run `uv run pytest tests/unit/data_engine -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run the offline Pro run "Open Settings" at trunk and head. Save `p1-regression.png`. Pass when both runs exit 0 and only the head step rows carry the four new keys.
- [ ] Lane 2. On a device, run Flash "Open Settings and open Battery". Save `p1-flash-activity.png`. Pass when every step has a non-null `activity` and a `version_code` equal to `dumpsys package com.android.settings`.
- [ ] Lane 3. On a device, run the same task with `--profile pro`. Save `p1-pro-activity.png`. Pass when every step has the same fields as lane 2.
- [ ] Lane 4. Set `ARTEMIS_HIERARCHY_BACKEND=uiautomator` and repeat lane 2. Save `p1-uiautomator.png`. Pass when `activity` is non-null and `ui_backend` is `uiautomator`.
- [ ] Lane 5. Run Flash "Open Settings, then open Chrome". Save `p1-cross-app.png`. Pass when `version_code` changes on the first Chrome step and matches `dumpsys package com.android.chrome`.
- [ ] Lane 6. Run Pro with a goal that reinstalls an APK through `run_adb_command`. Save `p1-reinstall.png`. Pass when the log shows the cache entry invalidated and the next step reads the new `version_code`.
- [ ] Lane 7. After lane 2, read the `images` row of each Flash step's `pre_image_name`. Save `p1-flash-tree.png`. Pass when every `ui_tree` is a JSON list of element dicts and none is the text rendering.
- [ ] Lane 8. During a Flash run, run `adb shell am force-stop com.artemis.helper`. Save `p1-helper-fallback.png`. Pass when the run continues and later steps record `ui_backend` as `uiautomator`.
- [ ] Lane 9. Open a trunk-recorded session at head with `mobile_inspect_trace view_summary` and `artemis trace list`. Save `p1-old-traces.png`. Pass when both show the session with no error.
- [ ] Lane 10. Call `mobile_inspect_trace view_step_details` on a head session. Save `p1-inspect.png`. Pass when the step details show the new keys.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Time from `session_started` to the first `step_recorded` event, and the wall time of `record_step`, on the same device task at trunk and head.
- [ ] Probe. Run Flash "Open Settings" five times per side, interleaved trunk then head, and read both times from the DataEngine trace timestamps.
- [ ] Baseline. Record the trunk median of both times first.
- [ ] Rule. Fail when the head median startup exceeds trunk by more than 300 ms, or when the head median `record_step` exceeds trunk by more than 5 ms.

**Review gate.** None. P1 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands P1 to the operator, who lands it first.

## Build the map store and the state abstraction (P2)

**Depends on.** None.

**Files.**

- [ ] Create `artemis/app_memory/__init__.py`.
- [ ] Create `artemis/app_memory/models.py`.
- [ ] Create `artemis/app_memory/store.py`.
- [ ] Create `artemis/app_memory/abstraction.py`.
- [ ] Edit `scripts/quality_ratchet.py` and `.quality-baseline.json`.
- [ ] Edit `pyright-core.json`.
- [ ] Edit `pyproject.toml` and `uv.lock` to add `sqlite-vec`.
- [ ] Create `tests/unit/app_memory/` with fixtures of real element lists.

**Build.**

- [ ] Define the domain types in `models.py` per **principle-model-the-domain**. `MapId`, `StateId`, `ScreenObservation`, `AbstractScreen`, `TargetDescriptor`, `CanonicalAction`, and `ObservationStatus` as an enum.
- [ ] Write `store.py`, the only module that opens `app_memory.db`. It creates the tables in `docs/specs/app-memory/data-model.md`, opens the file in WAL mode, loads sqlite-vec, and rebuilds edge counts from `observations`. Vector tables use a `vec0` partition key per map.
- [ ] Write `abstraction.py` as pure functions. `abstract(observation)` returns an `AbstractScreen`. `match(screen, candidates)` returns a `StateId` or `None`. Each masking rule is one small function in an ordered table.
- [ ] Add two metrics to `scripts/quality_ratchet.py`. `long_functions` counts functions over 100 lines everywhere, with a baseline of 111. `app_memory_long_functions` counts them under `artemis/app_memory`, with a baseline of 0.
- [ ] Add the new modules to `pyright-core.json`.

**You see.**

- [ ] `uv run python scripts/quality_ratchet.py` prints `long_functions` 111 and `app_memory_long_functions` 0, and exits 0.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/app_memory/test_abstraction.py` gains the golden cases from `state-abstraction.md`. Scroll positions, feed items, a dialog, tabs, the keyboard, and backend parity. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/app_memory/test_masking.py` gains a property test that no number, email address, or text field content survives masking. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/app_memory/test_store.py` gains schema re-creation, the count rebuild, and two writer processes. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/test_quality_ratchet.py` gains a case where a 101-line function under `artemis/app_memory` fails the check. Run `uv run pytest tests/unit/test_quality_ratchet.py -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no `artemis/app_memory`, so record that. Run `make test` and `make lint` at trunk and head. Save `p2-regression.png`. Pass when head passes the same tests trunk passes, plus the new ones, and `make lint` exits 0.
- [ ] Lane 2. Capture the Settings home hierarchy twice at two scroll positions with `mobile_get_device_state hierarchy` and feed both to `abstract` in a lane script. Save `p2-scroll.png`. Pass when both give the same `coarse_key`.
- [ ] Lane 3. Capture the YouTube home feed twice, five minutes apart. Save `p2-feed.png`. Pass when `match` returns the first state for the second capture.
- [ ] Lane 4. Capture a Settings page alone and with a dialog open. Save `p2-dialog.png`. Pass when the two captures give different states.
- [ ] Lane 5. Capture the Clock app on the Alarm tab and on the Timer tab. Save `p2-tabs.png`. Pass when the two captures give different states.
- [ ] Lane 6. Capture a search screen with the keyboard open and closed. Save `p2-keyboard.png`. Pass when both captures give the same state.
- [ ] Lane 7. Capture one screen with the helper and with UIAutomator through `uv run artemis helper parity`. Save `p2-parity.png`. Pass when both give the same `coarse_key`.
- [ ] Lane 8. Capture the Messages conversation list. Save `p2-masking.png`. Pass when `static_tokens` contain no visible name, number, or message text.
- [ ] Lane 9. Run two lane-script processes that each insert 500 observations into one `app_memory.db`. Save `p2-concurrency.png`. Pass when the cached counts equal a fresh rebuild and no write is lost.
- [ ] Lane 10. Capture a Flutter or game screen twice. Save `p2-opaque.png`. Pass when the state is marked opaque and the second capture matches by `dhash`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Trunk has no abstraction, so measure the diff-added work in absolute terms. The p95 time of `abstract` per screen, and the p95 time of `match` against a 2,000-state map.
- [ ] Probe. A lane script times 200 calls of each over the fixtures and the captures from the live lanes. Run it three times, interleaved with a trunk run of `make test` that confirms trunk test time is unchanged.
- [ ] Baseline. Record the trunk `make test` wall time first.
- [ ] Rule. Fail when `abstract` p95 exceeds 5 ms, when `match` p95 exceeds 20 ms, or when head `make test` time exceeds trunk by more than 10 percent.

**Review gate.** None. P2 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands P2 to the operator, who lands it after P1.

## Harvest steps into the map (P3)

**Depends on.** P1 and P2.

**Files.**

- [ ] Create `artemis/app_memory/harvester.py`.
- [ ] Create `artemis/app_memory/service.py`.
- [ ] Edit `artemis/app_memory/__init__.py`.
- [ ] Edit `artemis/context.py`.
- [ ] Edit `artemis/sdk/agent.py`.
- [ ] Edit `artemis/config/agent.py` and `config/artemis.jsonc`.
- [ ] Create `artemis/interfaces/cli/commands/app_memory.py`.
- [ ] Edit `artemis/interfaces/cli/main.py`.
- [ ] Create `tests/unit/app_memory/test_harvester.py`, `tests/unit/app_memory/test_service.py`, and `tests/unit/test_cli_app_memory.py`.

**Build.**

- [ ] Write `harvester.py` with three entry points per `docs/specs/app-memory/harvesting.md`. `on_step_recorded` writes provisional observations best-effort. `finalize_session` confirms or discounts a whole session and sweeps any step the live path missed. `reconcile` finalizes stale `live` sessions. Each entry point is idempotent per `(session_id, step_id)`.
- [ ] Write `AppMemory` in `service.py` with the profile-neutral interface from `integration-pro.md`, plus a `NoopAppMemory` for the disabled case. One `guarded` decorator logs and swallows errors at the service boundary, so harvesting adds one broad exception handler, not one per call site.
- [ ] Wire the lifecycle in `artemis/sdk/agent.py` and `artemis/context.py` through new helpers, with one-line calls inside existing long functions.
  - [ ] Open the service after `start_session` and call `prepare_run` after the device lock.
  - [ ] Subscribe to `step_recorded` and `session_ended` with `DataEngine.subscribe`.
  - [ ] Await `app_memory.close()` in `ArtemisContext.__aexit__` before the DataEngine shuts down.
- [ ] Add `AppMemoryConfig` with `enabled` and `harvest` to `AgentGlobalConfig`, and the matching block to `config/artemis.jsonc`.
- [ ] Add the `artemis app-memory` Typer sub-app with `backfill` and `stats`, following `artemis/interfaces/cli/commands/trace.py`.

**You see.**

- [ ] After a device run, `uv run artemis app-memory stats` prints a row for `com.android.settings` with non-zero states, edges, and confirmed observations.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/app_memory/test_harvester.py` gains the scripted five-step session, merged waits, a burst as one macro edge, a no-effect step, the cross-app edge split, the outcome mapping, reconcile, and a double backfill that leaves the database identical. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/app_memory/test_service.py` gains a case where every harvester call raises and the task result is unchanged. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/test_cli_app_memory.py` invokes `app-memory --help`, `stats`, and `backfill --session` through `CliRunner`. Run `uv run pytest tests/unit/test_cli_app_memory.py -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run Flash "Open Settings and open Battery" on a device at trunk and head. Save `p3-regression.png`. Pass when both runs reach the same outcome and only head creates `app_memory.db` with Settings states and edges.
- [ ] Lane 2. Run Pro on the same task and query `observations` mid-run and after exit. Save `p3-provisional.png`. Pass when rows are `provisional` mid-run and `confirmed` after exit.
- [ ] Lane 3. Run Pro with a goal that cannot succeed, such as opening a setting the device lacks. Save `p3-discounted.png`. Pass when that session's observations are `discounted`.
- [ ] Lane 4. Kill the worker process mid-run, then start a new run. Save `p3-reconcile.png`. Pass when the killed session is `finalized` with outcome `failed` before the new run's first step.
- [ ] Lane 5. Run `uv run artemis app-memory backfill --all` twice over the sessions from lanes 1 to 4. Save `p3-backfill.png`. Pass when `sqlite3 app_memory.db .dump` is identical after each run.
- [ ] Lane 6. Run `uv run artemis app-memory stats`. Save `p3-stats.png`. Pass when every printed count equals the matching SQL count.
- [ ] Lane 7. Run Flash "Open Settings, then open Chrome with manage_app". Save `p3-cross-app.png`. Pass when the map has an edge to Settings `@outside` and an edge from Chrome `@outside`.
- [ ] Lane 8. Set `agent.app_memory.harvest.enabled` to false and repeat lane 1. Save `p3-harvest-off.png`. Pass when no row is written and the run matches trunk.
- [ ] Lane 9. Set `agent.app_memory.enabled` to false and repeat lane 1. Save `p3-disabled.png`. Pass when `app_memory.db` is not created.
- [ ] Lane 10. Run `backfill --all` while a device run is in progress. Save `p3-concurrent.png`. Pass when neither process logs a `database is locked` error and both finish.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The median wall time per agent step on the same device task at trunk and head. Also the absolute time of `finalize_session` for a 100-step session.
- [ ] Probe. Run Flash "Open Settings and open Battery" five times per side, interleaved, and read step times from DataEngine step timestamps. Time `finalize_session` with a lane script over a recorded 100-step session.
- [ ] Baseline. Record the trunk median step time first.
- [ ] Rule. Fail when the head median step time exceeds trunk by more than 5 percent, or when `finalize_session` exceeds 2 seconds.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 5 and lane 6 screenshots into `/tmp/swarm-p3/media/p3-review-cli.png` and `/tmp/swarm-p3/media/p3-review-stats.png`.
- [ ] Record a 30 to 60 second video of a device run followed by `artemis app-memory stats` in a lane worktree. Save it as `/tmp/swarm-p3/media/p3-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands P3 to the operator, who lands it after P1 and P2.

## Describe and embed states and edges (P4)

**Depends on.** P3.

**Files.**

- [ ] Create `artemis/app_memory/describer.py`.
- [ ] Create `artemis/app_memory/embeddings.py`.
- [ ] Edit `artemis/app_memory/store.py`, `artemis/app_memory/harvester.py`, and `artemis/app_memory/service.py`.
- [ ] Edit `artemis/config/llm.py`, `artemis/config/constants.py`, `artemis/config/agent.py`, and `config/artemis.jsonc`.
- [ ] Create `tests/unit/app_memory/test_describer.py` and `tests/unit/app_memory/test_embeddings.py`, and edit `tests/unit/test_llm_config.py`.

**Build.**

- [ ] Write the describer as a `StepLens` subclass run by its own `StepMemoryService` instance with a concurrency of 2. Override `_on_ready` to persist the description and queue the embedding. The prompt forbids naming content seen in the screenshot.
- [ ] Write `EmbeddingProvider` over LangChain `Embeddings`, with `gemini`, `openai`, and `ollama` factories in one registry table.
- [ ] Add `app_memory_describer` and `app_memory_selector` as LLM nodes. Add each to `LLMConfig`, the `AgentNode` literal, and the defaults in `get_agent`.
- [ ] Fix `_expand_default_into_nodes` in `artemis/config/llm.py` so that a `nodes` override applies to every optional node. Today a `nodes.planner_validation` override is dropped without a warning.
- [ ] Add the `embedding` block to `AppMemoryConfig` and `config/artemis.jsonc`, with the current Gemini embedding model written explicitly.

**You see.**

- [ ] A minute after a device run, every Settings state in `app_memory.db` has `description_status` `ready`, and the `vec_` table holds one row per ready state and edge.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/app_memory/test_describer.py` gains persistence of a fake describer result, retry to `failed`, and re-queue of `pending` rows. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/app_memory/test_embeddings.py` gains the provider registry, one table per model, and re-embedding when `text_hash` changes. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/test_llm_config.py` gains a case where a `nodes.planner_validation` override changes the resolved model. Run `uv run pytest tests/unit/test_llm_config.py -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no describer, so record that. Run Flash "Open Settings and open Display" at trunk and head. Save `p4-regression.png`. Pass when both runs reach the same outcome and head states reach `ready` within 60 seconds of exit.
- [ ] Lane 2. Read the Settings home description. Save `p4-describe.png`. Pass when the title and purpose describe the screen and name no device-specific value.
- [ ] Lane 3. Run Flash "Open Messages". Save `p4-privacy.png`. Pass when no description contains a contact name, a number, or message text visible in the screenshot.
- [ ] Lane 4. Count rows in the `vec_` table. Save `p4-vectors.png`. Pass when the count equals the number of ready states and edges.
- [ ] Lane 5. Switch `embedding.provider` to a second configured provider and start a device run. `backfill --all` only harvests, so it fills no `vec_` table. The run's `prepare_run` queues the ready rows that have no vector for the new model. Save `p4-provider-switch.png`. Pass when a second `vec_` table fills and the first is unchanged.
- [ ] Lane 6. Remove the Gemini key and run a device task. Save `p4-no-key.png`. Pass when the run succeeds and descriptions stay `pending` with one warning in the log.
- [ ] Lane 7. Exit a run while describer jobs are queued, then start a new run. Save `p4-requeue.png`. Pass when the new run's `prepare_run` completes the earlier `pending` rows.
- [ ] Lane 8. Override `nodes.app_memory_describer` in `config/artemis.jsonc` with a different model. Save `p4-node-override.png`. Pass when the `llm_call` traces of the describer name the override model.
- [ ] Lane 9. Inspect `llm_call` traces of the describer during a long run. Save `p4-concurrency.png`. Pass when no more than 2 describer calls overlap.
- [ ] Lane 10. Read edge descriptions after lane 1. Save `p4-edges.png`. Pass when each edge description names its source and destination titles.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The median wall time per agent step on the same device task at trunk and head, with describer jobs running at head.
- [ ] Probe. Run Flash "Open Settings and open Display" five times per side, interleaved, and read step times from DataEngine step timestamps.
- [ ] Baseline. Record the trunk median step time first.
- [ ] Rule. Fail when the head median step time exceeds trunk by more than 5 percent.

**Review gate.** None. P4 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands P4 to the operator, who lands it after P3.

## Find targets and routes (P5)

**Depends on.** P4.

**Files.**

- [ ] Create `artemis/app_memory/retrieval.py`.
- [ ] Create `artemis/app_memory/routing.py`.
- [ ] Create `artemis/app_memory/hints.py`.
- [ ] Edit `artemis/app_memory/service.py` and `artemis/app_memory/store.py`.
- [ ] Create `tests/unit/app_memory/test_retrieval.py`, `tests/unit/app_memory/test_routing.py`, and `tests/unit/app_memory/test_hints.py`.

**Build.**

- [ ] Write tier 1 and tier 2 in `retrieval.py` per `retrieval.md`. Use the vector partition per map, the similarity floor, and the `app_memory_selector` node through `acomplete_structured`. Return `TargetResolution` or `NoTarget`.
- [ ] Write `routing.py` with `locate`, the edge cost function, Dijkstra with a 15-hop cap, and `RouteTracker`. Every constant is named at the top of the module.
- [ ] Write `hints.py` with one render function per hint variant, chosen from a table keyed by the route kind.
- [ ] Implement `request_targets` and `route_for` in `service.py`, with retrieval on a bounded background queue and a per-run cache keyed by milestone.

**You see.**

- [ ] A lane script calls `route_for` for "Turn on dark theme" on the Settings home screen and prints a route ending at the Display state.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/app_memory/test_retrieval.py` gains the cases in `retrieval.md`, with a hash-based fake `EmbeddingProvider`. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/app_memory/test_routing.py` gains the weight, discount, localization, and tracker cases in `routing-and-hints.md`. Run `uv run pytest tests/unit/app_memory -q`.
- [ ] `tests/unit/app_memory/test_hints.py` gains a golden text per variant and a check that no coordinate or masked value appears. Run `uv run pytest tests/unit/app_memory -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no retrieval, so record that. At head, build a map from a device run that visits Display, then retrieve "Turn on dark theme". Save `p5-regression.png`. Pass when the target is the Display state.
- [ ] Lane 2. Retrieve "Turn on Bluetooth" after a run that toggled Bluetooth. Save `p5-edge-hit.png`. Pass when an edge hit nominates the Bluetooth screen and the last hop is that toggle.
- [ ] Lane 3. Retrieve "Order a pizza". Save `p5-no-target.png`. Pass when the result is `NoTarget` and no selector call ran for a map below the floor.
- [ ] Lane 4. Retrieve "Play a song" with maps for YouTube and YouTube Music. Save `p5-tier2.png`. Pass when exactly one tier 2 call ran and it chose one app.
- [ ] Lane 5. Relabel a map with an older `version_code` and retrieve from it. Save `p5-borrowed.png`. Pass when the result is `borrowed`.
- [ ] Lane 6. Render the route from Settings home to Display. Save `p5-hint.png`. Pass when the text matches the spec format and contains no coordinates.
- [ ] Lane 7. Locate the current screen while it shows an unmapped Settings page. Save `p5-from-launch.png`. Pass when the route starts with the app launch hop.
- [ ] Lane 8. Add no-effect observations to the short path's first edge and route again. Save `p5-weights.png`. Pass when Dijkstra picks the longer, reliable path.
- [ ] Lane 9. Walk the device along a route by hand, then step off it twice into unmapped screens. Save `p5-tracker.png`. Pass when the tracker advances, then reroutes, then hides the hint after 2 unknown turns.
- [ ] Lane 10. Block network access to the embedding provider and retrieve. Save `p5-provider-down.png`. Pass when the result is `NoTarget` with one warning.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Trunk has no retrieval, so measure the diff-added work in absolute terms. The p95 of the vector search per map, the p95 of `route_for` on a 2,000-state map, and the end-to-end retrieval time per milestone.
- [ ] Probe. A lane script runs 100 vector searches and 100 `route_for` calls on a synthetic 2,000-state map, then 10 real retrievals, three rounds interleaved with a trunk `make test` run.
- [ ] Baseline. Record the trunk `make test` wall time first.
- [ ] Rule. Fail when vector search p95 exceeds 10 ms, when `route_for` p95 exceeds 10 ms, when any retrieval exceeds the 20 second budget, or when head `make test` time exceeds trunk by more than 10 percent.

**Review gate.** None. P5 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands P5 to the operator, who lands it after P4.

## Give the Pro Operator its route (P6)

**Depends on.** P5.

**Files.**

- [ ] Edit `artemis/graph/graph.py`.
- [ ] Edit `artemis/agents/operator/prompts.py`.
- [ ] Edit `artemis/agents/operator/operator.py`.
- [ ] Edit `artemis/agents/operator/operator.json`.
- [ ] Edit `artemis/config/agent.py` and `config/artemis.jsonc`.
- [ ] Create `tests/unit/agents/test_app_memory_route_component.py` and `tests/unit/graph/test_app_memory_node.py`.

**Build.**

- [ ] Add the `app_memory_targets` node between `planner` and the convergence node in `get_graph`, through a new `_add_app_memory_node` helper. Leave the graph unchanged when hints are disabled.
- [ ] Call `request_targets` after an accepted plan write in `_process_plan_write`, through one call into a new helper.
- [ ] Add `AppMemoryRoutePromptComponent` to `prompts.py`, modeled on `HistoricalStateHintPromptComponent`. Insert it after `PlanRecitationPromptComponent` in both component lists in `operator.py`.
- [ ] Add the gated sentence about the route block to the Operator system template.
- [ ] Add the `hints` block to `AppMemoryConfig` and `config/artemis.jsonc`.

**You see.**

- [ ] On a device Pro run of "Turn on dark theme" with a prepared map, the Operator prompt in the `llm_call` trace contains `--- App Memory: Known Route (advisory) ---`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/unit/graph/test_app_memory_node.py` gains a case that the graph routes `planner` through `app_memory_targets` when hints are on and is unchanged when they are off. Run `uv run pytest tests/unit/graph -q`.
- [ ] `tests/unit/agents/test_app_memory_route_component.py` gains no active milestone, retrieval still running, and a golden block. Run `uv run pytest tests/unit/agents -q`.
- [ ] `tests/unit/app_memory/test_service.py` gains a scripted Pro run against `MockDeviceDriver` with app memory raising on every call, which completes with the same result. Run `uv run pytest tests/unit/app_memory -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on the configured `swarm workers` model at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. With a map prepared by an earlier run, run Pro "Turn on dark theme" on a device at trunk and head. Save `p6-regression.png`. Pass when both runs complete, the head prompt contains the route block, and the head run takes no more steps than trunk.
- [ ] Lane 2. Repeat lane 1 at head with `hints.enabled` false. Save `p6-hints-off.png`. Pass when no prompt contains the route block.
- [ ] Lane 3. Run Pro with a goal whose plan gains a milestone mid-run. Save `p6-plan-edit.png`. Pass when the log shows retrieval for only the new milestone key.
- [ ] Lane 4. During a Pro run, inject an instruction through `mobile_manage_task inject_instruction` that moves the agent to another app. Save `p6-divergence.png`. Pass when the hint changes to rerouted or hides.
- [ ] Lane 5. Slow the selector with a node override to a slower model. Save `p6-late-route.png`. Pass when the first Operator turn has no block, a later turn has it, and no turn waits on retrieval.
- [ ] Lane 6. Run Pro "Turn on dark theme, then play a Coldplay song on YouTube" with maps for both apps. Save `p6-cross-app.png`. Pass when each milestone gets a route in its own app.
- [ ] Lane 7. Run Pro on an app with no map. Save `p6-no-map.png`. Pass when no block appears and the run behaves as on trunk.
- [ ] Lane 8. Run Pro with only an older-version map for the target app. Save `p6-borrowed.png`. Pass when the block carries the older-version note.
- [ ] Lane 9. Corrupt `app_memory.db` before a Pro run. Save `p6-corrupt.png`. Pass when the run completes and the log has one app memory warning.
- [ ] Lane 10. After lane 1, read an Operator `llm_call` trace from late in the run. Save `p6-scrub.png`. Pass when only the latest observation contains a route block.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The median wall time per Pro step and the time to the first Operator turn, on the same device task at trunk and head.
- [ ] Probe. Run Pro "Turn on dark theme" five times per side, interleaved, and read both times from DataEngine trace timestamps.
- [ ] Baseline. Record the trunk medians first.
- [ ] Rule. Fail when the head median step time exceeds trunk by more than 5 percent, or when the head first-turn time exceeds trunk by more than 500 ms.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1 and lane 4 screenshots into `/tmp/swarm-p6/media/p6-review-route.png` and `/tmp/swarm-p6/media/p6-review-divergence.png`.
- [ ] Record a 30 to 60 second video of the lane 1 head run with the route block visible in the agent stream. Save it as `/tmp/swarm-p6/media/p6-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Base and verdict are current under the execution playbook and the patch-id rule in `playbooks/shipping.md`.
- [ ] The root hands P6 to the operator, who lands it last.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

Three open questions shaped this plan. Two were settled before writing, and one is still open.

**sqlite-vec works on the project's Python on Windows.** A throwaway probe, not committed, ran under `uv run --no-project --python 3.12 --with sqlite-vec`. It printed Python 3.12.2, SQLite 3.43.1, `enable_load_extension` present, and `vec_version` v0.1.9. A `vec0` table with a partition key and cosine distance answered a top-20 query over 1,000 of 5,000 768-dimension vectors in 2.15 ms. The partition key replaces the spec's one-table-per-model filter for map scoping. It is measured on Windows only. Ubuntu CI is unproven.

**Flash pre-action screens already store a structured tree.** This was settled by reading the code. `observe` in `artemis/mcp/observation.py:98` saves each screenshot with `device_data.elements`, and `get_or_create_image` in `artemis/data_engine/engine.py:811` keeps the first tree. Flash later passes text at `artemis/agents/flash/runner.py:737`, but text never overwrites the stored list. Old Flash traces can be backfilled, which corrects the spec.

**An offline Pro run with `ARTEMIS_MOCK_DRIVER=1` and `ARTEMIS_FAKE_LLM=1` reaching completion is unproven.** `FakeChatModel` in `artemis/llm/fake_model.py` saves a checked plan when `save_note` is bound, which should end the Pro loop. Nobody has run it. P1 lane 1 depends on it.

## Appendix B. Alternatives rejected

**A new `DataEngine.add_step_listener` hook.** The spec asked for one. `DataEngine.subscribe` already delivers `step_recorded` and `session_ended`, so a second hook would duplicate it. The live path stays best-effort, because a step row can lag its event, and the post-run sweep makes the result complete.

**Finalizing in `_finalize_tracing_safely`.** The spec named that call site. By then `async with context` has exited and the DataEngine is shut down. Finalizing from the `session_ended` event and flushing in `ArtemisContext.__aexit__` keeps both profiles on one path.

**A new job queue for describer work.** `StepMemoryService` in `artemis/memory/step_memory.py` already gives keyed, bounded, retried, non-blocking jobs. A separate instance with its own lens reuses it. Sharing `ctx.step_memory` was rejected, because the visual summarizer owns that instance.

**One PR per spec note.** Seven PRs would leave P2 and P3 without a testable behavior of their own. Six PRs each end in a state a lane can observe.

**A `quality_ratchet.py` metric scoped to `artemis/app_memory` only.** That lets old long functions grow past 100 lines unchecked. The global count of 111 stops new long functions anywhere, and the scoped count of 0 keeps the new package clean.

## Appendix C. Risks

**No device or adb on the planning machine.** `adb` is not on PATH, and no device is attached. Every device lane needs the operator's device or an emulator. The owner of each PR confirms `adb devices` before the first lane.

**Broad exception headroom.** `.quality-baseline.json` allows 754 broad handlers, and the tree has 744. Harvesting must never raise into the agent. The single `guarded` decorator in P3 adds about one handler in total. Owners of P3 through P6 watch the ratchet output.

**sqlite-vec on Ubuntu CI.** Measured on Windows only. If the CI wheel fails, `store.py` falls back to numpy cosine search per `decisions/0006-embedded-vector-index.md`. The P2 owner watches the first CI run.

**A dropped LLM node override.** `_expand_default_into_nodes` drops `nodes` overrides for nodes outside its list. P4 fixes it at the root. The P4 owner watches for changed resolved models in other nodes.

**Long existing functions.** `_run_task` in `third_party/mobile_use/sdk/agent.py` is 403 lines and `record_step` is about 155. P1 and P3 add only one-line calls inside them.

**Executable bits on Windows.** The import lost the executable bit on five scripts, which was fixed by hand. An owner on Windows checks `git ls-files -s` on any new shell script.

## Appendix D. Links and reading list

Read these before editing.

- `docs/specs/app-memory/README.md`, then its reading order.
- `docs/specs/shared/step-recording-fields.md`.
- `CLAUDE.md` for the specs vault rules.
- `skills/how/SKILL.md` for P1, P3, and P6, which change existing flows.
- `skills/interrogate/SKILL.md` for P5 and P6, where the route design meets agent behavior.
- `skills/architect/SKILL.md` for P2 and P5, which set the module shapes.
- The decision trail per `skills/show-me-your-work/SKILL.md`, kept in `~/.claude/orchestrate/app-memory/` and committed only on the operator's request.
