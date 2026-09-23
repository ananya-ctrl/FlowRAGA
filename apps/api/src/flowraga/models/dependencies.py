from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from flowraga.core.config import get_settings
from flowraga.models.embeddings import FastEmbedProvider
from flowraga.models.generation import GroqGenerationProvider, OllamaGenerationProvider
from flowraga.models.providers import EmbeddingProvider, GenerationProvider, RerankingProvider
from flowraga.models.reranking import FastEmbedRerankingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return FastEmbedProvider(settings.embedding_model, settings.embedding_dimensions)


def build_generation_provider(model: str | None = None) -> GenerationProvider:
    settings = get_settings()
    if settings.generation_provider == "groq":
        selected_model = model if model and ":" not in model else settings.groq_model
        return GroqGenerationProvider(
            settings.groq_api_key or "",
            settings.groq_base_url,
            selected_model,
            settings.generation_timeout_seconds,
            settings.generation_max_tokens,
        )
    return OllamaGenerationProvider(
        settings.ollama_base_url,
        model or settings.ollama_model,
        settings.generation_timeout_seconds,
    )


@lru_cache
def get_generation_provider() -> GenerationProvider:
    return build_generation_provider()


@lru_cache
def get_reranking_provider() -> RerankingProvider | None:
    try:
        return FastEmbedRerankingProvider(get_settings().reranker_model)
    except RuntimeError:
        return None


EmbeddingDependency = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
GenerationDependency = Annotated[GenerationProvider, Depends(get_generation_provider)]
RerankingDependency = Annotated[RerankingProvider | None, Depends(get_reranking_provider)]
