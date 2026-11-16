---
feature: app-memory
status: draft
depends_on:
  - ../shared/step-recording-fields.md
  - data-model.md
code:
  - artemis/app_memory/abstraction.py
  - artemis/utils/ui_filter.py
  - artemis/utils/image_hash.py
---

# State abstraction

This note covers how a recorded screen becomes a state, and how a live screen is matched to a
stored state. Harvesting and routing both depend on it. Abstraction is a pure function with no
device calls and no LLM, so it is cheap enough to run on every step.

## Input

A `ScreenObservation`:
- `package`, `activity`, `version_code`
- `elements`: the structured, filtered, flat element list
- `dhash`: the screenshot's perceptual hash
- `ocr_tokens`: optional

All of these come from the step record (see
[step-recording-fields](../shared/step-recording-fields.md)) or, at routing time, from the
current perception.

The element list is **flat**. `parse_hierarchy_xml_to_elements` drops nesting, so containment is
worked out from bounds.

## Behaviour

### 1. Exclude

- **System UI elements:** status bar, navigation bar and IME keyboard windows.
- **Elements outside the screen, or smaller than the `ui_filter` minimum.**

The keyboard being open or closed therefore never changes the state.

### 2. Mask variable content

For each remaining element:

- **List items.** An element whose bounds lie inside a `scrollable` element's bounds is a list
  item. List items are dropped. Their container is kept with a `list` marker and no count. This
  covers feeds, search results, chats and settings lists that scroll.
- **Text fields.** For editable elements, the text is dropped and the hint kept.
- **Long text.** Text over 40 characters is content, not a label, and is dropped.
- **Patterns.** Numbers, times, dates, durations, currency, percentages, email addresses, phone
  numbers and URLs inside the remaining text become `<NUM>`, `<TIME>`, `<DATE>` and so on.
- **Kept as-is:** `resource_id`, `class`, `content_desc` (pattern-masked like text), and the
  `clickable`, `scrollable`, `editable`, `checkable` and `selected` flags.

### 3. Overlay and tab markers

- **Overlays.** A dialog, bottom sheet or popup over a page is a **different state** from the
  page alone, because the possible actions differ. It is detected by a window or element of a
  dialog class covering part of the screen, or by the helper's window metadata.
- **Tabs.** A tab bar with a different `selected` tab is a different state. The selected tab's
  label is added to the skeleton.
- **Scroll position is not a state.** The same screen scrolled is the same state.

### 4. Coarse key

`coarse_key = sha1(package | activity | sorted (class, resource_id) pairs of non-list elements |
overlay marker | selected tab label)`

Elements with an empty `resource_id` contribute `(class, "")`.

### 5. Skeleton and static tokens

- **`skeleton`**: the multiset of `(class, resource_id, flags)` tokens of non-list elements, plus
  the `list` container markers.
- **`static_tokens`**: the set of masked text and `content_desc` values, plus the last segment of
  each `resource_id`, for example `settings_title` from `com.app:id/settings_title`.

### 6. Opaque screens

If fewer than 5 non-list elements remain after masking, the state is **opaque**. That happens
with Flutter, Canvas or games. Opaque states are identified by `dhash`, with Hamming distance
≤ 8 (the same threshold `HistoricalStateHintPromptComponent` uses), plus `ocr_tokens` when OCR
ran. They match less reliably, and routing weights them accordingly (see
[routing-and-hints](routing-and-hints.md)).

## Matching

`match(observation, map) -> state_id | None` decides whether a screen is a state already in the
map:

1. **Exact.** Look for a non-opaque state in the same map with the same `coarse_key`. If several
   share it, go to step 2 among them.
2. **Fuzzy.** Among the map's states with the same `activity` (or all states when `activity` is
   null), compute
   `score = 0.6 · jaccard(skeleton) + 0.4 · jaccard(static_tokens)`.
   The best score ≥ **0.80** is a match.
3. **Opaque.** Opaque observations only match opaque states, by `dhash` distance and then
   `ocr_tokens` overlap.
4. **No match** returns None. The harvester creates a new state; the router treats the screen
   as unknown.

`cluster_ordinal` in the `state_id` (see [data-model](data-model.md)) separates distinct states
that share a coarse key but failed fuzzy matching against each other.

## Implementation notes (P2)

- `ScreenObservation` also carries an optional `screen_size`. Without it, "outside the screen"
  cannot be checked and only elements with empty or negative bounds are dropped.
- Fuzzy matching only compares screens whose overlay and tab markers are equal. Otherwise a dialog
  over a page scores at least 0.80 against the bare page and wrongly matches it.
- Overlays are detected from the dialog class and tabs from the selected tab label. Helper window
  metadata is not used yet.
- A text field's hint is read from an optional `hint` or `hint-text` key. UIAutomator dumps have
  none, so the hint is lost for them.

## Contracts

- `abstract(observation) -> AbstractScreen` is pure and deterministic. The same input always
  gives the same `coarse_key`, `skeleton` and `static_tokens`.
- No value removed by masking is ever stored or embedded.
- The thresholds 0.80, 40 characters, 5 elements and dHash ≤ 8 are named constants in
  `abstraction.py`, starting values to tune on real traces.

## Failure handling

- **Activity null:** skip the activity filter and let fuzzy matching run over the whole map.
- **Elements empty** (the hierarchy failed): the step is not harvested. A screenshot alone is
  not used to create a non-opaque state.

## Testing

- Golden tests on recorded element lists, in `tests/unit/app_memory/fixtures/`:
  - the same settings screen at two scroll positions gives the same state;
  - a feed with different items gives the same state;
  - the page with a dialog over it gives a different state;
  - two tabs give different states;
  - the keyboard open and closed gives the same state.
- **Backend parity:** the same screen dumped by the helper and by UIAutomator gives the same
  `coarse_key`. Use the dumps from `artemis/core/diagnostics/hierarchy_parity.py`.
- Masking never lets a number, email address or text field's contents through, checked with a
  property test over random strings.
