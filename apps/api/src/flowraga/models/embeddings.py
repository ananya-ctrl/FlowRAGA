import asyncio
import math
from collections.abc import Sequence

from flowraga.models.providers import EmbeddingProvider


class FastEmbedProvider(EmbeddingProvider):
    """Local ONNX embedding provider backed by an open-weight Hugging Face model."""

    def __init__(self, model_name: str, dimensions: int = 384) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError("Install flowraga-api[models] to run the ingestion worker") from exc
        self._model = TextEmbedding(model_name=model_name)
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = await asyncio.to_thread(lambda: list(self._model.embed(list(texts))))
        return [vector.tolist() for vector in vectors]

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Small deterministic provider for tests; never used as a production model."""

    def __init__(self, dimensions: int = 384) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        result = []
        for text in texts:
            vector = [0.0] * self._dimensions
            for index, byte in enumerate(text.encode("utf-8")):
                vector[index % self._dimensions] += (byte + 1) / 256
            norm = math.sqrt(sum(value * value for value in vector)) or 1
            result.append([value / norm for value in vector])
        return result

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]
