---
feature: shared
status: draft
depends_on: []
code:
  - artemis/data_engine/engine.py
  - artemis/agents/flash/runner.py
  - artemis/graph/graph.py
  - artemis/clients/accessibility_client.py
  - artemis/clients/screen_client_factory.py
  - third_party/mobile_use/clients/ui_automator_client.py
  - artemis/utils/app_launch_utils.py
---

# Step recording fields

Every recorded step must carry enough about the screen the agent acted on to identify that
screen again in a later run. Today it does not. This note specifies the missing fields. It is a
prerequisite for [app-memory](../app-memory/README.md) and is useful on its own for trace
inspection.

## Current gaps

- **Flash records the wrong screen, as text.**
  [runner.py:737](../../../artemis/agents/flash/runner.py#L737) stores
  `exec_result.ui_elements_text`, which the executor fills from the observation taken *after*
  the action ([action_executor.py:244](../../../artemis/mcp/action_executor.py#L244)). It is a
  flattened string, so resource-ids and classes are lost.
- **Pro records the right screen.** [graph.py:160](../../../artemis/graph/graph.py#L160) passes
  the structured, OCR-fused element list of the pre-action screen.
- **Neither profile records the activity or the app version.** `record_step` derives
  `foreground_app` from package attributes in the tree
  ([engine.py:901-911](../../../artemis/data_engine/engine.py#L901-L911)), and nothing else.
- **The helper already reports the activity, but the client drops it.** `HierarchyDumper` puts
  `activity` in the snapshot response (`HierarchyDumper.java:169`), and
  `AccessibilityClient` does not read it.

## Behaviour

### New fields on every step

These go in `StepRecord.extra_metadata`, so no schema migration is needed:

| Key | Type | Source |
|---|---|---|
| `foreground_app` | str | Unchanged. |
| `activity` | str or null | Helper snapshot `activity`. On the UIAutomator backend, `dumpsys activity activities` through the existing parser in `artemis/utils/app_launch_utils.py`. Null if both fail. |
| `version_code` | int or null | Installed `versionCode` of `foreground_app`. |
| `version_name` | str or null | Installed `versionName` of `foreground_app`. |
| `ui_backend` | `"helper"` or `"uiautomator"` | The backend that produced this step's tree. The trees differ slightly between backends. |

### Structured pre-action tree for Flash

Flash passes the structured element list of the observation it acted on, the same shape Pro
passes, as `ui_tree`. The model still sees the text rendering; only what is recorded changes.
`ObserveResult.elements` ([action_types.py](../../../artemis/mcp/action_types.py)) already
carries a structured list. The implementation must confirm it holds the full filtered element
list, not only the indexed subset, and widen it if not.

The pre-action tree is stored with the pre-action image in the `images` table, as today. Images
are keyed by SHA-256, so a byte-identical screenshot reuses the tree stored the first time. That
is acceptable: identical pixels mean the same screen.

### Version lookup

- One `pm list packages --show-versioncode` call at run start fills a per-run cache of package to
  `versionCode`. The `versionName` for a package is read with `dumpsys package <pkg>` the first
  time that package is seen in the foreground.
- The cache entry for a package is invalidated when a step runs an adb command containing
  `install` or `uninstall`, and is reloaded on next use.
- Lookups never block step recording. If a lookup is in flight, the step records null.

### Activity plumbing

- `AccessibilityClient` reads `activity` from the snapshot response and returns it on its screen
  data.
- `UIAutomatorScreenData` and `ScreenData` gain an optional `activity` field.
- `FallbackScreenClient` passes it through unchanged.
- The UIAutomator backend fills it with the `dumpsys` fallback only when a consumer asks for it.
  App memory harvesting asks for it.

## Contracts

- Missing values are null, never an empty string or a guess.
- Old records keep working. Readers treat absent keys as null.

## Failure handling

- **`dumpsys` fails or times out** (1 s cap): the field is null and the step is still recorded.
- **The helper returns no activity**, for example when an older APK is installed: the
  `dumpsys` fallback runs.

## Testing

- Unit tests in `tests/unit/data_engine/`: a Flash and a Pro step both record a structured
  pre-action tree and the new keys.
- `AccessibilityClient` parses `activity` from a recorded snapshot fixture.
- The version cache: one call per run, invalidation after `install`.
