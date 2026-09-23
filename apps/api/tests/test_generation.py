import httpx
import pytest

from flowraga.models.generation import GenerationUnavailable, GroqGenerationProvider


@pytest.mark.asyncio
async def test_groq_generation_uses_openai_compatible_endpoint(monkeypatch) -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = request.content
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Grounded answer [S1]."}}]},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    provider = GroqGenerationProvider(
        "secret", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", 10
    )
    answer = await provider.generate([{"role": "user", "content": "Question"}])
    assert answer == "Grounded answer [S1]."
    assert captured["path"] == "/openai/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert b"llama-3.3-70b-versatile" in captured["body"]


@pytest.mark.asyncio
async def test_groq_generation_hides_provider_errors(monkeypatch) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    provider = GroqGenerationProvider("secret", "https://example.test/v1", "model", 10)
    with pytest.raises(GenerationUnavailable):
        await provider.generate([{"role": "user", "content": "Question"}])
