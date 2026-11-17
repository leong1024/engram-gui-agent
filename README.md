<p align="center">
  <img src="./docs/assets/brand/engram-banner.png" alt="Engram: the self-learning Android agent that remembers every app it touches" width="100%" />
</p>

<p align="center">
  Other agents wake up with amnesia. Engram wakes up with a map.<br>
  Closed-loop memory. Graph-engineered navigation. No retraining.
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache-2.0"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-server-8A2BE2.svg" alt="MCP server"></a>
  <img src="https://img.shields.io/badge/learning-closed--loop-success.svg" alt="Closed-loop learning">
  <img src="https://img.shields.io/badge/navigation-graph--engineered-orange.svg" alt="Graph-engineered navigation">
</p>

---

## Every other GUI agent starts from zero. Every time.

Ask a typical phone agent to turn on dark mode. It squints at the home screen, guesses, wanders, and finds Settings. Ask again tomorrow and it does the same thing, because it has forgotten everything it learned.

**Engram closes the loop.** An *engram* is the trace a memory leaves behind in a brain. Engram builds that trace for software. Every screen it visits, every tap that worked, and every dead end becomes part of a living **cortex** for that app. The next time you ask for something, it already knows where the road goes.

```mermaid
flowchart LR
    T["You give a task"] --> A["Engram acts"]
    A --> H["Harvest<br/>every screen, every tap"]
    H --> C[("Cortex<br/>a map of each app")]
    C --> R["Recall<br/>find the screen your goal lives on"]
    R --> N["Route<br/>the cheapest known path"]
    N --> A
```

|  | A typical agent | Engram |
|---|---|---|
| Knows the app | Never. It looks again each task. | Yes. It keeps a map of every app version it has seen. |
| After a task | Everything is thrown away. | Every screen and action joins the cortex. |
| Finding a goal | Guess and scroll. | Search the cortex by meaning, then plan a route. |
| Learning loop | Open. Nothing carries over. | Closed. It is self-learning: it feeds on its own runs, and **no weights change**. |
| When a run fails | Nothing is recorded. | The run counts for less in the map, so bad routes fade. |

### Why the cortex matters

- **A closed learning loop.** Every run feeds the cortex, and the cortex feeds the next run. The more it works, the more it has to go on. There is no retraining and no labeled data.
- **Graph engineering at the core.** Each app version becomes a state graph. Screens are nodes. Actions are edges, weighted by how often they really worked. Routes come from Dijkstra over that graph, so reliable roads win over short ones.
- **Semantic retrieval for GUIs.** Each screen gets a plain-language description and a vector embedding. A goal like "turn on dark theme" finds the Display screen through vector search and an LLM selector, with no hard-coded rule. Think RAG, but for phones.
- **A world model of every app.** The graph is a learned model of how each app behaves: where a tap leads and how reliably it gets there.
- **Self-correcting.** A failed run counts for less. Bad routes fade, and good ones strengthen.
- **Version-aware.** Maps are keyed by app package and version code, so an update does not poison what it learned.
- **Privacy by design.** The cortex stores masked structure. Typed text is never stored. Numbers, emails, and long text are masked, and descriptions are written in general terms.
- **Fault tolerant.** Memory is advisory. The agent keeps full control, and a fault in the memory layer is built not to change the result of a task. A unit test with a mock device covers it.
- **A real system, not a prompt.** Harvesting, enrichment, vector search, and routing run as separate background services with the failure handling to match.

### See it drive a real phone

<p align="center">
  <img src="./docs/assets/demo.gif" alt="An agent plans driving routes in Google Maps, then plays a Coldplay song on YouTube" width="100%" />
  <br>
  <em>Plans driving routes and totals the durations in Google Maps, then opens YouTube and plays a Coldplay song.</em>
</p>

### Built on a full agent stack

