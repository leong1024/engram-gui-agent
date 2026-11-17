---
feature: app-knowledge
status: draft
depends_on:
  - overview.md
  - decisions/0002-mcp-tool-structured-and-text.md
code:
  - mcp_server/tools/knowledge.py
  - artemis/app_memory/knowledge/
---

# Interface

This note specifies `mobile_get_knowledge`: its arguments, its three levels and the shape of
every response. The tool is a thin adapter over one module, `Knowledge`, in
`artemis/app_memory/knowledge/`.

## Behaviour

The arguments pick the level:

| Call | Level | Answers |
|---|---|---|
| `mobile_get_knowledge()` | Overview | Which apps does Engram know? |
| `mobile_get_knowledge(app="com.android.settings")` | Capabilities | What has Engram seen in this app? |
| `mobile_get_knowledge(query="turn on dark theme")` | Probe | Does Engram know a route for this goal? |
| `mobile_get_knowledge(app=..., query=...)` | Probe | The same, limited to one app. |

`app` is an Android package name. A calling agent learns valid package names from the overview.

Each response has two parts. The tool returns `Annotated[CallToolResult, KnowledgeResponse]`,
which `mcp` 1.29 turns into an advertised output schema plus both parts. See
[Appendix A of the plan](implementation-plan.md#appendix-a-prototype-evidence).

- **Structured content**: a JSON object that matches the level's report schema, for code that
  filters or branches.
- **Text content**: a short markdown summary of the same report, for the calling model to read.
  It ends with one line that says what to do next, for example "Use profile `pro`".

### The `Knowledge` module

The module's interface has three methods. Each returns a typed report and never raises for a
missing map:

- `overview() -> Overview`
- `capabilities(package: str) -> Capabilities | NotMapped`
- `probe(query: str, package: str | None = None) -> ProbeResult`

`render(report) -> str` turns any report into the markdown summary. It picks one render function
per report type from a table. The MCP tool calls one method, then `render`, and returns both
parts. A CLI command can be a second adapter on the same module later.

## Contracts

### Reports

- `AppSummary`: `package`, `version_code`, `version_name`, `pages`, `routes`, `sessions`,
  `last_seen_at`, `recommended_profile` (`pro` or `either`).
- `Overview`: `apps` (a list of `AppSummary`, newest first) and `hints_enabled`.
- `Capabilities`: `app` (an `AppSummary`), `coverage` (`sparse`, `partial` or `broad`),
  `pages` (a list of `PageSummary` with `title`, `capabilities` and `visits`),
  `capabilities` (a de-duplicated list), `example_goals`, and `other_versions`.
- `NotMapped`: `package` and a one-line `reason`.
- `ProbeResult`: `query`, `status` (`found`, `no_match`, `no_maps`, `no_vectors` or
  `provider_unavailable`), and `candidates`.
- `ProbeCandidate`: `package`, `version_code`, `page`, `similarity`, `hops_from_launch` (or
  null when no route exists), and `borrowed`.

### The response wrapper

A tool advertises one output schema, so the three reports share one wrapper,
`KnowledgeResponse`. Its `level` field is `overview`, `capabilities`, `not_mapped` or `probe`,
and exactly one matching field holds the report.

### Size limits

The limits are named constants in the module:

- overview: at most 30 apps;
- capabilities: at most 8 pages, 20 capabilities and 5 example goals;
- probe: at most 3 candidates;
- text summary: at most 3,000 characters, cut at a list item and never mid-word.

### Wording rules

- Every report says it covers what Engram has seen, not what the app can do.
- Every app line names its `version_code`.
- A probe reports `similarity`, not "confidence". It never claims a task will succeed.

## Failure handling

- **No `app_memory.db`**: the overview is empty and says to run Pro tasks to build maps.
- **Unknown package**: `capabilities` returns `NotMapped`.
- **Database unreadable or locked past its timeout**: the tool returns an MCP error result
  with the reason. It does not retry.
- **Both arguments empty strings**: treated as absent.
