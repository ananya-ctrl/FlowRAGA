from collections.abc import AsyncIterator, Sequence

import httpx

from flowraga.models.providers import GenerationProvider


class GenerationUnavailable(RuntimeError):
    pass


class OllamaGenerationProvider(GenerationProvider):
    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(self, messages: Sequence[dict[str, str]]) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": list(messages),
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                response.raise_for_status()
                answer = response.json().get("message", {}).get("content", "").strip()
        except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError) as exc:
            raise GenerationUnavailable("The local generation model is unavailable") from exc
        if not answer:
            raise GenerationUnavailable("The local generation model returned an empty response")
        return answer

    async def stream(self, messages: Sequence[dict[str, str]]) -> AsyncIterator[str]:
        yield await self.generate(messages)
