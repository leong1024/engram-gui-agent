import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from langchain_core.embeddings import Embeddings
from pydantic import SecretStr

from artemis.app_memory.models import EmbeddingModel
from artemis.config import settings
from artemis.config.agent import AppMemoryEmbeddingConfig
from artemis.config.settings import is_placeholder_key

OLLAMA_BASE_URL = "http://localhost:11434/v1"


class EmbeddingUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EmbeddingProvider:
    """One configured embedding model. Vectors of different models never share a table, so
    every vector is stored under `model_for(len(vector)).model_id`."""

    provider: str
    model: str
    dimensions: int | None
    client: Embeddings

    def model_for(self, dim: int) -> EmbeddingModel:
        return EmbeddingModel(f"{self.provider}/{self.model}@{dim}", self.provider, self.model, dim)

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return await self.client.aembed_documents(list(texts))

    async def embed_query(self, text: str) -> list[float]:
        return await self.client.aembed_query(text)


def _required_key(secret: SecretStr | None, name: str) -> SecretStr:
    if secret is None or is_placeholder_key(secret):
        raise EmbeddingUnavailable(f"{name} is not set")
    return secret


def _gemini(config: AppMemoryEmbeddingConfig) -> Embeddings:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=config.model,
        api_key=_required_key(settings.GOOGLE_API_KEY, "GEMINI_API_KEY"),
        output_dimensionality=config.dimensions,
    )


def _openai(config: AppMemoryEmbeddingConfig) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=config.model,
        api_key=_required_key(settings.OPENAI_API_KEY, "OPENAI_API_KEY"),
        base_url=config.base_url,
        dimensions=config.dimensions,
    )


def _ollama(config: AppMemoryEmbeddingConfig) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    # Ollama takes raw text: OpenAI's token-length check would send token ids instead.
    return OpenAIEmbeddings(
        model=config.model,
        api_key=SecretStr("ollama"),
        base_url=config.base_url or os.environ.get("OPENAI_BASE_URL", OLLAMA_BASE_URL),
        dimensions=config.dimensions,
        check_embedding_ctx_length=False,
    )


PROVIDERS: dict[str, Callable[[AppMemoryEmbeddingConfig], Embeddings]] = {
    "gemini": _gemini,
    "openai": _openai,
    "ollama": _ollama,
}


def open_provider(config: AppMemoryEmbeddingConfig) -> EmbeddingProvider:
    """Raises EmbeddingUnavailable when the provider's key is missing."""
    client = PROVIDERS[config.provider](config)
    return EmbeddingProvider(config.provider, config.model, config.dimensions, client)
