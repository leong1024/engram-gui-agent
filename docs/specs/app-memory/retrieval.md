---
feature: app-memory
status: draft
depends_on:
  - data-model.md
  - harvesting.md
  - decisions/0001-per-version-maps.md
  - decisions/0005-configurable-embeddings.md
  - decisions/0006-embedded-vector-index.md
code:
  - artemis/app_memory/embeddings.py
  - artemis/app_memory/documents.py
  - artemis/app_memory/document_store.py
  - artemis/app_memory/retrieval.py
  - artemis/utils/plan_grammar.py
  - artemis/services/llm.py
---

# Retrieval

This note covers how a milestone finds its target state. The input is a milestone and the task
goal. The output is a target state in some map, or nothing. Retrieval runs once per milestone
per run, in the background, and the result is cached.

## What gets embedded

Embeddings come from the describer's output (see [harvesting](harvesting.md)), never from raw
screen text.

- **State document:** `"{title}. {purpose} You can: {affordances, joined}. Labels: {up to 20
  static tokens}"`
- **Edge document:** `"{description} (from {src title} to {dst title})"`

Edges are embedded because many milestones describe an action, not a screen, for example "turn
on dark mode". An edge hit nominates its **destination** state as the candidate and keeps the
edge as the suggested last hop.

A document's embedding is written once its description is `ready`. Documents still `pending`
are invisible to retrieval.

## Embedding provider

`EmbeddingProvider`, in `embeddings.py`:

- `model_id: str`: `provider/model@dim`, stored with every vector.
- `embed_documents(texts) -> list[list[float]]`
- `embed_query(text) -> list[float]`

It wraps the LangChain `Embeddings` interface, which the repo's dependencies already provide:

- `gemini` (default): `GoogleGenerativeAIEmbeddings` from `langchain-google-genai`, using the
  existing `GEMINI_API_KEY` / `GOOGLE_API_KEY`. It uses the retrieval-document and
  retrieval-query task types where the model supports them.
- `openai`: `OpenAIEmbeddings` from `langchain-openai`, including OpenAI-compatible base URLs.
- `ollama`: through the OpenAI-compatible endpoint, the same way the repo already reaches Ollama
  for chat.

Config (see [integration-pro](integration-pro.md)) sets `provider`, `model` and optional
`dimensions`. The default model is the current Gemini embedding model at implementation time,
written explicitly in `config/artemis.jsonc`, never inferred.

## The query

The query unit is a **top-level milestone** of the Pro plan, read with `parse_plan` from
[plan_grammar.py](../../../artemis/utils/plan_grammar.py). Its key is the milestone's
`subgoal_hash`, the same hash the step records carry.

- The query text is the milestone text plus its child items' texts.
- The task goal is not embedded. It goes to the LLM rerank as context.

## Candidate maps

At `prepare_run`, one `pm list packages --show-versioncode` call gives the installed version of
every package (shared with [step-recording-fields](../shared/step-recording-fields.md)).

- The **primary maps** are `(package, installed version_code)` for every package that has a
  map with that version.
- The **fallback maps** are up to 2 older versions per package that has a map, newest first,
  plus the `-1` unknown bucket last.

Maps for packages that are not installed are never searched.

## Tier 1: inside each map

For each primary map, in parallel (at most 3 at once):

1. **Vector search.** k-nearest neighbours over that map's states and edges, top **20**.
   Edge hits become their destination states, and duplicates are removed.
2. **Similarity floor.** If the best hit's cosine similarity is below `similarity_floor` (config,
   model-dependent, starting at 0.35), the map is skipped with no LLM call. Most maps are
   irrelevant to a given milestone, and this keeps LLM calls to the maps that plausibly matter.
3. **Rerank.** The LLM node `app_memory_selector` receives the goal, the milestone and the
   candidates. Each candidate is shown as `state_id`, `title`, `purpose`, `affordances`, the
   suggested last-hop edge if any, and `visit_count`. It answers in structured output (through
   `acomplete_structured`): `{state_id | null, confidence: 0-1, reason}`. Null means none of the
   candidates is the milestone's target.

A non-null answer with `confidence ≥ 0.5` is that map's **proposal**.

## Tier 2: across maps

- **No proposal from any primary map:** run tier 1 over the fallback maps, then apply the
  rules below to their proposals. A result from a fallback map is a **borrowed** target.
- **Exactly one proposal:** accept it with no extra call. Tier 1 already judged it.
- **Two or more proposals**, for example two apps that can both "play a song": the
  `app_memory_selector` node runs once more over the proposals and returns one or null. It uses
  the same structured shape, and its candidates are labelled with app and version.

