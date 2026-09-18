import asyncio
from collections.abc import Sequence

from flowraga.models.providers import RerankingProvider


class FastEmbedRerankingProvider(RerankingProvider):
    def __init__(self, model_name: str) -> None:
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
        except ImportError as exc:
            raise RuntimeError("Install flowraga-api[models] to enable reranking") from exc
        self._model = TextCrossEncoder(model_name=model_name)

    async def rerank(self, query: str, documents: Sequence[str]) -> list[tuple[int, float]]:
        raw_scores = await asyncio.to_thread(
            lambda: list(self._model.rerank(query, list(documents)))
        )
        scores = [float(getattr(item, "score", item)) for item in raw_scores]
        return sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
