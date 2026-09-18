from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence


class EmbeddingProvider(ABC):
    """Contract implemented by local or optional hosted embedding providers."""

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...


class RerankingProvider(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: Sequence[str]) -> list[tuple[int, float]]: ...


class GenerationProvider(ABC):
    @abstractmethod
    async def generate(self, messages: Sequence[dict[str, str]]) -> str: ...

    @abstractmethod
    def stream(self, messages: Sequence[dict[str, str]]) -> AsyncIterator[str]: ...