The result is a `TargetResolution`:
- `milestone_key`
- `state_id`, `package`, `version_code`
- `borrowed: bool`
- `confidence`, `reason`
- `last_hop_edge_id`: nullable

It may also be a `NoTarget` carrying the reason.

## Timing and caching

- After the Planner writes the plan, `request_targets(goal, milestones)` starts retrieval for
  every milestone, at most 3 at once. It returns immediately.
- Results are cached per run by `milestone_key`.
- When the Operator edits the plan (see [integration-pro](integration-pro.md)), new milestone
  keys get retrieval, and removed keys are dropped from the cache.
- Each milestone's retrieval has a 20 s budget. When it runs out, the result is `NoTarget`.
- Cost per milestone is one query embedding, one selector call per map that passes the floor,
  and at most one tier-2 call.

## Failure handling

- **Embedding provider unavailable** (no key, network down): retrieval returns `NoTarget` for
  the run. The warning is logged once, not per milestone.
- **Selector call fails** after the LLM layer's own retries and fallback: that map gives no
  proposal.
- **Empty maps or no maps:** `NoTarget` with no LLM call.

## Implementation notes (P4)

P4 builds the describer and the embeddings. The query, the tiers and `retrieval.py` come in P5.

- **Modules.** `describer.py` holds the prompts, the output schemas, `DescriptionLens` and
  `DescriberService`, a `StepMemoryService` with a concurrency of 2. `enrichment.py` holds
  `Enrichment`, which queues jobs and moves every write to the app memory worker thread.
  Description and vector statements live in `DocumentStore` (`document_store.py`), reached as
  `MapStore.documents` on the same connection, so `store.py` is still the only module that
  opens `app_memory.db`. Document texts are built in `documents.py`.
- **Default model.** `gemini-embedding-2`, the newest Gemini embedding model in the installed
  `langchain-google-genai` profiles (released 2026-04-22). The LangChain client already sends
  `RETRIEVAL_DOCUMENT` for documents and `RETRIEVAL_QUERY` for queries, so the wrapper sets no
  task type.
- **`model_id`.** With `dimensions: null` the size is known only from the first vector, so
  `EmbeddingProvider.model_for(dim)` builds the `provider/model@dim` id, and the stored
  `embedding_models` row is looked up by provider and model. `embed_documents` and
  `embed_query` are async, over the LangChain `aembed_*` calls.
- **Vector rows.** Each `vec_` row takes the rowid of its `embeddings` row, and `map_key` is
  `package:version_code`. A changed `text_hash` replaces the vector in place, in the same
  transaction as the `embeddings` row.
- **Edges wait for their endpoints.** An edge is described once its source and destination are
  `ready` or `failed`, or are `@outside`, so its prompt carries both titles. `@outside` reads as
  "outside the app".
- **Queueing.** `prepare_run`, every live harvest pass, finalize, and every saved description
  or vector batch queue up to 50 pending rows and 50 stale documents. Jobs already submitted in
  the run are skipped.
- **Failures.** A describer job that runs out of retries becomes `failed`. An embedding batch
  that fails logs one warning per run and is retried by the next run. With no describer
  credentials, nothing is queued and one warning is logged. With no embedding key, descriptions
  still run and one warning is logged.
- **No task pause.** Describer calls run inside `raise_when_exhausted` from
  [services/llm.py](../../../artemis/services/llm.py), so exhausted retries fail the attempt
  instead of pausing the agent's run.
- **LLM nodes.** `app_memory_describer` and `app_memory_selector` are expanded from `default`
  with their `nodes` overrides. A config written in the full schema, with no `default` block,
  falls back to the `summarizer` node. A `nodes` override of an optional node is now merged
  onto the node it inherits from: `planner_validation` and `validator_pixel_safety_net` onto
  the lightweight judge, `history_analyzer` onto `operator`, `output_analyzer` onto
  `log_analyzer`. Unknown node names are logged. The selector's temperature 0 is left to its
  P5 caller, through `get_llm(..., temperature=0.0)`.
- **Backfill.** `artemis app-memory backfill` harvests but does not describe or embed. Pending
  rows are described by the next run's `prepare_run`.
- **Unit isolation.** `tests/unit/conftest.py` replaces `open_enrichment` with a no-op, so no
  unit test reaches a model. The describer tests pass fakes.

## Testing

All tests are hermetic, using a deterministic fake `EmbeddingProvider` (hash-based vectors) and
`FakeModel` for the selector:

- An edge hit nominates its destination state.
- A map below the similarity floor makes no selector call.
- One proposal skips tier 2. Two proposals call tier 2.
- No primary proposal falls back to an older version and marks the result `borrowed`.
- A plan edit triggers retrieval for exactly the new milestone keys.
- The provider failing yields `NoTarget` and a single warning.
