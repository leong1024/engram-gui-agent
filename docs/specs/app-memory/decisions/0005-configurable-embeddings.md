---
feature: app-memory
status: accepted
date: 2026-11-16
supersedes: null
---

# 0005: Embedding provider set in config, Gemini by default

## Decision

Embeddings go through an `EmbeddingProvider` interface that wraps LangChain `Embeddings`. The
provider is chosen in `agent.app_memory.embedding`: `gemini` (default), `openai` or `ollama`.
Every vector is stored with its `model_id`.

## Options considered

- **Gemini API only.** Fits the default stack and uses the existing key, but locks one provider in.
- **Configurable (chosen).** Matches how ARTEMIS already configures LLM nodes.
- **Local model only.** Works offline and free, but brings a heavy dependency and is weaker on
  paraphrased queries.

## Reason

The work that matters is one interface. The providers are thin wrappers over packages already in
`pyproject.toml`.

## Consequences

- Changing the model means re-embedding. Vectors live in one table per model, so old and new
  models never mix (see [data-model](../data-model.md)).
- `similarity_floor` depends on the model and has to be retuned when the model changes.
