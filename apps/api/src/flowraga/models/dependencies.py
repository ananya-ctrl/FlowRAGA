from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from flowraga.core.config import get_settings
from flowraga.models.embeddings import FastEmbedProvider
from flowraga.models.generation import OllamaGenerationProvider
from flowraga.models.providers import EmbeddingProvider, GenerationProvider, RerankingProvider
from flowraga.models.reranking import FastEmbedRerankingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return FastEmbedProvider(settings.embedding_model, settings.embedding_dimensions)


@lru_cache
def get_generation_provider() -> GenerationProvider:
    settings = get_settings()
    return OllamaGenerationProvider(
        settings.ollama_base_url, settings.ollama_model, settings.generation_timeout_seconds
    )


@lru_cache
def get_reranking_provider() -> RerankingProvider | None:
    try:
        return FastEmbedRerankingProvider(get_settings().reranker_model)
    except RuntimeError:
        return None


EmbeddingDependency = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
GenerationDependency = Annotated[GenerationProvider, Depends(get_generation_provider)]
RerankingDependency = Annotated[RerankingProvider | None, Depends(get_reranking_provider)]