Engram ships with everything an agent needs on a real phone. **Flash** is a fast single-model loop. **Pro** is a multi-agent graph that plans, verifies, and recovers. An **MCP server** lets Claude Code, Cursor, Windsurf, and other IDEs drive a real device. The memory layer sits on top of both and feeds Pro its routes.

> **Honest status.** The cortex is built, merged, and covered by unit tests. It has not yet run on a real device, and its thresholds are untuned. [Status](#status) lists what is open.

This page describes how the system is built. Each section is a diagram first, with a few lines of text under it.

## Contents

1. [The system at a glance](#the-system-at-a-glance)
2. [Repository map](#repository-map)
3. [Two execution profiles](#two-execution-profiles)
4. [From screen to tap](#from-screen-to-tap)
5. [The LLM layer](#the-llm-layer)
6. [Two MCP servers](#two-mcp-servers)
7. [Data and context memory](#data-and-context-memory)
8. [App memory](#app-memory)
9. [Frameworks](#frameworks)
10. [Configuration](#configuration)
11. [Run it](#run-it)
12. [Develop](#develop)
13. [Status](#status)
14. [Origin](#origin)

## The system at a glance

```mermaid
flowchart LR
    subgraph IN["Front doors"]
        CLI["CLI<br/>artemis run, ui, doctor"]
        WEB["Web console<br/>Angular + FastAPI :8000"]
        MCPS["MCP server<br/>5 tools for IDEs"]
        SDK["Python SDK<br/>artemis-client"]
    end

    AGENT["artemis.sdk.Agent<br/>device lock, profile dispatch"]

    subgraph EXEC["Execution"]
        FLASH["Flash<br/>single-model loop"]
        PRO["Pro<br/>LangGraph multi-agent"]
    end

    subgraph IO["Perception and action"]
        PERC["Screen client<br/>helper APK, UIAutomator2 fallback"]
        ACT["Action server<br/>in-process MCP"]
        DEV[("Android device<br/>via ADB")]
    end

    LLM["LLM layer<br/>Gemini, OpenAI, Anthropic, local"]
    DE[("DataEngine<br/>data_engine.db")]
    AM[("App memory<br/>app_memory.db")]

    CLI --> AGENT
    WEB --> AGENT
    MCPS --> AGENT
    SDK --> WEB
    AGENT --> FLASH
    AGENT --> PRO
    FLASH --> PERC
    PRO --> PERC
    FLASH --> ACT
    PRO --> ACT
    PERC --> DEV
    ACT --> DEV
    FLASH --> LLM
    PRO --> LLM
    FLASH --> DE
    PRO --> DE
    DE -->|"step_recorded events"| AM
    AM -->|"route hint, Pro only"| PRO
```

Every task goes through `artemis.sdk.Agent`. It takes a cross-process lock on the device, then runs Flash or Pro. Both profiles write each step to the DataEngine. App memory listens to those writes and learns from them.

## Repository map

```mermaid
flowchart TB
    ROOT["engram-gui-agent"]
    ROOT --> A["artemis/<br/>core runtime"]
    ROOT --> M["mcp_server/<br/>IDE-facing MCP server"]
    ROOT --> APPS["apps/<br/>admin_console, showcase_ui"]
    ROOT --> PK["packages/<br/>artemis-client, accessibility-helper"]
    ROOT --> TP["third_party/<br/>mobile_use, vendored"]
    ROOT --> CFG["config/<br/>artemis.jsonc"]
    ROOT --> DOCS["docs/specs/<br/>design specs"]

    A --> A1["agents/ graph/<br/>Flash and Pro"]
    A --> A2["mcp/ drivers/ controllers/ clients/<br/>perception and action"]
    A --> A3["llm/ services/<br/>model layer"]
    A --> A4["data_engine/ memory/<br/>traces and context"]
    A --> A5["app_memory/<br/>screen map"]
```

| Path | What it holds |
|---|---|
| `artemis/agents/`, `artemis/graph/` | The Flash loop, the Pro graph, and the agents behind them. |
| `artemis/mcp/`, `artemis/drivers/`, `artemis/controllers/`, `artemis/clients/` | Screen capture and action execution. |
| `artemis/llm/`, `artemis/services/llm.py` | Model routing, fallback, structured output. |
| `artemis/data_engine/`, `artemis/memory/` | Trace storage and context compression. |
| `artemis/app_memory/` | The learned screen map. |
| `mcp_server/` | The MCP server that IDEs talk to. |
| `apps/admin_console/`, `apps/showcase_ui/` | FastAPI backend and Angular front end. |
| `packages/artemis-client/` | Zero-dependency Python client for the daemon. |
| `packages/artemis-accessibility-helper/` | Java APK that reads the screen on the phone. |
| `third_party/mobile_use/` | Vendored subset of Minitap's mobile-use. |
| `docs/specs/` | Design specs and decision records, one folder per feature. |

## Two execution profiles

`third_party/mobile_use/sdk/agent.py` picks the profile. `flash` runs `FlashRunner`. Anything else runs the Pro graph. The default is Pro.

| | Flash | Pro |
|---|---|---|
| Shape | One model in a loop | LangGraph of several agents |
| Plan | None | Planner writes milestones and checks |
| Safety net | None | Checks the target before each action |
| Verification | None | Read-only Checker, set by `verification_level` |
| App memory hints | No | Yes |
| Ends when | The model calls `report_task_status` | All top-level milestones are done |

### Flash

```mermaid
flowchart LR
    S["Start turn"] --> O["Observe<br/>screenshot + numbered elements"]
    O --> R["Render transcript<br/>scrub edge, chunks"]
    R --> L["Model call<br/>native tool use"]
    L --> T{"Tool calls?"}
    T -->|"none"| N["Nudge the model"] --> S
    T -->|"actions"| X["Execute through<br/>McpActionExecutor"]
    X --> REC["Record step<br/>DataEngine"] --> S
    T -->|"report_task_status"| E["End: completed or failed"]
```

### Pro

```mermaid
flowchart LR
    START(("start")) --> PL["planner"]
    PL --> AMT["app_memory_targets<br/>(only when hints are on)"]
    PL -.->|"hints off"| CV
    AMT --> CV["convergence<br/>deferred join"]
    CV --> G1{"convergence_gate"}
    G1 -->|"continue"| PE["perception"]
    G1 -->|"plan done, checks pending"| EX["exit_settlement"]
    G1 -->|"end"| FIN(("end"))
    PE --> OP["operator"]
    OP --> EC["execution_check"]
    EC -->|"actions"| VA["validator"]
    EC -->|"no actions"| CV
    VA --> SU["summarizer"]
    SU --> CV
    EX --> G2{"exit_settlement_gate"}
    G2 -->|"continue"| PE
    G2 -->|"end"| FIN
```

The loop is `perception → operator → execution_check → validator → summarizer → convergence`. The Checker and the planner's validation run as background tasks inside `execution_check` and `exit_settlement`. They are not graph nodes.

### Pro agents

| Agent | Job |
|---|---|
| `planner` | Writes the task plan once: milestones plus `verify` and `assert` checks. |
| `operator` | Reads the screen and plan each turn, calls tools, and emits an action list. |
| `validator` | Runs the actions. A single action passes the safety net first (XML, then pixel). Two or more run as a burst. |
| `summarizer` | Hands the step to the background step-memory service. |
| `checker` | Read-only audits against the plan: per checkpoint and at exit. |
| `explorer` | Finds hard-to-locate UI. Three tiers: flash, pro, ultra. |
| `diagnoser` | Finds the root cause of a failure. |
| `history_analyzer`, `log_analyzer` | Answer questions about past steps and logcat output. |
| `object_detector`, `image_processor` | Visual grounding and image tools for the Explorer. |
| `video_analyzer` | Reads the scrcpy session recording. |
| `outputter` | Writes the final report. |

## From screen to tap

```mermaid
sequenceDiagram
    participant Ag as Agent (Flash or Pro)
    participant SC as Screen client
    participant H as Helper APK
    participant U as UIAutomator2
    participant AS as ActionSession
    participant AC as Actuator
    participant D as Device (adbutils)

    Ag->>SC: get_screen_data()
    SC->>H: /snapshot over adb forward :18888
    alt helper answers
        H-->>SC: XML + screenshot
    else helper fails
        SC->>U: dump_hierarchy()
        U-->>SC: XML + screenshot
    end
    SC-->>Ag: elements + screenshot + activity
    Note over Ag: optional OCR fusion,<br/>numbered element list
    Ag->>AS: call_tool(click, x, y)
    AS->>AC: in-process MCP, one call at a time
    AC->>D: adb input
    D-->>Ag: ActionResult
```

**Perception.** `FallbackScreenClient` tries the helper APK first and falls back to UIAutomator2. It retries the helper after 30 seconds. Set `ARTEMIS_HIERARCHY_BACKEND` to `helper` or `uiautomator` to pin one. OCR through Google Vision is optional and fuses with the hierarchy.

**Action.** `ActionSession` is an in-memory MCP client and server pair. It serializes calls, so only one action touches the device at a time. Coordinates are normalized to 0 to 1000.

```mermaid
flowchart LR
    AS["ActionSession"] --> SRV["FastMCP action server"]
    SRV --> ACT["Actuator protocol"]
    ACT --> ADB["AdbActuator"]
    ACT --> MOCK["MockActuator"]
    ADB --> UMC["UnifiedMobileController"]
    MOCK --> UMC
    UMC --> DRV["BaseDeviceDriver"]
    DRV --> AND["AndroidAdbDriver<br/>adbutils"]
    DRV --> MD["MockDeviceDriver"]
```

The action surface is defined in `artemis/mcp/action_manifest.py`. `click_sequence` is required. Other actions such as `swipe`, `input_text`, `press_key`, and `manage_app` are optional per actuator.

## The LLM layer

```mermaid
flowchart LR
    NODE["Agent node<br/>operator, planner, ..."] --> GL["get_llm(ctx, node)"]
    CFG[("config/artemis.jsonc<br/>default + per-node + fallback")] --> GL
    GL --> RT["Router"]
    RT --> G["Gemini / Vertex"]
    RT --> OA["OpenAI-compatible<br/>OpenAI, OpenRouter, xAI,<br/>Ollama, vLLM, custom"]
    RT --> AN["Anthropic"]
    G --> W["RobustChatModelWrapper<br/>retry, telemetry"]
    OA --> W
    AN --> W
    W --> FB{"Failure?"}
    FB -->|"another model could fix it"| FM["Fallback model"]
    FB -->|"no"| OUT["Result"]
    FM --> OUT
```

- Each agent node has its own model, with an optional fallback. Nodes without an override inherit `default`.
- `acomplete_structured` parses JSON and asks the model once to correct a bad reply.
- A circuit breaker and a failure classifier (`rate_limit`, `timeout`, `authentication`, and others) decide when to retry or switch.
- When retries run out, the task pauses on a pause file. Background jobs such as app-memory description raise `LLMExhaustedError` instead of pausing the run.
- `ARTEMIS_FAKE_LLM=1` swaps in a fake model for tests.

## Two MCP servers

The repository holds two unrelated MCP servers.

```mermaid
flowchart LR
    subgraph IDE["IDE side"]
        C["Claude Code, Cursor,<br/>Antigravity, Windsurf, Codex"]
    end
    subgraph A["mcp_server/ (front door)"]
        T["mobile_run_task<br/>mobile_manage_task<br/>mobile_get_device_state<br/>mobile_inspect_trace<br/>mobile_diagnose"]
    end
    subgraph B["artemis/mcp/ (inside a task)"]
        AX["Action server<br/>click_sequence, swipe, ..."]
    end
    C -->|"stdio or SSE"| T
    T -->|"spawns detached worker"| AG["artemis.sdk.Agent"]
    AG -->|"in-memory MCP"| AX
    AX --> DEV[("Device")]
    T -.->|"screenshots, hierarchy"| DEV
```

- `mcp_server/` is what your IDE connects to. `mobile_run_task` starts a detached worker and returns, and `mobile_manage_task` checks status, stops, or injects an instruction.
- `artemis/mcp/` is how agents touch the device during a task. It runs in memory with no network.
- `artemis mcp --install <client>` writes the config and the behavior rules in `mcp_server/rules.md` for a given IDE. Details are in [`mcp_server/README.md`](mcp_server/README.md).

## Data and context memory

### DataEngine

Every step lands in one SQLite file, with screenshots stored by content hash.

```mermaid
erDiagram
    sessions ||--o{ steps : has
    sessions ||--o{ traces : has
    sessions ||--o{ history_chunks : has
    steps }o--o| images : "pre and post"
    steps ||--o{ traces : emits

    sessions {
        text session_id PK
        text initial_goal
        text status
        int pid
    }
    steps {
        text step_id PK
        text action_taken
        text pre_image_name FK
        text post_image_name FK
        json extra_metadata
    }
    images {
        text image_name PK "sha256"
        json ui_tree
        text ocr_result
    }
    traces {
        text trace_id PK
        text type "agent, tool, log"
        json payload
    }
    history_chunks {
        text chunk_id PK
        text status "pending or ready"
        text rendered_text
    }
```

`extra_metadata` on each step carries `foreground_app`, `activity`, `version_code`, `version_name`, `ui_backend`, and a perceptual hash of the screenshot. App memory relies on those fields. Files live under the traces directory: `data_engine.db`, `images/<sha256>.jpg`, and one folder per session.

### Context memory

Both profiles keep the conversation in a `TranscriptLedger`, so a long run does not grow without bound.

```mermaid
flowchart LR
    S["S<br/>stable prefix"] --> F["F<br/>frozen history"] --> A["A<br/>active window"] --> T["T<br/>tail: current observation"]
    A -->|"older screenshots become<br/>visual summaries"| F
    F -->|"3-band chunks<br/>synopsis, interval, per step"| HC[("history_chunks")]
    HC -.->|"search_history<br/>replay_steps"| T
```

## App memory

App memory builds a map of each app version from what the agent actually did. Screens are states with their variable content masked. Actions that moved between them are edges. For each plan milestone, the Pro graph finds the target screen in the map, finds the cheapest route from the current screen, and shows that route to the Operator as advisory text. Execution is unchanged.

### Pipeline

```mermaid
flowchart TB
    subgraph LEARN["Learn (every run)"]
        DE[("DataEngine<br/>step_recorded")] --> TR["TraceReader"]
        TR --> SC["scan<br/>pair acting steps with<br/>the next non-wait screen"]
        SC --> AB["abstract<br/>mask text, drop list items,<br/>coarse key + skeleton"]
        AB --> MW["MapWriter<br/>match or create state,<br/>add edge, add observation"]
        MW --> DB[("app_memory.db")]
    end

    subgraph ENRICH["Describe and embed (background)"]
        DB --> DESC["Describer LLM<br/>title, purpose, affordances"]
        DESC --> EMB["Embedding provider<br/>gemini, openai, ollama"]
        EMB --> VEC[("vec_* tables<br/>sqlite-vec")]
    end

    subgraph USE["Use (Pro only)"]
        PLAN["Plan milestone"] --> RET["Retriever<br/>vector top-k + LLM selector"]
        VEC --> RET
        RET --> NAV["Navigator<br/>one tracker per milestone"]
        MGC["MapGraphCache<br/>one graph per map per run"] --> NAV
        DB --> MGC
        NAV --> HINT["hints.render"]
        HINT --> OPR["Operator prompt<br/>latest observation only"]
    end
```

### One run

```mermaid
sequenceDiagram
    participant P as Planner
    participant N as app_memory_targets
    participant R as Retriever
    participant V as sqlite-vec
    participant T as RouteTracker
    participant O as Operator

    P->>N: plan written
    N->>R: request_targets (returns at once)
    R->>R: embed milestone text, one call
    R->>V: nearest k, per map
    V-->>R: candidate states and edges
    R->>R: LLM picks one target
    R-->>T: KnownTarget + shared map
    loop each Operator turn
        O->>T: route_for(current screen)
        T-->>O: advisory route, or nothing
    end
```

The Operator never waits on retrieval. Until a target is found, `route_for` returns nothing and the prompt is unchanged.

### Store

```mermaid
erDiagram
    app_versions ||--o{ states : "package + version_code"
    states ||--o{ edges : "src"
    states ||--o{ edges : "dst"
    edges ||--o{ observations : counted_by
    states ||--o{ embeddings : has
    edges ||--o{ embeddings : has
    embedding_models ||--o{ embeddings : produces

    states {
        text state_id PK
        text coarse_key
        json skeleton
        json static_tokens
        text title
        text purpose
        text description_status "pending, ready, failed"
    }
    edges {
        text edge_id PK
        text action_signature
        json actions
        int confirmed_n
        int discounted_n
        int provisional_n
    }
    observations {
        text session_id PK
        text step_id PK
        text status "provisional, confirmed, discounted, dropped"
    }
    embeddings {
        text owner_kind "state or edge"
        text text_hash
    }
```

A map is one app package plus one `version_code`. There is no `maps` table. Vectors live in one sqlite-vec `vec0` table per embedding model, partitioned by map. Descriptions are embedded once and re-embedded only when their text changes. A query embeds only the milestone text.

### How a route is chosen

Each edge costs `-ln(p) + 0.1`, where `p` is the edge's observed success rate under a Beta(1, 1) prior. Confirmed observations count 1.0, provisional 0.5, discounted 0.25. Rustworkx runs Dijkstra over the shared graph, capped at 15 hops. Ties go to fewer hops, then to the more recently seen path.

| Stage | Where | Key constants |
|---|---|---|
| State match | `abstraction/matching.py` | 0.60 skeleton + 0.40 static tokens, threshold 0.80 |
| Vector search | `retrieval/` | top-k 20, similarity floor 0.35 |
| Selector | `retrieval/selector.py` | minimum confidence 0.5 |
| Routing | `routing/` | 15 hops, hop cost 0.1 |

These constants are starting values. Real data has not tuned them yet.

Design notes and the settled decisions are in [`docs/specs/app-memory/`](docs/specs/app-memory/README.md).

## Frameworks

| Layer | Framework | Used for |
|---|---|---|
| Orchestration | LangGraph | The Pro graph and its state. |
| Models | LangChain, `langchain-google-genai`, `-vertexai`, `-openai`, `-anthropic` | Chat models for every provider. |
| Gemini native | `google-genai` | Files API, caching, and token counting for video analysis. |
| Tool protocol | `mcp` (FastMCP) | The IDE server and the in-process action server. |
| Device | `adbutils`, `uiautomator2`, scrcpy | ADB control, hierarchy fallback, screen recording. |
| Android helper | Java, Gradle, no dependencies | A 37 KB accessibility service that serves the UI tree. |
| Backend | FastAPI, uvicorn, SSE | Admin console and task queue. |
| Front end | Angular 22, RxJS | The web console. |
| CLI | Typer, Rich | The `artemis` command. |
| Config | Pydantic, pydantic-settings, JSONC | Typed config and state. |
| Storage | SQLite (WAL), `sqlite-vec` | Traces, the screen map, and vector search. |
| Graph search | `rustworkx` | Dijkstra over the screen map. |
| Imaging | Pillow, OpenCV, NumPy | Hashing, diffs, overlays. |
| Tooling | uv, ruff, pyright, pytest | Build, lint, types, tests. |

## Configuration

```mermaid
flowchart TB
    JSONC["config/artemis.jsonc"] --> D["default<br/>provider, model, fallback"]
    JSONC --> PR["presets<br/>flagship, flash, cost-saving, local"]
    JSONC --> NO["nodes<br/>per-agent overrides"]
    JSONC --> AG["agent"]
    AG --> FL["flash"]
    AG --> PRO["pro<br/>explorer, checker, committee"]
    AG --> MEM["memory<br/>transcript, chunking, recall"]
    AG --> AMC["app_memory<br/>enabled, harvest, hints, embedding"]
    ENV[".env"] --> KEYS["API keys, ADB settings"]
```

- One file, `config/artemis.jsonc`, with an identical copy bundled in the wheel.
- Pick the profile per task with `--profile flash|pro`, the SDK `TaskRequest.profile`, or the MCP `model` argument.
- App memory switches: `agent.app_memory.enabled`, `.harvest.enabled`, `.hints.enabled`. Hints need all three. Retrieval and descriptions need `GEMINI_API_KEY`, or the key for the embedding provider you configure.
- The checker level is `off`, `final`, `checkpoints`, or `strict`.

## Run it

You need Python 3.12 or later, `uv`, and an Android device with USB debugging on, or an emulator.

```bash
git clone https://github.com/leong1024/engram-gui-agent.git
cd engram-gui-agent
./start.sh          # installs the toolchain and opens the web console
```

On Windows, run `.\start.bat` instead.

```bash
uv run artemis doctor                                   # check the setup
uv run artemis run "Open Settings and read the battery level" --profile flash
uv run artemis run "Turn on dark theme" --profile pro
uv run artemis mcp --install all                        # connect your IDEs
uv run artemis app-memory stats                         # inspect the learned map
```

**On the phone.** The first task installs a small accessibility service, the Artemis helper. It listens on `127.0.0.1` only. Use `artemis helper install`, `status`, or `uninstall` to manage it, or set `ARTEMIS_HIERARCHY_BACKEND=uiautomator` to skip it.

## Develop

| Command | What it does |
|---|---|
| `make lint` | `ruff format --check`, `ruff check`, and the quality ratchet. |
| `make typecheck` | `pyright` on the typed core in `pyright-core.json`. |
| `uv run pytest tests/unit -q` | Unit tests. They need no device. |
| `make test-device` | Tests that need a connected phone. |

The quality ratchet in `scripts/quality_ratchet.py` caps three counts against `.quality-baseline.json`: broad exception handlers, `type: ignore` comments, and functions over 100 lines. A count can fall but not rise. The rules for contributors are in [`CLAUDE.md`](CLAUDE.md).

Set `GEMINI_API_KEY=dummy` to run the full unit suite without a real key. CI runs lint, the ratchet, the typed core, the front-end tests, and a wheel build. It runs the Python unit tests only on manual dispatch.

## Status

| Area | State |
|---|---|
| Flash and Pro profiles | Working. |
| App memory, code | Merged and covered by unit tests. |
| App memory, on a device | **Not yet run.** The device and perf checks in `docs/specs/app-memory/implementation-plan.md` are open. |
| App memory, tuning | Open. The thresholds above, the 20-label limit in state documents, and the single frozen description per state need real scores. |
| Cloud devices | `playground/` has sample deployment code. Treat it as unsupported. |

Hints and harvesting are on by default in `config/artemis.jsonc`.

## Origin

This repository started as an import of [google/artemis](https://github.com/google/artemis) and keeps its Apache-2.0 license. App memory (`artemis/app_memory/` and its specs) is new work here.

Third-party code lives under [`third_party/`](third_party/), one directory per upstream project, each with its own `LICENSE` and `METADATA`.

- [`third_party/mobile_use`](third_party/mobile_use/): portions of [mobile-use](https://github.com/minitap-ai/mobile-use) by Minitap, Inc., Apache License 2.0.

Licensed under the [Apache License 2.0](LICENSE).
