import asyncio
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


class GroqGenerationProvider(GenerationProvider):
    def __init__(
        self, api_key: str, base_url: str, model: str, timeout: float, max_tokens: int = 1200
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    async def generate(self, messages: Sequence[dict[str, str]]) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for attempt in range(3):
                    try:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": self.model,
                                "messages": list(messages),
                                "temperature": 0.1,
                                "max_completion_tokens": self.max_tokens,
                            },
                        )
                        response.raise_for_status()
                        answer = response.json()["choices"][0]["message"]["content"].strip()
                        break
                    except httpx.HTTPStatusError as exc:
                        retryable = exc.response.status_code in {429, 500, 502, 503, 504}
                        if not retryable or attempt == 2:
                            raise
                    except httpx.TransportError:
                        if attempt == 2:
                            raise
                    await asyncio.sleep(0.25 * (2**attempt))
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            AttributeError,
            TypeError,
        ) as exc:
            raise GenerationUnavailable("The hosted generation model is unavailable") from exc
        if not answer:
            raise GenerationUnavailable("The hosted generation model returned an empty response")
        return answer

    async def stream(self, messages: Sequence[dict[str, str]]) -> AsyncIterator[str]:
        yield await self.generate(messages)
