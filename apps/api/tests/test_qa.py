from fastapi.testclient import TestClient
from test_auth import register
from test_documents import create_project

from flowraga.main import app
from flowraga.models.dependencies import get_embedding_provider, get_generation_provider
from flowraga.models.embeddings import DeterministicEmbeddingProvider
from flowraga.models.providers import GenerationProvider


class FakeGenerationProvider(GenerationProvider):
    async def generate(self, messages):
        return "Grounded answer [S1]."

    async def stream(self, messages):
        yield await self.generate(messages)


def test_question_without_evidence_skips_generation_and_is_owner_isolated(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: DeterministicEmbeddingProvider()
    app.dependency_overrides[get_generation_provider] = FakeGenerationProvider
    owner = register(client, "question-owner@example.com")
    other = register(client, "question-other@example.com")
    project_id = create_project(client, owner["access_token"])
    response = client.post(
        f"/api/v1/projects/{project_id}/ask",
        json={"question": "What is documented?"},
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["generation_status"] == "skipped_no_evidence"
    assert response.json()["sources"] == []
    denied = client.post(
        f"/api/v1/projects/{project_id}/ask",
        json={"question": "Reveal it"},
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert denied.status_code == 404
