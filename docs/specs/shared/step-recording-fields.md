---
feature: shared
status: draft
depends_on: []
code:
  - artemis/data_engine/engine.py
  - artemis/data_engine/screen_identity.py
  - artemis/runtime/app_versions.py
  - artemis/agents/flash/runner.py
  - artemis/graph/graph.py
  - artemis/graph/perception.py
  - artemis/mcp/observation.py
  - artemis/clients/accessibility_client.py
  - artemis/clients/screen_client_factory.py
  - third_party/mobile_use/clients/ui_automator_client.py
  - artemis/drivers/base.py
  - artemis/drivers/android/adb_driver.py
  - artemis/controllers/device_controller.py
  - third_party/mobile_use/controllers/unified_controller.py
  - artemis/tools/command_tool.py
  - artemis/utils/app_launch_utils.py
---

# Step recording fields

Every recorded step must carry enough about the screen the agent acted on to identify that
screen again in a later run. This note specifies the fields that do that. It is a prerequisite
for [app-memory](../app-memory/README.md) and is useful on its own for trace inspection.

## Gaps this note closes

- **Flash passed the wrong screen to `record_step`, as text.** `_record_action_step` in
  [runner.py](../../../artemis/agents/flash/runner.py) passed `exec_result.ui_elements_text`,
  which the executor fills from the observation taken *after* the action
  ([action_executor.py](../../../artemis/mcp/action_executor.py)). It is a flattened string,
  so no `foreground_app` could be derived from it.
- **The stored Flash pre-action tree was already structured.** `observe` in
  [observation.py](../../../artemis/mcp/observation.py) saves each screenshot with the
  structured element list first, and `get_or_create_image` in
  [engine.py](../../../artemis/data_engine/engine.py) keeps the first tree stored for an image.
  The text never overwrote it, so old Flash traces hold structured pre-action trees and can be
  backfilled.
- **Pro records the right screen.** [graph.py](../../../artemis/graph/graph.py) passes the
  structured element list of the pre-action screen.
- **Neither profile recorded the activity or the app version.** `record_step` derived only
  `foreground_app`, from package attributes in the tree.
- **The helper already reported the activity, but the client dropped it.** `HierarchyDumper`
  puts `activity` in the snapshot response (`HierarchyDumper.java:169`), and
  `AccessibilityClient` did not read it.

## Behaviour

### New fields on every step

These go in `StepRecord.extra_metadata`, so no schema migration is needed. The four new keys
are present on every new step:

| Key | Type | Source |
|---|---|---|
| `foreground_app` | str | From the tree as before. When the tree gives none, as for Flash, from the observed pre-action screen. Absent when unknown. |
| `activity` | str or null | Helper snapshot `activity`. When the helper gives none, and always on the UIAutomator backend, the resumed activity from `dumpsys activity activities`, parsed by `parse_foreground_task` in `artemis/utils/app_launch_utils.py`. |
| `version_code` | int or null | Installed `versionCode` of `foreground_app`. |
| `version_name` | str or null | Installed `versionName` of `foreground_app`. |
| `ui_backend` | `"helper"`, `"uiautomator"` or null | The backend that produced this step's tree. The trees differ slightly between backends. |

Both backends record the fully qualified class, for example `com.android.settings.Settings`.
`dumpsys` prints `com.android.settings/.Settings`, which the UIAutomator client expands.

### Screen identity is captured at observation

A step must describe its pre-action screen, not whatever the device shows when the step is
written. Both observation sites call `DataEngine.note_observed_screen(image_name, screen,
ui_tree)` with the screen data they captured: `observe` for Flash and `perception_node` in
[perception.py](../../../artemis/graph/perception.py) for Pro. The DataEngine keeps the
activity, backend and tree-derived app per image hash for the session.

`record_step` calls `DataEngine._stamp_screen_identity` in one line. It looks up the step's
`pre_image_name` and the app's version, and sets each key with `setdefault`, so a value a
caller passes explicitly wins. Images are keyed by SHA-256, so a byte-identical screenshot
shares one identity. That is acceptable: identical pixels mean the same screen.

### Structured pre-action tree for Flash

Flash passes no `ui_tree`. The image row of the pre-action screenshot already holds the
structured tree that `observe` stored, the same `ScreenDataResponse.elements` shape Pro
stores. The model still sees the text rendering; only what is recorded changes.

### Version lookup

`AppVersionCache` in [app_versions.py](../../../artemis/runtime/app_versions.py) is opened by
`DataEngine.start_session` from the device serial, one per session.

- One `pm list packages --show-versioncode` call, started at session start, fills every
  `versionCode`. The `versionName` for a package is read with `dumpsys package <pkg>` the first
  time the package is looked up.
- Both adb command tools in [command_tool.py](../../../artemis/tools/command_tool.py) report
  each command line. A command containing `install`, which covers `uninstall`, drops every
  cached version, because the package an install touches is not always named in the command.
  The next lookup reloads. A load that started before the command is discarded.
- Lookups never block step recording. All adb work runs on one background worker. A step
  whose lookup is in flight records null, so the first step in a newly seen app records a null
  `version_name`.

### Activity plumbing

- `AccessibilityClient` reads `activity` from the snapshot response and returns it on its screen
  data, with `ui_backend = "helper"`.
- `UIAutomatorScreenData`, `ScreenData` and `ScreenDataResponse` gain optional `activity` and
  `ui_backend` fields. The adb driver and the unified controller copy them through.
- `FallbackScreenClient` returns the serving client's screen data unchanged, so the fields name
  whichever backend served that capture.
- The UIAutomator backend reads the activity on every capture, with `ui_backend =
  "uiautomator"`.

## Contracts

- Missing values are null, never an empty string or a guess.
- Old records keep working. Readers treat absent keys as null.

## Failure handling

- **`dumpsys` fails or times out** (1 s cap): the field is null and the step is still recorded.
- **The helper returns no activity**, for example when an older APK is installed or no window
  has changed since the helper started: the `dumpsys` fallback runs.
- **adb is unavailable**, as in mock and cloud runs: the version fields are null. The listing is
  not retried in that session.

## Testing

- `tests/unit/data_engine/test_engine.py`: a step records its pre-action screen's identity, and
  a step on an unknown screen records null for each new key.
- `tests/unit/agents/test_flash_runner.py`: a Flash step records the structured pre-action tree
  and the new keys, and never stores the post-action text as a tree.
- `tests/unit/clients/test_accessibility_activity.py` parses `activity` from a snapshot fixture
  shaped like the helper's answer, including the `dumpsys` fallback.
- `tests/unit/clients/test_uiautomator_activity.py`: the UIAutomator backend's activity and its
  failure path.
- `tests/unit/runtime/test_app_versions.py`: one listing per run, non-blocking lookups, and
  invalidation after `install`.
